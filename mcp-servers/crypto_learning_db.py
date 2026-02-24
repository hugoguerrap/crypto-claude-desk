#!/usr/bin/env python3
"""
Crypto Learning DB MCP Server - SQLite-backed cognitive memory.

Replaces unbounded JSON files (portfolio.json, predictions.json,
agent-scorecards.json, patterns.json) with a SQLite database that
supports filtered queries, automatic archival, and summary generation.

This solves the context-window growth problem: agents query only
what they need instead of loading entire files into context.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DB_DIR = Path(os.environ.get(
    "CRYPTO_DB_DIR",
    Path(__file__).resolve().parent.parent / "data" / "db",
))
DB_PATH = DB_DIR / "learning.db"

mcp = FastMCP("crypto-learning-db")

# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_conn() -> sqlite3.Connection:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS trades (
        id              TEXT PRIMARY KEY,
        symbol          TEXT NOT NULL,
        side            TEXT NOT NULL CHECK(side IN ('long','short')),
        portfolio_type  TEXT NOT NULL CHECK(portfolio_type IN ('spot','futures')),
        entry_price     REAL NOT NULL,
        exit_price      REAL,
        usd_amount      REAL NOT NULL,
        leverage        REAL NOT NULL DEFAULT 1,
        stop_loss       REAL,
        take_profit     REAL,
        strategy_type   TEXT,
        opened_at       TEXT NOT NULL,
        closed_at       TEXT,
        close_reason    TEXT,
        pnl_usd         REAL,
        pnl_percent     REAL,
        result          TEXT CHECK(result IN ('win','loss',NULL)),
        status          TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','closed')),
        reasoning       TEXT,
        key_assumptions TEXT,  -- JSON array
        agent_signals   TEXT,  -- JSON object
        learning        TEXT,  -- JSON object
        created_at      TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
    CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
    CREATE INDEX IF NOT EXISTS idx_trades_strategy ON trades(strategy_type);

    CREATE TABLE IF NOT EXISTS predictions (
        id              TEXT PRIMARY KEY,
        trade_id        TEXT NOT NULL,
        symbol          TEXT NOT NULL,
        agent           TEXT NOT NULL,
        prediction_type TEXT NOT NULL,
        prediction      TEXT NOT NULL,
        target_value    REAL,
        timeframe_hours REAL,
        confidence      REAL,
        status          TEXT NOT NULL DEFAULT 'pending'
                        CHECK(status IN ('pending','correct','incorrect','expired')),
        actual_outcome  TEXT,
        error_margin    REAL,
        evaluation      TEXT,  -- agent's NL analysis of how close the prediction was
        created_at      TEXT NOT NULL DEFAULT (datetime('now')),
        validated_at    TEXT,
        FOREIGN KEY (trade_id) REFERENCES trades(id)
    );

    CREATE INDEX IF NOT EXISTS idx_predictions_trade ON predictions(trade_id);
    CREATE INDEX IF NOT EXISTS idx_predictions_agent ON predictions(agent);
    CREATE INDEX IF NOT EXISTS idx_predictions_status ON predictions(status);

    CREATE TABLE IF NOT EXISTS patterns (
        name            TEXT PRIMARY KEY,
        conditions      TEXT,  -- JSON array
        occurrences     INTEGER NOT NULL DEFAULT 0,
        wins            INTEGER NOT NULL DEFAULT 0,
        losses          INTEGER NOT NULL DEFAULT 0,
        win_rate        REAL NOT NULL DEFAULT 0,
        avg_pnl_percent REAL NOT NULL DEFAULT 0,
        first_seen      TEXT,
        last_seen       TEXT,
        recommendation  TEXT CHECK(recommendation IN ('SEEK','NEUTRAL','AVOID')),
        notes           TEXT
    );

    CREATE TABLE IF NOT EXISTS summaries (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        period          TEXT NOT NULL,       -- e.g. '2026-Q1', '2026-02'
        summary_type    TEXT NOT NULL,       -- 'quarterly', 'monthly', 'agent_performance'
        content         TEXT NOT NULL,       -- markdown
        created_at      TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS trade_modifications (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        trade_id        TEXT NOT NULL,
        field           TEXT NOT NULL,
        old_value       REAL,
        new_value       REAL,
        reason          TEXT,  -- NL explanation for the change
        created_at      TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (trade_id) REFERENCES trades(id)
    );

    CREATE INDEX IF NOT EXISTS idx_tm_trade ON trade_modifications(trade_id);

    CREATE TABLE IF NOT EXISTS portfolio_state (
        id              INTEGER PRIMARY KEY CHECK(id = 1),
        spot_initial    REAL NOT NULL DEFAULT 10000,
        spot_balance    REAL NOT NULL DEFAULT 10000,
        futures_initial REAL NOT NULL DEFAULT 10000,
        futures_balance REAL NOT NULL DEFAULT 10000,
        currency        TEXT NOT NULL DEFAULT 'USDT',
        total_trades    INTEGER NOT NULL DEFAULT 0,
        wins            INTEGER NOT NULL DEFAULT 0,
        losses          INTEGER NOT NULL DEFAULT 0,
        total_pnl       REAL NOT NULL DEFAULT 0,
        updated_at      TEXT
    );
    """)
    conn.commit()

    # Schema migrations for existing databases.
    for migration in (
        "ALTER TABLE predictions ADD COLUMN evaluation TEXT",
        "DROP TABLE IF EXISTS scorecard_history",
        "DROP TABLE IF EXISTS agent_scorecards",
    ):
        try:
            conn.execute(migration)
            conn.commit()
        except sqlite3.OperationalError:
            pass  # Column/table already exists or already dropped

    # Seed default portfolio state if missing.
    cur = conn.execute("SELECT COUNT(*) FROM portfolio_state")
    if cur.fetchone()[0] == 0:
        conn.execute(
            "INSERT INTO portfolio_state(id) VALUES(1)"
        )
    conn.commit()


