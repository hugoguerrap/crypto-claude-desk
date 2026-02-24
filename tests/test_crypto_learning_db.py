"""
Tests for crypto_learning_db MCP server.

Covers: schema creation, trade CRUD, predictions, prediction track records,
patterns, summaries, migration, and trade modifications.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest import TestCase, main

# Add mcp-servers to path so we can import directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mcp-servers"))

# Point DB to a temp directory before importing
_tmpdir = tempfile.mkdtemp()
os.environ["CRYPTO_DB_DIR"] = _tmpdir

import crypto_learning_db as db  # noqa: E402


class TestSchemaInit(TestCase):
    """Test database initialization and schema creation."""

    def setUp(self):
        # Fresh DB for each test
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()

    def test_schema_creates_all_tables(self):
        conn = db._init_db()
        tables = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
            if not r[0].startswith("sqlite_")  # Exclude internal SQLite tables
        ]
        conn.close()
        expected = [
            "patterns", "portfolio_state",
            "predictions", "summaries",
            "trade_modifications", "trades",
        ]
        self.assertEqual(tables, expected)

    def test_default_portfolio_state(self):
        conn = db._init_db()
        row = conn.execute("SELECT * FROM portfolio_state WHERE id = 1").fetchone()
        conn.close()
        self.assertIsNotNone(row)
        state = dict(row)
        self.assertEqual(state["spot_balance"], 10000)
        self.assertEqual(state["futures_balance"], 10000)
        self.assertEqual(state["currency"], "USDT")

    def test_idempotent_init(self):
        """Running _init_db twice should not fail or duplicate data."""
        db._init_db()
        conn = db._init_db()
        count = conn.execute("SELECT COUNT(*) FROM portfolio_state").fetchone()[0]
        conn.close()
        self.assertEqual(count, 1)


class TestTrades(TestCase):
    """Test trade recording, closing, and querying."""

    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()

    def test_record_trade(self):
        result = db._record_trade(
            trade_id="trade_001",
            symbol="BTC/USDT",
            side="long",
            portfolio_type="futures",
            entry_price=97000,
            usd_amount=1000,
            leverage=3,
            stop_loss=94500,
            take_profit=103200,
            strategy_type="swing",
            reasoning="RSI oversold",
            key_assumptions='["Support holds"]',
            agent_signals='{"market-monitor":"bullish"}',
            learning='{"entry_thesis":"Oversold bounce"}',
        )
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["trade_id"], "trade_001")

    def test_record_trade_deducts_balance(self):
        db._record_trade(
            trade_id="trade_001", symbol="BTC/USDT", side="long",
            portfolio_type="futures", entry_price=97000, usd_amount=1000,
        )
        state = db._get_portfolio_state()
        self.assertEqual(state["portfolio"]["futures_balance"], 9000)
        self.assertEqual(state["portfolio"]["spot_balance"], 10000)

    def test_record_trade_spot_deducts_spot(self):
        db._record_trade(
            trade_id="trade_002", symbol="ETH/USDT", side="long",
            portfolio_type="spot", entry_price=3000, usd_amount=500,
        )
        state = db._get_portfolio_state()
        self.assertEqual(state["portfolio"]["spot_balance"], 9500)

    def test_close_trade_long_win(self):
        db._record_trade(
            trade_id="trade_001", symbol="BTC/USDT", side="long",
            portfolio_type="futures", entry_price=97000, usd_amount=1000,
            leverage=3,
        )
        result = db._close_trade("trade_001", exit_price=100000, close_reason="TP hit")
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["result"], "win")
        self.assertGreater(result["pnl_usd"], 0)
        # PnL = 1000 * (((100000 - 97000) / 97000) * 100 * 3) / 100
        expected_pnl = 1000 * (((100000 - 97000) / 97000) * 100 * 3) / 100
        self.assertAlmostEqual(result["pnl_usd"], round(expected_pnl, 2), places=1)

    def test_close_trade_long_loss(self):
        db._record_trade(
            trade_id="trade_001", symbol="BTC/USDT", side="long",
            portfolio_type="futures", entry_price=97000, usd_amount=1000,
            leverage=3,
        )
        result = db._close_trade("trade_001", exit_price=94000, close_reason="SL hit")
        self.assertEqual(result["result"], "loss")
        self.assertLess(result["pnl_usd"], 0)

    def test_close_trade_short_win(self):
        db._record_trade(
            trade_id="trade_001", symbol="BTC/USDT", side="short",
            portfolio_type="futures", entry_price=97000, usd_amount=1000,
            leverage=2,
        )
        result = db._close_trade("trade_001", exit_price=94000)
        self.assertEqual(result["result"], "win")
        self.assertGreater(result["pnl_usd"], 0)

    def test_close_trade_updates_portfolio(self):
        db._record_trade(
            trade_id="trade_001", symbol="BTC/USDT", side="long",
            portfolio_type="futures", entry_price=97000, usd_amount=1000,
            leverage=3,
        )
        result = db._close_trade("trade_001", exit_price=100000)
        state = db._get_portfolio_state()
        # Balance should be: initial 10000 - 1000 (open) + 1000 (returned) + pnl
        expected = 10000 + result["pnl_usd"]
        self.assertAlmostEqual(state["portfolio"]["futures_balance"], expected, places=1)
        self.assertEqual(state["portfolio"]["wins"], 1)
        self.assertEqual(state["portfolio"]["losses"], 0)

    def test_close_nonexistent_trade(self):
        result = db._close_trade("trade_999", exit_price=100000)
        self.assertEqual(result["status"], "error")

    def test_query_trades_all(self):
        db._record_trade(
            trade_id="trade_001", symbol="BTC/USDT", side="long",
            portfolio_type="futures", entry_price=97000, usd_amount=1000,
        )
        db._record_trade(
            trade_id="trade_002", symbol="ETH/USDT", side="short",
            portfolio_type="spot", entry_price=3000, usd_amount=500,
        )
        result = db._query_trades()
        self.assertEqual(result["total"], 2)
        self.assertEqual(len(result["trades"]), 2)

    def test_query_trades_filter_symbol(self):
        db._record_trade(
            trade_id="trade_001", symbol="BTC/USDT", side="long",
            portfolio_type="futures", entry_price=97000, usd_amount=1000,
        )
        db._record_trade(
            trade_id="trade_002", symbol="ETH/USDT", side="short",
            portfolio_type="spot", entry_price=3000, usd_amount=500,
        )
        result = db._query_trades(symbol="BTC/USDT")
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["trades"][0]["symbol"], "BTC/USDT")

    def test_query_trades_filter_status(self):
        db._record_trade(
            trade_id="trade_001", symbol="BTC/USDT", side="long",
            portfolio_type="futures", entry_price=97000, usd_amount=1000,
        )
        db._close_trade("trade_001", exit_price=100000)
        db._record_trade(
            trade_id="trade_002", symbol="ETH/USDT", side="long",
            portfolio_type="spot", entry_price=3000, usd_amount=500,
        )
        open_trades = db._query_trades(status="open")
        closed_trades = db._query_trades(status="closed")
        self.assertEqual(open_trades["total"], 1)
        self.assertEqual(closed_trades["total"], 1)

    def test_query_trades_limit_offset(self):
        for i in range(5):
            db._record_trade(
                trade_id=f"trade_{i:03d}", symbol="BTC/USDT", side="long",
                portfolio_type="futures", entry_price=97000, usd_amount=100,
            )
        result = db._query_trades(limit=2, offset=0)
        self.assertEqual(len(result["trades"]), 2)
        self.assertEqual(result["total"], 5)

    def test_duplicate_trade_id_fails(self):
        db._record_trade(
            trade_id="trade_001", symbol="BTC/USDT", side="long",
            portfolio_type="futures", entry_price=97000, usd_amount=1000,
        )
        result = db._record_trade(
            trade_id="trade_001", symbol="ETH/USDT", side="long",
            portfolio_type="spot", entry_price=3000, usd_amount=500,
        )
        self.assertEqual(result["status"], "error")

    def test_get_portfolio_state_shows_open_trades(self):
        db._record_trade(
            trade_id="trade_001", symbol="BTC/USDT", side="long",
            portfolio_type="futures", entry_price=97000, usd_amount=1000,
        )
        state = db._get_portfolio_state()
        self.assertEqual(state["open_trades_count"], 1)
        self.assertEqual(len(state["open_trades"]), 1)
        self.assertEqual(state["open_trades"][0]["id"], "trade_001")


class TestPredictions(TestCase):
    """Test prediction recording, querying, and validation."""

    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db._record_trade(
            trade_id="trade_001", symbol="BTC/USDT", side="long",
            portfolio_type="futures", entry_price=97000, usd_amount=1000,
        )

    def test_record_prediction(self):
        result = db._record_prediction(
            prediction_id="pred_001",
            trade_id="trade_001",
            symbol="BTC/USDT",
            agent="technical-analyst",
            prediction_type="price_direction",
            prediction="BTC will break $100k",
            target_value=100000,
            timeframe_hours=72,
            confidence=0.75,
        )
        self.assertEqual(result["status"], "success")

    def test_query_predictions_by_trade(self):
        db._record_prediction(
            prediction_id="pred_001", trade_id="trade_001",
            symbol="BTC/USDT", agent="technical-analyst",
            prediction_type="price_direction",
            prediction="BTC will break $100k",
        )
        db._record_prediction(
            prediction_id="pred_002", trade_id="trade_001",
            symbol="BTC/USDT", agent="news-sentiment",
            prediction_type="sentiment",
            prediction="No negative catalysts",
        )
        result = db._query_predictions(trade_id="trade_001")
        self.assertEqual(len(result["predictions"]), 2)

    def test_query_predictions_by_agent(self):
        db._record_prediction(
            prediction_id="pred_001", trade_id="trade_001",
            symbol="BTC/USDT", agent="technical-analyst",
            prediction_type="price_direction",
            prediction="BTC will break $100k",
        )
        db._record_prediction(
            prediction_id="pred_002", trade_id="trade_001",
            symbol="BTC/USDT", agent="news-sentiment",
            prediction_type="sentiment",
            prediction="No negative catalysts",
        )
        result = db._query_predictions(agent="technical-analyst")
        self.assertEqual(len(result["predictions"]), 1)

    def test_validate_prediction_correct(self):
        db._record_prediction(
            prediction_id="pred_001", trade_id="trade_001",
            symbol="BTC/USDT", agent="technical-analyst",
            prediction_type="price_direction",
            prediction="BTC will break $100k",
            confidence=0.75,
        )
        result = db._validate_prediction(
            prediction_id="pred_001",
            actual_outcome="BTC reached $101k",
            is_correct=True,
            error_margin=1.0,
            evaluation="Nailed it. BTC broke $100k as predicted.",
        )
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["result"], "correct")
        self.assertEqual(result["agent"], "technical-analyst")

    def test_validate_prediction_incorrect(self):
        db._record_prediction(
            prediction_id="pred_001", trade_id="trade_001",
            symbol="BTC/USDT", agent="technical-analyst",
            prediction_type="price_direction",
            prediction="BTC will break $100k",
        )
        result = db._validate_prediction(
            prediction_id="pred_001",
            actual_outcome="BTC dropped to $94k",
            is_correct=False,
            evaluation="Completely wrong direction. Market sold off on regulatory news.",
        )
        self.assertEqual(result["result"], "incorrect")
        self.assertEqual(result["agent"], "technical-analyst")

    def test_validate_prediction_stores_evaluation(self):
        db._record_prediction(
            prediction_id="pred_001", trade_id="trade_001",
            symbol="BTC/USDT", agent="technical-analyst",
            prediction_type="price_direction",
            prediction="BTC will break $100k",
        )
        eval_text = "Near miss — BTC hit $99.8k. Direction was right."
        db._validate_prediction(
            "pred_001", "BTC reached $99.8k", is_correct=False,
            error_margin=0.2, evaluation=eval_text,
        )
        preds = db._query_predictions(trade_id="trade_001")
        self.assertEqual(preds["predictions"][0]["evaluation"], eval_text)

    def test_validate_nonexistent_prediction(self):
        result = db._validate_prediction(
            prediction_id="pred_999",
            actual_outcome="doesn't matter",
            is_correct=True,
        )
        self.assertEqual(result["status"], "error")


class TestPatterns(TestCase):
    """Test pattern creation, update, and querying."""

    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()

    def test_create_pattern(self):
        result = db._upsert_pattern(
            name="oversold_bounce",
            conditions='["RSI <35", "funding <-0.01%"]',
            is_win=True,
            pnl_percent=5.2,
            notes="First observation",
        )
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["action"], "created")

    def test_update_existing_pattern(self):
        db._upsert_pattern(name="oversold_bounce", is_win=True, pnl_percent=5.0)
        db._upsert_pattern(name="oversold_bounce", is_win=True, pnl_percent=3.0)
        db._upsert_pattern(name="oversold_bounce", is_win=False, pnl_percent=-2.0)

        result = db._query_patterns()
        pat = result["patterns"][0]
        self.assertEqual(pat["occurrences"], 3)
        self.assertEqual(pat["wins"], 2)
        self.assertEqual(pat["losses"], 1)
        self.assertAlmostEqual(pat["win_rate"], 2 / 3, places=3)

    def test_pattern_recommendation_seek(self):
        # 3 wins, 1 loss = 75% → SEEK
        for i in range(3):
            db._upsert_pattern(name="breakout", is_win=True, pnl_percent=4.0)
        db._upsert_pattern(name="breakout", is_win=False, pnl_percent=-2.0)

        result = db._query_patterns()
        pat = result["patterns"][0]
        self.assertEqual(pat["recommendation"], "SEEK")

    def test_pattern_recommendation_avoid(self):
        # 1 win, 3 losses = 25% → AVOID
        db._upsert_pattern(name="fomo_entry", is_win=True, pnl_percent=2.0)
        for i in range(3):
            db._upsert_pattern(name="fomo_entry", is_win=False, pnl_percent=-3.0)

        result = db._query_patterns()
        pat = next(p for p in result["patterns"] if p["name"] == "fomo_entry")
        self.assertEqual(pat["recommendation"], "AVOID")

    def test_pattern_recommendation_neutral(self):
        # 1 win, 1 loss = 50% → NEUTRAL
        db._upsert_pattern(name="range_play", is_win=True, pnl_percent=3.0)
        db._upsert_pattern(name="range_play", is_win=False, pnl_percent=-2.0)

        result = db._query_patterns()
        pat = next(p for p in result["patterns"] if p["name"] == "range_play")
        self.assertEqual(pat["recommendation"], "NEUTRAL")

    def test_query_patterns_filter_win_rate(self):
        db._upsert_pattern(name="good_pattern", is_win=True, pnl_percent=5.0)
        db._upsert_pattern(name="bad_pattern", is_win=False, pnl_percent=-3.0)

        result = db._query_patterns(min_win_rate=0.5)
        names = [p["name"] for p in result["patterns"]]
        self.assertIn("good_pattern", names)
        self.assertNotIn("bad_pattern", names)

    def test_query_patterns_filter_occurrences(self):
        db._upsert_pattern(name="proven", is_win=True, pnl_percent=5.0)
        db._upsert_pattern(name="proven", is_win=True, pnl_percent=4.0)
        db._upsert_pattern(name="proven", is_win=True, pnl_percent=3.0)
        db._upsert_pattern(name="new_one", is_win=True, pnl_percent=5.0)

        result = db._query_patterns(min_occurrences=3)
        self.assertEqual(len(result["patterns"]), 1)
        self.assertEqual(result["patterns"][0]["name"], "proven")


class TestSummaries(TestCase):
    """Test summary generation and retrieval."""

    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()

    def test_generate_summary_empty(self):
        result = db._generate_summary(period="2026-02", summary_type="monthly")
        self.assertEqual(result["status"], "success")
        self.assertIn("Trading Summary: 2026-02", result["summary"])

    def test_generate_summary_with_data(self):
        # Create and close a trade in Feb 2026
        db._record_trade(
            trade_id="trade_001", symbol="BTC/USDT", side="long",
            portfolio_type="futures", entry_price=97000, usd_amount=1000,
            leverage=3, strategy_type="swing",
        )
        db._close_trade("trade_001", exit_price=100000, close_reason="TP hit")

        result = db._generate_summary(period="2026-02", summary_type="monthly")
        self.assertEqual(result["status"], "success")
        self.assertIn("Total trades", result["summary"])

    def test_get_summary(self):
        db._generate_summary(period="2026-02", summary_type="monthly")
        result = db._get_summary(period="2026-02", summary_type="monthly")
        self.assertIsNotNone(result["summary"])

    def test_get_summary_not_found(self):
        result = db._get_summary(period="2025-01", summary_type="monthly")
        self.assertIsNone(result["summary"])

    def test_generate_quarterly_summary(self):
        result = db._generate_summary(period="2026-Q1", summary_type="quarterly")
        self.assertEqual(result["status"], "success")
        self.assertIn("2026-Q1", result["summary"])


class TestTradeStats(TestCase):
    """Test aggregated trade statistics."""

    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()

    def _create_and_close(self, trade_id, symbol, entry, exit_price, strategy="swing"):
        db._record_trade(
            trade_id=trade_id, symbol=symbol, side="long",
            portfolio_type="futures", entry_price=entry, usd_amount=500,
            leverage=2, strategy_type=strategy,
        )
        db._close_trade(trade_id, exit_price=exit_price)

    def test_stats_empty(self):
        result = db._get_trade_stats()
        self.assertEqual(result["stats"]["total"], 0)

    def test_stats_overall(self):
        self._create_and_close("t1", "BTC/USDT", 97000, 100000)
        self._create_and_close("t2", "BTC/USDT", 97000, 94000)
        self._create_and_close("t3", "ETH/USDT", 3000, 3200)

        result = db._get_trade_stats()
        self.assertEqual(result["stats"]["total"], 3)
        self.assertEqual(result["stats"]["wins"], 2)
        self.assertEqual(result["stats"]["losses"], 1)
        self.assertAlmostEqual(result["stats"]["win_rate"], 2 / 3, places=3)

    def test_stats_filter_symbol(self):
        self._create_and_close("t1", "BTC/USDT", 97000, 100000)
        self._create_and_close("t2", "ETH/USDT", 3000, 3200)

        result = db._get_trade_stats(symbol="BTC/USDT")
        self.assertEqual(result["stats"]["total"], 1)

    def test_stats_filter_strategy(self):
        self._create_and_close("t1", "BTC/USDT", 97000, 100000, strategy="swing")
        self._create_and_close("t2", "BTC/USDT", 97000, 100000, strategy="scalp")

        result = db._get_trade_stats(strategy_type="swing")
        self.assertEqual(result["stats"]["total"], 1)


class TestMigration(TestCase):
    """Test JSON to SQLite migration."""

    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        self.json_dir = tempfile.mkdtemp()

    def test_migrate_from_example_files(self):
        """Test migration from .example JSON files."""
        # Create realistic JSON files
        portfolio = {
            "portfolios": {
                "spot": {"initial_balance": 10000, "current_balance": 9500, "currency": "USDT"},
                "futures": {"initial_balance": 10000, "current_balance": 10200, "currency": "USDT"},
            },
            "open_trades": [
                {
                    "id": "trade_001", "symbol": "BTC/USDT", "side": "long",
                    "portfolio_type": "futures", "entry_price": 97000,
                    "usd_amount": 1000, "leverage": 3, "stop_loss": 94500,
                    "take_profit": 103200, "strategy_type": "swing",
                    "opened_at": "2026-02-16T14:30:00Z",
                    "reasoning": "RSI oversold",
                    "key_assumptions": ["Support holds"],
                    "agent_signals": {"market-monitor": "bullish"},
                    "learning": {"entry_thesis": "Oversold bounce"},
                }
            ],
            "closed_trades": [
                {
                    "id": "trade_000", "symbol": "ETH/USDT", "side": "long",
                    "portfolio_type": "spot", "entry_price": 3000,
                    "exit_price": 3200, "usd_amount": 500, "leverage": 1,
                    "opened_at": "2026-02-10T10:00:00Z",
                    "closed_at": "2026-02-12T10:00:00Z",
                    "close_reason": "TP hit", "pnl_usd": 33.33,
                    "pnl_percent": 6.67, "result": "win",
                    "strategy_type": "swing",
                }
            ],
            "stats": {"total_trades": 2, "wins": 1, "losses": 0, "total_pnl": 33.33},
        }
        predictions = {
            "predictions": [
                {
                    "id": "pred_001", "trade_id": "trade_001", "symbol": "BTC/USDT",
                    "agent": "technical-analyst", "prediction_type": "price_direction",
                    "prediction": "BTC to $100k", "target_value": 100000,
                    "timeframe_hours": 72, "confidence": 0.75, "status": "pending",
                }
            ],
            "stats": {"total": 1, "correct": 0, "incorrect": 0, "pending": 1},
        }
        patterns = {
            "patterns": [
                {
                    "name": "oversold_bounce", "conditions": ["RSI <35"],
                    "occurrences": 3, "wins": 2, "losses": 1, "win_rate": 0.67,
                    "avg_pnl_percent": 3.5, "first_seen": "2026-01-15",
                    "last_seen": "2026-02-10", "recommendation": "SEEK",
                    "notes": "Works well with negative funding",
                }
            ],
            "stats": {"total_patterns": 1, "avg_win_rate": 0.67},
        }

        Path(self.json_dir, "portfolio.json").write_text(json.dumps(portfolio))
        Path(self.json_dir, "predictions.json").write_text(json.dumps(predictions))
        Path(self.json_dir, "patterns.json").write_text(json.dumps(patterns))

        result = db._migrate_from_json(self.json_dir)
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["migrated"]["trades"], 2)
        self.assertEqual(result["migrated"]["predictions"], 1)
        self.assertEqual(result["migrated"]["patterns"], 1)

        # Verify data is queryable
        state = db._get_portfolio_state()
        self.assertEqual(state["portfolio"]["spot_balance"], 9500)
        self.assertEqual(state["portfolio"]["futures_balance"], 10200)

        trades = db._query_trades()
        self.assertEqual(trades["total"], 2)

        preds = db._query_predictions(status="pending")
        self.assertEqual(len(preds["predictions"]), 1)

        pats = db._query_patterns()
        self.assertEqual(len(pats["patterns"]), 1)
        self.assertEqual(pats["patterns"][0]["name"], "oversold_bounce")

    def test_migrate_idempotent(self):
        """Running migration twice should not duplicate data."""
        portfolio = {
            "portfolios": {
                "spot": {"initial_balance": 10000, "current_balance": 10000},
                "futures": {"initial_balance": 10000, "current_balance": 10000},
            },
            "open_trades": [],
            "closed_trades": [],
            "stats": {"total_trades": 0, "wins": 0, "losses": 0, "total_pnl": 0},
        }
        Path(self.json_dir, "portfolio.json").write_text(json.dumps(portfolio))

        db._migrate_from_json(self.json_dir)
        db._migrate_from_json(self.json_dir)  # Second run
        state = db._get_portfolio_state()
        self.assertEqual(state["portfolio"]["spot_balance"], 10000)

    def test_migrate_missing_files(self):
        """Migration should work with missing files (uses .example if available)."""
        result = db._migrate_from_json(self.json_dir)
        self.assertEqual(result["status"], "success")


class TestDbStats(TestCase):
    """Test database statistics."""

    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()

    def test_db_stats(self):
        db._record_trade(
            trade_id="trade_001", symbol="BTC/USDT", side="long",
            portfolio_type="futures", entry_price=97000, usd_amount=1000,
        )
        result = db._get_db_stats()
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["tables"]["trades"], 1)
        self.assertGreater(result["db_size_bytes"], 0)


class TestContextWindowScaling(TestCase):
    """Test that the system scales without context window issues.
    This is the key test: verify that queries return bounded results
    even with many trades."""

    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()

    def test_query_returns_bounded_results(self):
        """Even with 500 trades, queries return only the requested limit."""
        for i in range(500):
            db._record_trade(
                trade_id=f"trade_{i:04d}",
                symbol="BTC/USDT" if i % 2 == 0 else "ETH/USDT",
                side="long",
                portfolio_type="futures",
                entry_price=97000,
                usd_amount=10,
                strategy_type="swing" if i % 3 == 0 else "scalp",
            )

        # Default limit is 20
        result = db._query_trades()
        self.assertEqual(len(result["trades"]), 20)
        self.assertEqual(result["total"], 500)

        # Custom limit
        result = db._query_trades(limit=5)
        self.assertEqual(len(result["trades"]), 5)

        # Filtered
        result = db._query_trades(symbol="BTC/USDT", limit=10)
        self.assertEqual(len(result["trades"]), 10)
        self.assertEqual(result["total"], 250)

    def test_portfolio_state_constant_size(self):
        """Portfolio state should be O(1) regardless of trade count, plus open trades only."""
        for i in range(100):
            db._record_trade(
                trade_id=f"trade_{i:04d}", symbol="BTC/USDT", side="long",
                portfolio_type="futures", entry_price=97000, usd_amount=1,
            )
            if i < 97:  # Close most trades, keep 3 open
                db._close_trade(f"trade_{i:04d}", exit_price=98000)

        state = db._get_portfolio_state()
        self.assertEqual(state["open_trades_count"], 3)
        self.assertEqual(len(state["open_trades"]), 3)
        # Portfolio stats are aggregated, not full history
        self.assertEqual(state["portfolio"]["total_trades"], 100)

    def test_stats_aggregate_instead_of_full_read(self):
        """get_trade_stats returns aggregated data, not individual trades."""
        for i in range(200):
            db._record_trade(
                trade_id=f"trade_{i:04d}", symbol="BTC/USDT", side="long",
                portfolio_type="futures", entry_price=97000, usd_amount=1,
            )
            db._close_trade(f"trade_{i:04d}", exit_price=98000 if i % 3 != 0 else 95000)

        result = db._get_trade_stats(symbol="BTC/USDT")
        # Returns aggregate numbers, not 200 rows
        self.assertIn("total", result["stats"])
        self.assertIn("win_rate", result["stats"])
        self.assertIn("avg_pnl_pct", result["stats"])
        self.assertEqual(result["stats"]["total"], 200)


class TestEvaluationDrivenValidation(TestCase):
    """Test NL evaluation storage — no formula scoring."""

    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db._record_trade(
            trade_id="trade_001", symbol="BTC/USDT", side="long",
            portfolio_type="futures", entry_price=97000, usd_amount=1000,
            strategy_type="swing",
        )

    def test_evaluation_stored_in_prediction(self):
        db._record_prediction(
            prediction_id="pred_001", trade_id="trade_001",
            symbol="BTC/USDT", agent="technical-analyst",
            prediction_type="price_direction", prediction="up",
        )
        eval_text = "Direction correct. BTC rose 3% as predicted. RSI analysis was spot-on."
        db._validate_prediction(
            "pred_001", "BTC rose 3%", is_correct=True,
            evaluation=eval_text,
        )
        preds = db._query_predictions(trade_id="trade_001")
        self.assertEqual(preds["predictions"][0]["evaluation"], eval_text)

    def test_evaluation_empty_is_ok(self):
        """Evaluation is optional — backward compatible."""
        db._record_prediction(
            prediction_id="pred_001", trade_id="trade_001",
            symbol="BTC/USDT", agent="technical-analyst",
            prediction_type="price_direction", prediction="up",
        )
        result = db._validate_prediction("pred_001", "went up", is_correct=True)
        self.assertEqual(result["status"], "success")

    def test_no_confidence_adjustment_in_result(self):
        """Result should NOT contain confidence_adjustment, credit, or new_accuracy."""
        db._record_prediction(
            prediction_id="pred_001", trade_id="trade_001",
            symbol="BTC/USDT", agent="technical-analyst",
            prediction_type="price_direction", prediction="up",
        )
        result = db._validate_prediction("pred_001", "went up", is_correct=True)
        self.assertNotIn("confidence_adjustment", result)
        self.assertNotIn("credit", result)
        self.assertNotIn("new_accuracy", result)

    def test_validate_returns_agent(self):
        """Validate should return the agent name for reference."""
        db._record_prediction(
            prediction_id="pred_001", trade_id="trade_001",
            symbol="BTC/USDT", agent="technical-analyst",
            prediction_type="price_direction", prediction="up",
        )
        result = db._validate_prediction("pred_001", "went up", is_correct=True)
        self.assertEqual(result["agent"], "technical-analyst")

    def test_double_validate_rejected(self):
        """Cannot validate the same prediction twice."""
        db._record_prediction(
            prediction_id="pred_001", trade_id="trade_001",
            symbol="BTC/USDT", agent="technical-analyst",
            prediction_type="price_direction", prediction="up",
        )
        db._validate_prediction("pred_001", "went up", is_correct=True)
        result = db._validate_prediction("pred_001", "went up again", is_correct=False)
        self.assertEqual(result["status"], "error")


class TestPredictionTrackRecord(TestCase):
    """Test prediction-centric track record queries."""

    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        # Create trades with different strategies
        db._record_trade(
            trade_id="trade_001", symbol="BTC/USDT", side="long",
            portfolio_type="futures", entry_price=97000, usd_amount=1000,
            strategy_type="swing",
        )
        db._record_trade(
            trade_id="trade_002", symbol="ETH/USDT", side="long",
            portfolio_type="spot", entry_price=3000, usd_amount=500,
            strategy_type="scalp",
        )

    def test_empty_track_record(self):
        result = db._get_prediction_track_record(agent="technical-analyst")
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["windows"]["global"]["total"], 0)
        self.assertIsNone(result["windows"]["global"]["accuracy"])

    def test_track_record_with_data(self):
        for i in range(5):
            db._record_prediction(
                prediction_id=f"pred_{i:03d}", trade_id="trade_001",
                symbol="BTC/USDT", agent="technical-analyst",
                prediction_type="price_direction", prediction=f"pred {i}",
            )
            db._validate_prediction(
                f"pred_{i:03d}", "actual", is_correct=(i < 3)  # 3 correct, 2 wrong
            )
        result = db._get_prediction_track_record(agent="technical-analyst")
        self.assertEqual(result["windows"]["global"]["total"], 5)
        self.assertEqual(result["windows"]["global"]["correct"], 3)
        self.assertAlmostEqual(result["windows"]["global"]["accuracy"], 0.6, places=2)

    def test_filter_by_symbol(self):
        db._record_prediction(
            prediction_id="pred_btc", trade_id="trade_001",
            symbol="BTC/USDT", agent="technical-analyst",
            prediction_type="price_direction", prediction="up",
        )
        db._record_prediction(
            prediction_id="pred_eth", trade_id="trade_002",
            symbol="ETH/USDT", agent="technical-analyst",
            prediction_type="price_direction", prediction="up",
        )
        db._validate_prediction("pred_btc", "went up", is_correct=True)
        db._validate_prediction("pred_eth", "went down", is_correct=False)

        btc_result = db._get_prediction_track_record(symbol="BTC/USDT")
        self.assertEqual(btc_result["windows"]["global"]["total"], 1)
        self.assertEqual(btc_result["windows"]["global"]["correct"], 1)
        self.assertEqual(btc_result["filters"]["symbol"], "BTC/USDT")

        eth_result = db._get_prediction_track_record(symbol="ETH/USDT")
        self.assertEqual(eth_result["windows"]["global"]["total"], 1)
        self.assertEqual(eth_result["windows"]["global"]["correct"], 0)

    def test_filter_by_strategy_type(self):
        db._record_prediction(
            prediction_id="pred_swing", trade_id="trade_001",
            symbol="BTC/USDT", agent="technical-analyst",
            prediction_type="price_direction", prediction="up",
        )
        db._record_prediction(
            prediction_id="pred_scalp", trade_id="trade_002",
            symbol="ETH/USDT", agent="technical-analyst",
            prediction_type="price_direction", prediction="up",
        )
        db._validate_prediction("pred_swing", "went up", is_correct=True)
        db._validate_prediction("pred_scalp", "went up", is_correct=True)

        result = db._get_prediction_track_record(strategy_type="swing")
        self.assertEqual(result["windows"]["global"]["total"], 1)
        self.assertEqual(result["filters"]["strategy_type"], "swing")

    def test_filter_by_agent(self):
        db._record_prediction(
            prediction_id="pred_ta", trade_id="trade_001",
            symbol="BTC/USDT", agent="technical-analyst",
            prediction_type="price_direction", prediction="up",
        )
        db._record_prediction(
            prediction_id="pred_ns", trade_id="trade_001",
            symbol="BTC/USDT", agent="news-sentiment",
            prediction_type="sentiment", prediction="bullish",
        )
        db._validate_prediction("pred_ta", "went up", is_correct=True)
        db._validate_prediction("pred_ns", "bullish confirmed", is_correct=True)

        result = db._get_prediction_track_record(agent="technical-analyst")
        self.assertEqual(result["windows"]["global"]["total"], 1)
        self.assertEqual(result["filters"]["agent"], "technical-analyst")

    def test_filter_by_prediction_type(self):
        db._record_prediction(
            prediction_id="pred_dir", trade_id="trade_001",
            symbol="BTC/USDT", agent="technical-analyst",
            prediction_type="price_direction", prediction="up",
        )
        db._record_prediction(
            prediction_id="pred_sup", trade_id="trade_001",
            symbol="BTC/USDT", agent="technical-analyst",
            prediction_type="support_level", prediction="holds $96k",
        )
        db._validate_prediction("pred_dir", "went up", is_correct=True)
        db._validate_prediction("pred_sup", "held", is_correct=True)

        result = db._get_prediction_track_record(prediction_type="price_direction")
        self.assertEqual(result["windows"]["global"]["total"], 1)

    def test_combined_filters(self):
        """Multiple filters should narrow results."""
        db._record_prediction(
            prediction_id="pred_001", trade_id="trade_001",
            symbol="BTC/USDT", agent="technical-analyst",
            prediction_type="price_direction", prediction="up",
        )
        db._validate_prediction("pred_001", "went up", is_correct=True)

        result = db._get_prediction_track_record(
            symbol="BTC/USDT", strategy_type="swing", agent="technical-analyst"
        )
        self.assertEqual(result["windows"]["global"]["total"], 1)
        self.assertEqual(result["windows"]["global"]["accuracy"], 1.0)

        # Non-matching combo returns 0
        result = db._get_prediction_track_record(
            symbol="ETH/USDT", strategy_type="swing"
        )
        self.assertEqual(result["windows"]["global"]["total"], 0)

    def test_time_windows(self):
        """Data created now should appear in all time windows."""
        db._record_prediction(
            prediction_id="pred_001", trade_id="trade_001",
            symbol="BTC/USDT", agent="technical-analyst",
            prediction_type="test", prediction="test",
        )
        db._validate_prediction("pred_001", "actual", is_correct=True)

        result = db._get_prediction_track_record(agent="technical-analyst")
        w = result["windows"]
        self.assertEqual(w["7d"]["total"], 1)
        self.assertEqual(w["30d"]["total"], 1)
        self.assertEqual(w["90d"]["total"], 1)
        self.assertEqual(w["global"]["total"], 1)

    def test_custom_windows(self):
        result = db._get_prediction_track_record(
            agent="technical-analyst", days_windows="[3,14]"
        )
        w = result["windows"]
        self.assertIn("3d", w)
        self.assertIn("14d", w)
        self.assertIn("global", w)
        self.assertNotIn("7d", w)

    def test_includes_evaluations(self):
        eval_text = "Excellent call. RSI oversold + funding negative = textbook setup."
        db._record_prediction(
            prediction_id="pred_001", trade_id="trade_001",
            symbol="BTC/USDT", agent="technical-analyst",
            prediction_type="price_direction", prediction="up",
        )
        db._validate_prediction(
            "pred_001", "BTC up 5%", is_correct=True,
            evaluation=eval_text,
        )
        result = db._get_prediction_track_record(agent="technical-analyst")
        evals = result["windows"]["recent_evaluations"]
        self.assertEqual(len(evals), 1)
        self.assertEqual(evals[0]["evaluation"], eval_text)
        # Should include agent and strategy_type from JOIN
        self.assertEqual(evals[0]["agent"], "technical-analyst")
        self.assertEqual(evals[0]["strategy_type"], "swing")

    def test_excludes_evaluations_when_zero(self):
        db._record_prediction(
            prediction_id="pred_001", trade_id="trade_001",
            symbol="BTC/USDT", agent="technical-analyst",
            prediction_type="test", prediction="test",
        )
        db._validate_prediction("pred_001", "outcome", is_correct=True,
                                evaluation="some eval")
        result = db._get_prediction_track_record(
            agent="technical-analyst", include_evaluations=0
        )
        self.assertNotIn("recent_evaluations", result["windows"])

    def test_no_filters_returns_all(self):
        """Without any filters, returns all validated predictions."""
        db._record_prediction(
            prediction_id="pred_001", trade_id="trade_001",
            symbol="BTC/USDT", agent="technical-analyst",
            prediction_type="price_direction", prediction="up",
        )
        db._record_prediction(
            prediction_id="pred_002", trade_id="trade_002",
            symbol="ETH/USDT", agent="news-sentiment",
            prediction_type="sentiment", prediction="bullish",
        )
        db._validate_prediction("pred_001", "went up", is_correct=True)
        db._validate_prediction("pred_002", "was bullish", is_correct=False)

        result = db._get_prediction_track_record()
        self.assertEqual(result["windows"]["global"]["total"], 2)
        self.assertEqual(result["windows"]["global"]["correct"], 1)
        self.assertEqual(result["filters"], {})


class TestFindExpiredPredictions(TestCase):
    """Test finding expired predictions for agent evaluation."""

    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db._record_trade(
            trade_id="trade_001", symbol="BTC/USDT", side="long",
            portfolio_type="futures", entry_price=97000, usd_amount=1000,
        )

    def test_no_expired_predictions(self):
        # Prediction with 72h timeframe, just created → not expired
        db._record_prediction(
            prediction_id="pred_001", trade_id="trade_001",
            symbol="BTC/USDT", agent="technical-analyst",
            prediction_type="price_direction", prediction="up",
            timeframe_hours=72,
        )
        result = db._find_expired_predictions()
        self.assertEqual(result["total_expired"], 0)

    def test_finds_expired_prediction(self):
        # Insert prediction with backdated created_at so it's expired
        conn = db._init_db()
        conn.execute(
            """INSERT INTO predictions
               (id, trade_id, symbol, agent, prediction_type, prediction,
                target_value, timeframe_hours, confidence, status, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            ("pred_exp", "trade_001", "BTC/USDT", "technical-analyst",
             "price_target", "BTC to $100k", 100000, 24, 0.75, "pending",
             "2025-01-01T00:00:00+00:00"),
        )
        conn.commit()
        conn.close()

        result = db._find_expired_predictions(
            current_prices='{"BTC/USDT": 99000}'
        )
        self.assertEqual(result["total_expired"], 1)
        pred = result["expired_predictions"][0]
        self.assertEqual(pred["prediction_id"], "pred_exp")
        self.assertEqual(pred["current_price"], 99000)
        self.assertEqual(pred["target_value"], 100000)
        self.assertAlmostEqual(pred["price_diff_pct"], -1.0, places=1)

    def test_expired_without_prices(self):
        """Should still find expired predictions even without current prices."""
        conn = db._init_db()
        conn.execute(
            """INSERT INTO predictions
               (id, trade_id, symbol, agent, prediction_type, prediction,
                target_value, timeframe_hours, confidence, status, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            ("pred_exp", "trade_001", "BTC/USDT", "technical-analyst",
             "price_target", "BTC to $100k", 100000, 24, 0.75, "pending",
             "2025-01-01T00:00:00+00:00"),
        )
        conn.commit()
        conn.close()

        result = db._find_expired_predictions()
        self.assertEqual(result["total_expired"], 1)
        pred = result["expired_predictions"][0]
        self.assertNotIn("current_price", pred)

    def test_non_price_predictions_tagged(self):
        """Non-price predictions (no target_value) should be tagged."""
        conn = db._init_db()
        conn.execute(
            """INSERT INTO predictions
               (id, trade_id, symbol, agent, prediction_type, prediction,
                target_value, timeframe_hours, confidence, status, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            ("pred_sentiment", "trade_001", "BTC/USDT", "news-sentiment",
             "sentiment", "No negative catalysts", 0, 48, 0.6, "pending",
             "2025-01-01T00:00:00+00:00"),
        )
        conn.commit()
        conn.close()

        result = db._find_expired_predictions()
        self.assertEqual(result["total_expired"], 1)
        pred = result["expired_predictions"][0]
        self.assertFalse(pred["has_price_target"])

    def test_ignores_already_validated(self):
        """Should not include already validated predictions."""
        conn = db._init_db()
        conn.execute(
            """INSERT INTO predictions
               (id, trade_id, symbol, agent, prediction_type, prediction,
                target_value, timeframe_hours, confidence, status, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            ("pred_done", "trade_001", "BTC/USDT", "technical-analyst",
             "price_target", "BTC to $100k", 100000, 24, 0.75, "correct",
             "2025-01-01T00:00:00+00:00"),
        )
        conn.commit()
        conn.close()

        result = db._find_expired_predictions()
        self.assertEqual(result["total_expired"], 0)

    def test_ignores_no_timeframe(self):
        """Predictions without timeframe_hours should not expire."""
        db._record_prediction(
            prediction_id="pred_notime", trade_id="trade_001",
            symbol="BTC/USDT", agent="technical-analyst",
            prediction_type="general", prediction="BTC bullish long-term",
            timeframe_hours=0,
        )
        result = db._find_expired_predictions()
        self.assertEqual(result["total_expired"], 0)


class TestUpdateTrade(TestCase):
    """Test trade modification (SL/TP updates) and modification history."""

    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db._record_trade(
            trade_id="mod_001",
            symbol="BTC/USDT",
            side="long",
            portfolio_type="futures",
            entry_price=97000,
            usd_amount=1000,
            leverage=3,
            stop_loss=94500,
            take_profit=103200,
        )

    def test_update_stop_loss(self):
        result = db._update_trade("mod_001", stop_loss=95000, notes="Tightening SL after support confirmed")
        self.assertEqual(result["status"], "success")
        self.assertEqual(len(result["changes"]), 1)
        self.assertEqual(result["changes"][0]["field"], "stop_loss")
        self.assertEqual(result["changes"][0]["old"], 94500)
        self.assertEqual(result["changes"][0]["new"], 95000)
        # Verify trade updated in DB
        trades = db._query_trades(symbol="BTC/USDT")
        self.assertEqual(trades["trades"][0]["stop_loss"], 95000)

    def test_update_take_profit(self):
        result = db._update_trade("mod_001", take_profit=105000, notes="Extending TP on momentum")
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["changes"][0]["field"], "take_profit")
        self.assertEqual(result["changes"][0]["old"], 103200)
        self.assertEqual(result["changes"][0]["new"], 105000)

    def test_update_both_sl_tp(self):
        result = db._update_trade("mod_001", stop_loss=95500, take_profit=106000, notes="Trailing stop adjustment")
        self.assertEqual(result["status"], "success")
        self.assertEqual(len(result["changes"]), 2)
        fields = [c["field"] for c in result["changes"]]
        self.assertIn("stop_loss", fields)
        self.assertIn("take_profit", fields)

    def test_update_no_change_needed(self):
        """Passing the same value should report no changes."""
        result = db._update_trade("mod_001", stop_loss=94500)
        self.assertEqual(result["status"], "success")
        self.assertIn("No changes", result["message"])

    def test_update_nonexistent_trade(self):
        result = db._update_trade("nonexistent")
        self.assertEqual(result["status"], "error")

    def test_update_closed_trade_fails(self):
        db._close_trade("mod_001", exit_price=100000, close_reason="TP hit")
        result = db._update_trade("mod_001", stop_loss=96000)
        self.assertEqual(result["status"], "error")

    def test_modification_history_recorded(self):
        db._update_trade("mod_001", stop_loss=95000, notes="First adjustment")
        db._update_trade("mod_001", stop_loss=95500, notes="Second adjustment")
        mods = db._get_trade_modifications("mod_001")
        self.assertEqual(mods["status"], "success")
        self.assertEqual(len(mods["modifications"]), 2)
        # Most recent first
        self.assertEqual(mods["modifications"][0]["new_value"], 95500)
        self.assertEqual(mods["modifications"][1]["new_value"], 95000)

    def test_modification_history_all_trades(self):
        db._record_trade(
            trade_id="mod_002", symbol="ETH/USDT", side="long",
            portfolio_type="spot", entry_price=3200, usd_amount=500,
            stop_loss=3000, take_profit=3600,
        )
        db._update_trade("mod_001", stop_loss=95000, notes="BTC SL")
        db._update_trade("mod_002", take_profit=3800, notes="ETH TP")
        mods = db._get_trade_modifications()
        self.assertEqual(len(mods["modifications"]), 2)

    def test_modification_stores_reason(self):
        db._update_trade("mod_001", stop_loss=95200, notes="Risk-specialist recommended tighter SL due to volatility spike")
        mods = db._get_trade_modifications("mod_001")
        self.assertIn("volatility spike", mods["modifications"][0]["reason"])


if __name__ == "__main__":
    main()
