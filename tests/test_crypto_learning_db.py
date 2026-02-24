"""
Tests for crypto_learning_db MCP server.

Covers: schema creation, trade CRUD, predictions, scorecards,
patterns, summaries, migration, and meta-learning queries.
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
            "agent_scorecards", "patterns", "portfolio_state",
            "predictions", "scorecard_history", "summaries", "trades",
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

    def test_default_agent_scorecards(self):
        conn = db._init_db()
        rows = conn.execute("SELECT agent FROM agent_scorecards ORDER BY agent").fetchall()
        conn.close()
        agents = [r[0] for r in rows]
        self.assertIn("market-monitor", agents)
        self.assertIn("technical-analyst", agents)
        self.assertIn("news-sentiment", agents)
        self.assertIn("risk-specialist", agents)
        self.assertIn("portfolio-manager", agents)

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
        )
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["result"], "correct")
        self.assertGreater(result["new_confidence_adjustment"], 1.0)

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
        )
        self.assertEqual(result["result"], "incorrect")
        self.assertLess(result["new_confidence_adjustment"], 1.0)

    def test_validate_nonexistent_prediction(self):
        result = db._validate_prediction(
            prediction_id="pred_999",
            actual_outcome="doesn't matter",
            is_correct=True,
        )
        self.assertEqual(result["status"], "error")


class TestScorecardsAndMetaLearning(TestCase):
    """Test scorecard updates and meta-learning queries."""

    def setUp(self):
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        # Setup: a trade with predictions
        db._record_trade(
            trade_id="trade_001", symbol="BTC/USDT", side="long",
            portfolio_type="futures", entry_price=97000, usd_amount=1000,
            strategy_type="swing",
        )

    def test_get_agent_scorecards_initial(self):
        result = db._get_agent_scorecards()
        self.assertEqual(result["status"], "success")
        self.assertEqual(len(result["scorecards"]), 5)
        for sc in result["scorecards"]:
            self.assertEqual(sc["confidence_adjustment"], 1.0)

    def test_scorecard_updates_on_validation(self):
        db._record_prediction(
            prediction_id="pred_001", trade_id="trade_001",
            symbol="BTC/USDT", agent="technical-analyst",
            prediction_type="price_direction",
            prediction="BTC up",
        )
        db._validate_prediction("pred_001", "BTC went up", is_correct=True)
        result = db._get_agent_scorecards()
        ta = next(s for s in result["scorecards"] if s["agent"] == "technical-analyst")
        self.assertEqual(ta["total_signals"], 1)
        self.assertEqual(ta["accurate_signals"], 1)
        self.assertEqual(ta["accuracy_rate"], 1.0)
        self.assertEqual(ta["confidence_adjustment"], 1.05)
        self.assertEqual(ta["streak"], 1)

    def test_scorecard_streak_resets_on_miss(self):
        db._record_prediction(
            prediction_id="pred_001", trade_id="trade_001",
            symbol="BTC/USDT", agent="technical-analyst",
            prediction_type="price_direction", prediction="up",
        )
        db._record_prediction(
            prediction_id="pred_002", trade_id="trade_001",
            symbol="BTC/USDT", agent="technical-analyst",
            prediction_type="support", prediction="holds $96k",
        )
        db._validate_prediction("pred_001", "went up", is_correct=True)
        db._validate_prediction("pred_002", "broke $96k", is_correct=False)
        result = db._get_agent_scorecards()
        ta = next(s for s in result["scorecards"] if s["agent"] == "technical-analyst")
        self.assertEqual(ta["streak"], -1)
        self.assertEqual(ta["total_signals"], 2)
        self.assertEqual(ta["accurate_signals"], 1)

    def test_confidence_adjustment_bounds(self):
        """Confidence should stay within 0.5-1.5 bounds."""
        # 10 consecutive misses
        for i in range(10):
            db._record_prediction(
                prediction_id=f"pred_{i:03d}", trade_id="trade_001",
                symbol="BTC/USDT", agent="technical-analyst",
                prediction_type="test", prediction="wrong",
            )
            db._validate_prediction(f"pred_{i:03d}", "actual", is_correct=False)

        result = db._get_agent_scorecards()
        ta = next(s for s in result["scorecards"] if s["agent"] == "technical-analyst")
        self.assertGreaterEqual(ta["confidence_adjustment"], 0.5)

        # Reset and do 20 consecutive hits
        if db.DB_PATH.exists():
            db.DB_PATH.unlink()
        db._record_trade(
            trade_id="trade_001", symbol="BTC/USDT", side="long",
            portfolio_type="futures", entry_price=97000, usd_amount=1000,
        )
        for i in range(20):
            db._record_prediction(
                prediction_id=f"pred_{i:03d}", trade_id="trade_001",
                symbol="BTC/USDT", agent="technical-analyst",
                prediction_type="test", prediction="right",
            )
            db._validate_prediction(f"pred_{i:03d}", "actual", is_correct=True)

        result = db._get_agent_scorecards()
        ta = next(s for s in result["scorecards"] if s["agent"] == "technical-analyst")
        self.assertLessEqual(ta["confidence_adjustment"], 1.5)

    def test_get_agent_performance_contextual(self):
        """Test meta-learning: accuracy filtered by symbol and strategy."""
        db._record_prediction(
            prediction_id="pred_001", trade_id="trade_001",
            symbol="BTC/USDT", agent="technical-analyst",
            prediction_type="price_direction", prediction="up",
        )
        db._validate_prediction("pred_001", "went up", is_correct=True)

        # Query for BTC + swing (should find 1)
        result = db._get_agent_performance(
            agent="technical-analyst", symbol="BTC/USDT", strategy_type="swing"
        )
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["total_predictions"], 1)
        self.assertEqual(result["contextual_accuracy"], 1.0)

        # Query for ETH (should find 0)
        result = db._get_agent_performance(
            agent="technical-analyst", symbol="ETH/USDT"
        )
        self.assertEqual(result["total_predictions"], 0)
        self.assertEqual(result["contextual_accuracy"], 0)


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
        scorecards = {
            "scorecards": {
                "market-monitor": {
                    "total_signals": 5, "accurate_signals": 3,
                    "accuracy_rate": 0.6, "confidence_adjustment": 1.1,
                    "streak": 2, "last_updated": "2026-02-15T10:00:00Z",
                },
                "technical-analyst": {
                    "total_signals": 0, "accurate_signals": 0,
                    "accuracy_rate": 0, "confidence_adjustment": 1.0,
                    "streak": 0, "last_updated": None,
                },
            },
            "history": [
                {
                    "timestamp": "2026-02-15T10:00:00Z", "trade_id": "trade_000",
                    "agent": "market-monitor", "prediction_correct": True,
                    "new_accuracy": 0.6, "new_confidence_adjustment": 1.1,
                },
            ],
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
        Path(self.json_dir, "agent-scorecards.json").write_text(json.dumps(scorecards))
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

        sc = db._get_agent_scorecards()
        mm = next(s for s in sc["scorecards"] if s["agent"] == "market-monitor")
        self.assertEqual(mm["total_signals"], 5)
        self.assertEqual(mm["confidence_adjustment"], 1.1)

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


if __name__ == "__main__":
    main()