def _init_db() -> sqlite3.Connection:
    conn = _get_conn()
    _ensure_schema(conn)
    return conn


def _row_to_dict(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    return dict(row)


def _rows_to_list(rows: list[sqlite3.Row]) -> list[dict]:
    return [dict(r) for r in rows]


# ===================================================================
# CORE FUNCTIONS (called by both MCP tools and tests)
# ===================================================================


def _record_trade(
    trade_id: str,
    symbol: str,
    side: str,
    portfolio_type: str,
    entry_price: float,
    usd_amount: float,
    leverage: float = 1,
    stop_loss: float = 0,
    take_profit: float = 0,
    strategy_type: str = "",
    reasoning: str = "",
    key_assumptions: str = "[]",
    agent_signals: str = "{}",
    learning: str = "{}",
) -> dict:
    conn = _init_db()
    try:
        conn.execute(
            """INSERT INTO trades
               (id, symbol, side, portfolio_type, entry_price, usd_amount,
                leverage, stop_loss, take_profit, strategy_type, opened_at,
                reasoning, key_assumptions, agent_signals, learning, status)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'open')""",
            (trade_id, symbol.upper(), side, portfolio_type, entry_price,
             usd_amount, leverage, stop_loss, take_profit, strategy_type,
             _now_iso(), reasoning, key_assumptions, agent_signals, learning),
        )
        bal_col = "spot_balance" if portfolio_type == "spot" else "futures_balance"
        conn.execute(
            f"UPDATE portfolio_state SET {bal_col} = {bal_col} - ?, "
            "total_trades = total_trades + 1, updated_at = ? WHERE id = 1",
            (usd_amount, _now_iso()),
        )
        conn.commit()
        return {"status": "success", "trade_id": trade_id, "message": f"Trade {trade_id} recorded"}
    except Exception as e:
        conn.rollback()
        return {"status": "error", "error": str(e)}
    finally:
        conn.close()


def _close_trade(
    trade_id: str,
    exit_price: float,
    close_reason: str = "",
) -> dict:
    conn = _init_db()
    try:
        row = conn.execute(
            "SELECT * FROM trades WHERE id = ? AND status = 'open'", (trade_id,)
        ).fetchone()
        if not row:
            return {"status": "error", "error": f"No open trade {trade_id}"}
        t = dict(row)
        entry = t["entry_price"]
        leverage = t["leverage"]
        amount = t["usd_amount"]
        if t["side"] == "long":
            pnl_pct = ((exit_price - entry) / entry) * 100 * leverage
        else:
            pnl_pct = ((entry - exit_price) / entry) * 100 * leverage
        pnl_usd = amount * (pnl_pct / 100)
        result = "win" if pnl_usd >= 0 else "loss"
        now = _now_iso()
        conn.execute(
            """UPDATE trades SET exit_price=?, closed_at=?, close_reason=?,
               pnl_usd=?, pnl_percent=?, result=?, status='closed'
               WHERE id=?""",
            (exit_price, now, close_reason, round(pnl_usd, 2),
             round(pnl_pct, 4), result, trade_id),
        )
        bal_col = "spot_balance" if t["portfolio_type"] == "spot" else "futures_balance"
        win_inc = 1 if result == "win" else 0
        loss_inc = 1 if result == "loss" else 0
        conn.execute(
            f"""UPDATE portfolio_state SET
                {bal_col} = {bal_col} + ? + ?,
                wins = wins + ?, losses = losses + ?,
                total_pnl = total_pnl + ?, updated_at = ?
                WHERE id = 1""",
            (amount, round(pnl_usd, 2), win_inc, loss_inc,
             round(pnl_usd, 2), now),
        )
        conn.commit()
        return {
            "status": "success", "trade_id": trade_id,
            "result": result, "pnl_usd": round(pnl_usd, 2),
            "pnl_percent": round(pnl_pct, 4),
        }
    except Exception as e:
        conn.rollback()
        return {"status": "error", "error": str(e)}
    finally:
        conn.close()


def _update_trade(
    trade_id: str,
    stop_loss: float | None = None,
    take_profit: float | None = None,
    notes: str = "",
) -> dict:
    """Update SL/TP on an open trade. Logs every change with NL reason."""
    conn = _init_db()
    try:
        row = conn.execute(
            "SELECT * FROM trades WHERE id = ? AND status = 'open'", (trade_id,)
        ).fetchone()
        if not row:
            return {"status": "error", "error": f"No open trade {trade_id}"}
        t = dict(row)
        now = _now_iso()
        changes: list[dict] = []

        if stop_loss is not None and stop_loss != t["stop_loss"]:
            conn.execute(
                "INSERT INTO trade_modifications (trade_id, field, old_value, new_value, reason, created_at) VALUES (?,?,?,?,?,?)",
                (trade_id, "stop_loss", t["stop_loss"], stop_loss, notes, now),
            )
            conn.execute(
                "UPDATE trades SET stop_loss = ? WHERE id = ?",
                (stop_loss, trade_id),
            )
            changes.append({"field": "stop_loss", "old": t["stop_loss"], "new": stop_loss})

        if take_profit is not None and take_profit != t["take_profit"]:
            conn.execute(
                "INSERT INTO trade_modifications (trade_id, field, old_value, new_value, reason, created_at) VALUES (?,?,?,?,?,?)",
                (trade_id, "take_profit", t["take_profit"], take_profit, notes, now),
            )
            conn.execute(
                "UPDATE trades SET take_profit = ? WHERE id = ?",
                (take_profit, trade_id),
            )
            changes.append({"field": "take_profit", "old": t["take_profit"], "new": take_profit})

        if not changes:
            return {"status": "success", "trade_id": trade_id, "message": "No changes needed"}

        conn.commit()
        return {
            "status": "success",
            "trade_id": trade_id,
            "changes": changes,
            "reason": notes,
        }
    except Exception as e:
        conn.rollback()
        return {"status": "error", "error": str(e)}
    finally:
        conn.close()


def _get_trade_modifications(trade_id: str = "", limit: int = 20) -> dict:
    """Get modification history for a trade (or all trades)."""
    conn = _init_db()
    try:
        if trade_id:
            rows = conn.execute(
                "SELECT * FROM trade_modifications WHERE trade_id = ? ORDER BY created_at DESC LIMIT ?",
                (trade_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM trade_modifications ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return {"status": "success", "modifications": _rows_to_list(rows)}
    finally:
        conn.close()


def _query_trades(
    symbol: str = "",
    status: str = "",
    strategy_type: str = "",
    result: str = "",
    limit: int = 20,
    offset: int = 0,
) -> dict:
    conn = _init_db()
    try:
        clauses: list[str] = []
        params: list[Any] = []
        if symbol:
            clauses.append("symbol = ?")
            params.append(symbol.upper())
        if status:
            clauses.append("status = ?")
            params.append(status)
        if strategy_type:
            clauses.append("strategy_type = ?")
            params.append(strategy_type)
        if result:
            clauses.append("result = ?")
            params.append(result)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = conn.execute(
            f"SELECT * FROM trades {where} ORDER BY opened_at DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()
        total = conn.execute(
            f"SELECT COUNT(*) FROM trades {where}", params
        ).fetchone()[0]
        return {"status": "success", "trades": _rows_to_list(rows), "total": total}
    finally:
        conn.close()


def _get_portfolio_state() -> dict:
    conn = _init_db()
    try:
        state = _row_to_dict(
            conn.execute("SELECT * FROM portfolio_state WHERE id = 1").fetchone()
        )
        open_count = conn.execute(
            "SELECT COUNT(*) FROM trades WHERE status = 'open'"
        ).fetchone()[0]
        open_trades = _rows_to_list(
            conn.execute(
                "SELECT * FROM trades WHERE status = 'open' ORDER BY opened_at DESC"
            ).fetchall()
        )
        return {
            "status": "success",
            "portfolio": state,
            "open_trades_count": open_count,
            "open_trades": open_trades,
        }
    finally:
        conn.close()


def _record_prediction(
    prediction_id: str,
    trade_id: str,
    symbol: str,
    agent: str,
    prediction_type: str,
    prediction: str,
    target_value: float = 0,
    timeframe_hours: float = 0,
    confidence: float = 0.5,
) -> dict:
    conn = _init_db()
    try:
        conn.execute(
            """INSERT INTO predictions
               (id, trade_id, symbol, agent, prediction_type, prediction,
                target_value, timeframe_hours, confidence, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (prediction_id, trade_id, symbol.upper(), agent, prediction_type,
             prediction, target_value, timeframe_hours, confidence, _now_iso()),
        )
        conn.commit()
        return {"status": "success", "prediction_id": prediction_id}
    except Exception as e:
        conn.rollback()
        return {"status": "error", "error": str(e)}
    finally:
        conn.close()


def _validate_prediction(
    prediction_id: str,
    actual_outcome: str,
    is_correct: bool,
    error_margin: float = 0,
    evaluation: str = "",
) -> dict:
    """Validate a prediction. Pure recording — no formula scoring.

    The agent provides:
    - actual_outcome: what happened in the market
    - is_correct: simple boolean for counting
    - error_margin: numerical difference if applicable
    - evaluation: agent's NL reasoning about how close the prediction was,
      why it worked/failed, and what we can learn from it
    """
    conn = _init_db()
    try:
        pred = _row_to_dict(
            conn.execute("SELECT * FROM predictions WHERE id = ?", (prediction_id,)).fetchone()
        )
        if not pred:
            return {"status": "error", "error": f"No prediction {prediction_id}"}
        if pred["status"] != "pending":
            return {"status": "error", "error": f"Prediction {prediction_id} already validated as '{pred['status']}'"}

        new_status = "correct" if is_correct else "incorrect"
        now = _now_iso()
        conn.execute(
            """UPDATE predictions SET status=?, actual_outcome=?,
               error_margin=?, evaluation=?, validated_at=? WHERE id=?""",
            (new_status, actual_outcome, error_margin, evaluation, now,
             prediction_id),
        )

        conn.commit()
        return {
            "status": "success",
            "prediction_id": prediction_id,
            "agent": pred["agent"],
            "result": new_status,
        }
    except Exception as e:
        conn.rollback()
        return {"status": "error", "error": str(e)}
    finally:
        conn.close()


def _query_predictions(
    trade_id: str = "",
    agent: str = "",
    status: str = "",
    symbol: str = "",
    limit: int = 20,
) -> dict:
    conn = _init_db()
    try:
        clauses: list[str] = []
        params: list[Any] = []
        if trade_id:
            clauses.append("trade_id = ?")
            params.append(trade_id)
        if agent:
            clauses.append("agent = ?")
            params.append(agent)
        if status:
            clauses.append("status = ?")
            params.append(status)
        if symbol:
            clauses.append("symbol = ?")
            params.append(symbol.upper())
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = conn.execute(
            f"SELECT * FROM predictions {where} ORDER BY created_at DESC LIMIT ?",
            params + [limit],
        ).fetchall()
        return {"status": "success", "predictions": _rows_to_list(rows)}
    finally:
        conn.close()


def _upsert_pattern(
    name: str,
    conditions: str = "[]",
    is_win: bool = True,
    pnl_percent: float = 0,
    notes: str = "",
) -> dict:
    conn = _init_db()
    try:
        existing = _row_to_dict(
            conn.execute("SELECT * FROM patterns WHERE name = ?", (name,)).fetchone()
        )
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if existing:
            occ = existing["occurrences"] + 1
            wins = existing["wins"] + (1 if is_win else 0)
            losses = existing["losses"] + (0 if is_win else 1)
            wr = wins / occ if occ > 0 else 0
            old_avg = existing["avg_pnl_percent"] or 0
            avg_pnl = ((old_avg * existing["occurrences"]) + pnl_percent) / occ
            rec = "SEEK" if wr > 0.6 else ("NEUTRAL" if wr >= 0.4 else "AVOID")
            conn.execute(
                """UPDATE patterns SET occurrences=?, wins=?, losses=?,
                   win_rate=?, avg_pnl_percent=?, last_seen=?,
                   recommendation=?, notes=CASE WHEN ?='' THEN notes ELSE ? END
                   WHERE name=?""",
                (occ, wins, losses, round(wr, 4), round(avg_pnl, 2),
                 now, rec, notes, notes, name),
            )
            if conditions != "[]":
                conn.execute(
                    "UPDATE patterns SET conditions = ? WHERE name = ?",
                    (conditions, name),
                )
        else:
            wr = 1.0 if is_win else 0.0
            rec = "SEEK" if is_win else "AVOID"
            conn.execute(
                """INSERT INTO patterns
                   (name, conditions, occurrences, wins, losses, win_rate,
                    avg_pnl_percent, first_seen, last_seen, recommendation, notes)
                   VALUES (?,?,1,?,?,?,?,?,?,?,?)""",
                (name, conditions, 1 if is_win else 0, 0 if is_win else 1,
                 wr, pnl_percent, now, now, rec,
                 notes or "Initial observation - need more data"),
            )
        conn.commit()
        return {"status": "success", "pattern": name, "action": "updated" if existing else "created"}
    except Exception as e:
        conn.rollback()
        return {"status": "error", "error": str(e)}
    finally:
        conn.close()


def _query_patterns(
    symbol: str = "",
    min_win_rate: float = 0,
    min_occurrences: int = 0,
    recommendation: str = "",
    limit: int = 10,
) -> dict:
    conn = _init_db()
    try:
        clauses: list[str] = []
        params: list[Any] = []
        if symbol:
            clauses.append("conditions LIKE ?")
            params.append(f"%{symbol.upper()}%")
        if min_win_rate > 0:
            clauses.append("win_rate >= ?")
            params.append(min_win_rate)
        if min_occurrences > 0:
            clauses.append("occurrences >= ?")
            params.append(min_occurrences)
        if recommendation:
            clauses.append("recommendation = ?")
            params.append(recommendation.upper())
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = conn.execute(
            f"SELECT * FROM patterns {where} ORDER BY win_rate DESC, occurrences DESC LIMIT ?",
            params + [limit],
        ).fetchall()
        return {"status": "success", "patterns": _rows_to_list(rows)}
    finally:
        conn.close()


def _generate_summary(period: str = "", summary_type: str = "monthly") -> dict:
    conn = _init_db()
    try:
        now = datetime.now(timezone.utc)
        if not period:
            if summary_type == "quarterly":
                q = (now.month - 1) // 3 + 1
                period = f"{now.year}-Q{q}"
            else:
                period = now.strftime("%Y-%m")

        # Gather stats for the period
        if summary_type == "quarterly":
            year, qn = period.split("-Q")
            q = int(qn)
            start_month = (q - 1) * 3 + 1
            end_month = q * 3
            date_start = f"{year}-{start_month:02d}-01"
            if end_month == 12:
                date_end = f"{int(year)+1}-01-01"
            else:
                date_end = f"{year}-{end_month+1:02d}-01"
        else:
            date_start = f"{period}-01"
            parts = period.split("-")
            y, m = int(parts[0]), int(parts[1])
            if m == 12:
                date_end = f"{y+1}-01-01"
            else:
                date_end = f"{y}-{m+1:02d}-01"

        trades = _rows_to_list(conn.execute(
            """SELECT * FROM trades WHERE status='closed'
               AND closed_at >= ? AND closed_at < ?
               ORDER BY closed_at""",
            (date_start, date_end),
        ).fetchall())

        total = len(trades)
        wins = sum(1 for t in trades if t["result"] == "win")
        losses = total - wins
        total_pnl = sum(t["pnl_usd"] or 0 for t in trades)
        win_rate = wins / total if total > 0 else 0

        # Agent performance in period (from predictions directly)
        agent_stats = _rows_to_list(conn.execute(
            """SELECT agent, COUNT(*) as total,
                      SUM(CASE WHEN status='correct' THEN 1 ELSE 0 END) as correct
               FROM predictions
               WHERE status IN ('correct','incorrect')
                 AND validated_at >= ? AND validated_at < ?
               GROUP BY agent""",
            (date_start, date_end),
        ).fetchall())

        # Top patterns
        top_patterns = _rows_to_list(conn.execute(
            """SELECT name, occurrences, win_rate, recommendation
               FROM patterns WHERE last_seen >= ? AND last_seen < ?
               ORDER BY occurrences DESC LIMIT 5""",
            (date_start, date_end),
        ).fetchall())

        # Strategy breakdown
        strat_stats = _rows_to_list(conn.execute(
            """SELECT strategy_type,
                      COUNT(*) as total,
                      SUM(CASE WHEN result='win' THEN 1 ELSE 0 END) as wins,
                      ROUND(AVG(pnl_percent),2) as avg_pnl
               FROM trades WHERE status='closed'
               AND closed_at >= ? AND closed_at < ?
               GROUP BY strategy_type""",
            (date_start, date_end),
        ).fetchall())

        # Build markdown summary
        lines = [
            f"# Trading Summary: {period} ({summary_type})",
            "",
            f"**Total trades:** {total} | **Wins:** {wins} | "
            f"**Losses:** {losses} | **Win Rate:** {win_rate:.0%}",
            f"**Total PnL:** ${total_pnl:+,.2f}",
            "",
            "## Agent Performance",
            "| Agent | Predictions | Correct | Accuracy |",
            "|-------|------------|---------|----------|",
        ]
        for a in agent_stats:
            acc = a["correct"] / a["total"] if a["total"] > 0 else 0
            lines.append(
                f"| {a['agent']} | {a['total']} | {a['correct']} | {acc:.0%} |"
            )
        lines += ["", "## Top Patterns"]
        for p in top_patterns:
            lines.append(
                f"- **{p['name']}**: {p['occurrences']} occurrences, "
                f"{p['win_rate']:.0%} win rate -> {p['recommendation']}"
            )
        lines += ["", "## Strategy Breakdown"]
        for s in strat_stats:
            lines.append(
                f"- **{s['strategy_type'] or 'unknown'}**: {s['total']} trades, "
                f"{s['wins']} wins, avg PnL {s['avg_pnl']}%"
            )

        content = "\n".join(lines)

        # Store summary
        conn.execute(
            "DELETE FROM summaries WHERE period = ? AND summary_type = ?",
            (period, summary_type),
        )
        conn.execute(
            """INSERT INTO summaries (period, summary_type, content, created_at)
               VALUES (?,?,?,?)""",
            (period, summary_type, content, _now_iso()),
        )
        conn.commit()
        return {"status": "success", "period": period, "summary": content}
    except Exception as e:
        conn.rollback()
        return {"status": "error", "error": str(e)}
    finally:
        conn.close()


def _get_summary(period: str = "", summary_type: str = "monthly") -> dict:
    conn = _init_db()
    try:
        if not period:
            row = conn.execute(
                "SELECT * FROM summaries WHERE summary_type = ? ORDER BY created_at DESC LIMIT 1",
                (summary_type,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM summaries WHERE period = ? AND summary_type = ?",
                (period, summary_type),
            ).fetchone()
        if not row:
            return {"status": "success", "summary": None, "message": "No summary found"}
        return {"status": "success", "summary": _row_to_dict(row)}
    finally:
        conn.close()


def _get_trade_stats(symbol: str = "", strategy_type: str = "") -> dict:
    conn = _init_db()
    try:
        clauses = ["status = 'closed'"]
        params: list[Any] = []
        if symbol:
            clauses.append("symbol = ?")
            params.append(symbol.upper())
        if strategy_type:
            clauses.append("strategy_type = ?")
            params.append(strategy_type)
        where = " AND ".join(clauses)

        row = conn.execute(
            f"""SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN result='win' THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN result='loss' THEN 1 ELSE 0 END) as losses,
                    ROUND(AVG(pnl_percent),2) as avg_pnl_pct,
                    ROUND(SUM(pnl_usd),2) as total_pnl,
                    ROUND(AVG(CASE WHEN result='win' THEN pnl_percent END),2) as avg_win_pct,
                    ROUND(AVG(CASE WHEN result='loss' THEN pnl_percent END),2) as avg_loss_pct
                FROM trades WHERE {where}""",
            params,
        ).fetchone()
        stats = _row_to_dict(row) if row else {}
        total = stats.get("total", 0) or 0
        wins = stats.get("wins", 0) or 0
        stats["win_rate"] = round(wins / total, 4) if total > 0 else 0
        return {"status": "success", "stats": stats}
    finally:
        conn.close()


def _migrate_from_json(json_dir: str = "") -> dict:
    if not json_dir:
        json_dir = str(Path(__file__).resolve().parent.parent / "data" / "trades")
    json_path = Path(json_dir)
    conn = _init_db()
    migrated = {"trades": 0, "predictions": 0, "patterns": 0}
    try:
        # Portfolio / trades
        pf = json_path / "portfolio.json"
        if not pf.exists():
            pf = json_path / "portfolio.json.example"
        if pf.exists():
            data = json.loads(pf.read_text())
            portfolios = data.get("portfolios", {})
            spot = portfolios.get("spot", {})
            futures = portfolios.get("futures", {})
            stats = data.get("stats", {})
            conn.execute(
                """UPDATE portfolio_state SET
                   spot_initial=?, spot_balance=?,
                   futures_initial=?, futures_balance=?,
                   total_trades=?, wins=?, losses=?, total_pnl=?, updated_at=?
                   WHERE id=1""",
                (spot.get("initial_balance", 10000), spot.get("current_balance", 10000),
                 futures.get("initial_balance", 10000), futures.get("current_balance", 10000),
                 stats.get("total_trades", 0), stats.get("wins", 0),
                 stats.get("losses", 0), stats.get("total_pnl", 0), _now_iso()),
            )
            for t in data.get("open_trades", []) + data.get("closed_trades", []):
                status = "closed" if t.get("closed_at") else "open"
                try:
                    conn.execute(
                        """INSERT OR IGNORE INTO trades
                           (id, symbol, side, portfolio_type, entry_price, exit_price,
                            usd_amount, leverage, stop_loss, take_profit, strategy_type,
                            opened_at, closed_at, close_reason, pnl_usd, pnl_percent,
                            result, status, reasoning, key_assumptions, agent_signals, learning)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (t.get("id"), t.get("symbol"), t.get("side"),
                         t.get("portfolio_type", "spot"), t.get("entry_price"),
                         t.get("exit_price"), t.get("usd_amount"),
                         t.get("leverage", 1), t.get("stop_loss"),
                         t.get("take_profit"), t.get("strategy_type"),
                         t.get("opened_at", _now_iso()), t.get("closed_at"),
                         t.get("close_reason"), t.get("pnl_usd"),
                         t.get("pnl_percent"), t.get("result"), status,
                         t.get("reasoning"),
                         json.dumps(t.get("key_assumptions", [])),
                         json.dumps(t.get("agent_signals", {})),
                         json.dumps(t.get("learning", {}))),
                    )
                    migrated["trades"] += 1
                except sqlite3.IntegrityError:
                    pass

        # Predictions
        pred_file = json_path / "predictions.json"
        if not pred_file.exists():
            pred_file = json_path / "predictions.json.example"
        if pred_file.exists():
            data = json.loads(pred_file.read_text())
            for p in data.get("predictions", []):
                try:
                    conn.execute(
                        """INSERT OR IGNORE INTO predictions
                           (id, trade_id, symbol, agent, prediction_type, prediction,
                            target_value, timeframe_hours, confidence, status,
                            actual_outcome, error_margin, created_at, validated_at)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (p.get("id"), p.get("trade_id"), p.get("symbol"),
                         p.get("agent"), p.get("prediction_type"), p.get("prediction"),
                         p.get("target_value"), p.get("timeframe_hours"),
                         p.get("confidence"), p.get("status", "pending"),
                         p.get("actual_outcome"), p.get("error_margin"),
                         p.get("created_at", _now_iso()), p.get("validated_at")),
                    )
                    migrated["predictions"] += 1
                except sqlite3.IntegrityError:
                    pass

        # Patterns
        pat_file = json_path / "patterns.json"
        if not pat_file.exists():
            pat_file = json_path / "patterns.json.example"
        if pat_file.exists():
            data = json.loads(pat_file.read_text())
            for p in data.get("patterns", []):
                try:
                    conn.execute(
                        """INSERT OR IGNORE INTO patterns
                           (name, conditions, occurrences, wins, losses, win_rate,
                            avg_pnl_percent, first_seen, last_seen, recommendation, notes)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                        (p.get("name"), json.dumps(p.get("conditions", [])),
                         p.get("occurrences", 0), p.get("wins", 0),
                         p.get("losses", 0), p.get("win_rate", 0),
                         p.get("avg_pnl_percent", 0), p.get("first_seen"),
                         p.get("last_seen"), p.get("recommendation"),
                         p.get("notes")),
                    )
                    migrated["patterns"] += 1
                except sqlite3.IntegrityError:
                    pass

        conn.commit()
        return {"status": "success", "migrated": migrated}
    except Exception as e:
        conn.rollback()
        return {"status": "error", "error": str(e)}
    finally:
        conn.close()


def _get_prediction_track_record(
    symbol: str = "",
    strategy_type: str = "",
    prediction_type: str = "",
    agent: str = "",
    days_windows: str = "[7,30,90]",
    include_evaluations: int = 5,
) -> dict:
    """Prediction-centric track record. Queries predictions JOIN trades directly.

    Replaces the old agent-centric get_agent_scorecards, get_recency_scores,
    and get_agent_performance. The key shift: agent is a FILTER, not the
    primary key. The question is "how has this type of setup performed?"
    not "how much do I trust this agent?"

    Args:
        symbol: Filter by symbol (e.g., "BTC/USDT")
        strategy_type: Filter by strategy (e.g., "swing", "breakout")
        prediction_type: Filter by prediction type (e.g., "price_direction")
        agent: Filter by agent (optional — agent is ONE filter, not the key)
        days_windows: JSON array of day windows for time-bucketed accuracy
        include_evaluations: Number of recent NL evaluations to include
    """
    conn = _init_db()
    try:
        windows = json.loads(days_windows) if days_windows else [7, 30, 90]

        # Build base WHERE clause
        base_clauses: list[str] = ["p.status IN ('correct','incorrect')"]
        base_params: list[Any] = []
        if symbol:
            base_clauses.append("p.symbol = ?")
            base_params.append(symbol.upper())
        if strategy_type:
            base_clauses.append("t.strategy_type = ?")
            base_params.append(strategy_type)
        if prediction_type:
            base_clauses.append("p.prediction_type = ?")
            base_params.append(prediction_type)
        if agent:
            base_clauses.append("p.agent = ?")
            base_params.append(agent)

        base_where = " AND ".join(base_clauses)

        # Time-windowed accuracy
        windows_data: dict[str, Any] = {}
        for days in windows:
            r = conn.execute(
                f"""SELECT COUNT(*) as total,
                           SUM(CASE WHEN p.status='correct' THEN 1 ELSE 0 END) as correct
                    FROM predictions p
                    LEFT JOIN trades t ON p.trade_id = t.id
                    WHERE {base_where}
                      AND p.validated_at >= datetime('now', ?)""",
                base_params + [f"-{days} days"],
            ).fetchone()
            total = r[0] or 0
            correct = r[1] or 0
            windows_data[f"{days}d"] = {
                "total": total,
                "correct": correct,
                "accuracy": round(correct / total, 4) if total > 0 else None,
            }

        # Global (all-time)
        r = conn.execute(
            f"""SELECT COUNT(*) as total,
                       SUM(CASE WHEN p.status='correct' THEN 1 ELSE 0 END) as correct
                FROM predictions p
                LEFT JOIN trades t ON p.trade_id = t.id
                WHERE {base_where}""",
            base_params,
        ).fetchone()
        total_all = r[0] or 0
        correct_all = r[1] or 0
        windows_data["global"] = {
            "total": total_all,
            "correct": correct_all,
            "accuracy": round(correct_all / total_all, 4) if total_all > 0 else None,
        }

        # Recent NL evaluations for context
        if include_evaluations > 0:
            evals = _rows_to_list(conn.execute(
                f"""SELECT p.id, p.symbol, p.agent, p.prediction_type,
                           p.prediction, p.actual_outcome, p.evaluation,
                           p.status, p.error_margin, p.validated_at,
                           t.strategy_type, t.result as trade_result
                    FROM predictions p
                    LEFT JOIN trades t ON p.trade_id = t.id
                    WHERE {base_where}
                          AND p.evaluation IS NOT NULL AND p.evaluation != ''
                    ORDER BY p.validated_at DESC LIMIT ?""",
                base_params + [include_evaluations],
            ).fetchall())
            windows_data["recent_evaluations"] = evals

        filters = {}
        if symbol:
            filters["symbol"] = symbol
        if strategy_type:
            filters["strategy_type"] = strategy_type
        if prediction_type:
            filters["prediction_type"] = prediction_type
        if agent:
            filters["agent"] = agent

        return {
            "status": "success",
            "filters": filters,
            "windows": windows_data,
        }
    finally:
        conn.close()


def _find_expired_predictions(current_prices: str = "{}") -> dict:
    """Find predictions past their timeframe and return context for agent evaluation.
    Does NOT auto-validate — returns data so the agent can reason about each one
    and call validate_prediction() with its own credit judgment.

    current_prices: JSON like {"BTC/USDT": 98500, "ETH/USDT": 3200}
    """
    conn = _init_db()
    try:
        prices = json.loads(current_prices) if current_prices else {}

        # Find pending predictions whose timeframe has expired
        rows = conn.execute(
            """SELECT * FROM predictions
               WHERE status = 'pending'
                 AND timeframe_hours > 0
                 AND datetime(created_at, '+' || CAST(timeframe_hours AS INTEGER) || ' hours')
                     < datetime('now')
               ORDER BY created_at""",
        ).fetchall()

        expired = []
        for row in rows:
            p = dict(row)
            symbol = p["symbol"]
            current_price = prices.get(symbol)
            context: dict[str, Any] = {
                "prediction_id": p["id"],
                "trade_id": p["trade_id"],
                "agent": p["agent"],
                "prediction_type": p["prediction_type"],
                "prediction": p["prediction"],
                "target_value": p["target_value"],
                "timeframe_hours": p["timeframe_hours"],
                "confidence": p["confidence"],
                "created_at": p["created_at"],
                "symbol": symbol,
            }
            if current_price is not None and p["target_value"]:
                target = p["target_value"]
                context["current_price"] = current_price
                context["price_diff_pct"] = round(
                    ((current_price - target) / target) * 100, 2
                )
            expired.append(context)

        # Also find non-price predictions that expired (sentiment, funding, etc.)
        non_price_rows = conn.execute(
            """SELECT * FROM predictions
               WHERE status = 'pending'
                 AND timeframe_hours > 0
                 AND (target_value IS NULL OR target_value = 0)
                 AND datetime(created_at, '+' || CAST(timeframe_hours AS INTEGER) || ' hours')
                     < datetime('now')
               ORDER BY created_at""",
        ).fetchall()

        # These are already included in the main query above,
        # but we tag them so the agent knows they lack price data
        non_price_ids = {dict(r)["id"] for r in non_price_rows}
        for item in expired:
            if item["prediction_id"] in non_price_ids:
                item["has_price_target"] = False
            else:
                item["has_price_target"] = True

        return {
            "status": "success",
            "total_expired": len(expired),
            "expired_predictions": expired,
            "prices_provided": list(prices.keys()),
        }
    finally:
        conn.close()


def _get_db_stats() -> dict:
    conn = _init_db()
    try:
        tables = {}
        for table in ("trades", "predictions", "patterns", "summaries",
                       "trade_modifications", "portfolio_state"):
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            tables[table] = count
        db_size = DB_PATH.stat().st_size if DB_PATH.exists() else 0
        return {
            "status": "success",
            "db_path": str(DB_PATH),
            "db_size_bytes": db_size,
            "db_size_kb": round(db_size / 1024, 1),
            "tables": tables,
        }
    finally:
        conn.close()


# ===================================================================
# MCP TOOL WRAPPERS (thin delegation to core functions)
# ===================================================================


@mcp.tool()
def record_trade(trade_id: str, symbol: str, side: str, portfolio_type: str,
                 entry_price: float, usd_amount: float, leverage: float = 1,
                 stop_loss: float = 0, take_profit: float = 0,
                 strategy_type: str = "", reasoning: str = "",
                 key_assumptions: str = "[]", agent_signals: str = "{}",
                 learning: str = "{}") -> dict:
    """Record a new open trade and deduct from portfolio balance."""
    return _record_trade(trade_id, symbol, side, portfolio_type, entry_price,
                         usd_amount, leverage, stop_loss, take_profit,
                         strategy_type, reasoning, key_assumptions,
                         agent_signals, learning)


@mcp.tool()
def close_trade(trade_id: str, exit_price: float,
                close_reason: str = "") -> dict:
    """Close an open trade, calculate PnL, update portfolio balance."""
    return _close_trade(trade_id, exit_price, close_reason)


@mcp.tool()
def update_trade(trade_id: str, stop_loss: float | None = None,
                 take_profit: float | None = None, notes: str = "") -> dict:
    """Update SL/TP on an open trade. Every change is logged with the reason.
    Use for trailing stops, TP adjustments, or risk management changes.
    The agent should explain WHY in the notes field."""
    return _update_trade(trade_id, stop_loss, take_profit, notes)


@mcp.tool()
def get_trade_modifications(trade_id: str = "", limit: int = 20) -> dict:
    """Get the modification history for a trade. Shows all SL/TP changes
    with timestamps and NL reasons. Useful for post-mortem analysis."""
    return _get_trade_modifications(trade_id, limit)


@mcp.tool()
def query_trades(symbol: str = "", status: str = "", strategy_type: str = "",
                 result: str = "", limit: int = 20, offset: int = 0) -> dict:
    """Query trades with optional filters. Returns only matching rows, not everything."""
    return _query_trades(symbol, status, strategy_type, result, limit, offset)


@mcp.tool()
def get_portfolio_state() -> dict:
    """Get current portfolio balances and overall stats."""
    return _get_portfolio_state()


@mcp.tool()
def record_prediction(prediction_id: str, trade_id: str, symbol: str,
                      agent: str, prediction_type: str, prediction: str,
                      target_value: float = 0, timeframe_hours: float = 0,
                      confidence: float = 0.5) -> dict:
    """Record a testable prediction from an agent."""
    return _record_prediction(prediction_id, trade_id, symbol, agent,
                              prediction_type, prediction, target_value,
                              timeframe_hours, confidence)


@mcp.tool()
def validate_prediction(prediction_id: str, actual_outcome: str,
                        is_correct: bool, error_margin: float = 0,
                        evaluation: str = "") -> dict:
    """Validate a prediction. Pure recording — no formula scoring.
    The agent writes a natural language evaluation explaining how close
    the prediction was, why it worked/failed, and lessons learned.
    This evaluation is stored and available for future agents to read."""
    return _validate_prediction(prediction_id, actual_outcome, is_correct,
                                error_margin, evaluation)


@mcp.tool()
def query_predictions(trade_id: str = "", agent: str = "", status: str = "",
                      symbol: str = "", limit: int = 20) -> dict:
    """Query predictions with optional filters."""
    return _query_predictions(trade_id, agent, status, symbol, limit)


@mcp.tool()
def get_prediction_track_record(symbol: str = "", strategy_type: str = "",
                                prediction_type: str = "", agent: str = "",
                                days_windows: str = "[7,30,90]",
                                include_evaluations: int = 5) -> dict:
    """Prediction-centric track record. Queries predictions JOIN trades directly.
    The key question: "how has this type of setup performed?" — not "how much
    do I trust this agent?" Agent is ONE filter, not the primary key.
    Returns accuracy by time window (7d, 30d, 90d, global) plus recent NL
    evaluations for context. Use this to assess setup reliability before trading."""
    return _get_prediction_track_record(symbol, strategy_type, prediction_type,
                                        agent, days_windows, include_evaluations)


@mcp.tool()
def upsert_pattern(name: str, conditions: str = "[]", is_win: bool = True,
                   pnl_percent: float = 0, notes: str = "") -> dict:
    """Create or update a trading pattern after a trade closes."""
    return _upsert_pattern(name, conditions, is_win, pnl_percent, notes)


@mcp.tool()
def query_patterns(symbol: str = "", min_win_rate: float = 0,
                   min_occurrences: int = 0, recommendation: str = "",
                   limit: int = 10) -> dict:
    """Query patterns with filters. Agents use this instead of reading the entire file."""
    return _query_patterns(symbol, min_win_rate, min_occurrences,
                           recommendation, limit)


@mcp.tool()
def generate_summary(period: str = "", summary_type: str = "monthly") -> dict:
    """Generate and store a summary of trading activity for a period.
    If period is empty, defaults to current month (YYYY-MM) or quarter (YYYY-QN)."""
    return _generate_summary(period, summary_type)


@mcp.tool()
def get_summary(period: str = "", summary_type: str = "monthly") -> dict:
    """Retrieve a previously generated summary."""
    return _get_summary(period, summary_type)


@mcp.tool()
def get_trade_stats(symbol: str = "", strategy_type: str = "") -> dict:
    """Get aggregated trade statistics with optional filters."""
    return _get_trade_stats(symbol, strategy_type)


@mcp.tool()
def migrate_from_json(json_dir: str = "") -> dict:
    """Migrate data from JSON files (portfolio.json, predictions.json, etc.) into SQLite.
    Only needs to be run once. Safe to re-run (skips existing records)."""
    return _migrate_from_json(json_dir)


@mcp.tool()
def find_expired_predictions(current_prices: str = "{}") -> dict:
    """Find predictions past their timeframe and return context for evaluation.
    Does NOT auto-validate. Returns each expired prediction with target vs current
    price context so the agent can reason about credit and call validate_prediction().
    current_prices: JSON like '{"BTC/USDT": 98500, "ETH/USDT": 3200}'"""
    return _find_expired_predictions(current_prices)


@mcp.tool()
def get_db_stats() -> dict:
    """Get database size and row counts for monitoring."""
    return _get_db_stats()


if __name__ == "__main__":
    mcp.run()
