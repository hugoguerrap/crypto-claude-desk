import Database from "better-sqlite3";
import path from "node:path";
import fs from "node:fs";

let _db: Database.Database | null = null;

function getDb(): Database.Database {
  if (_db) return _db;
  const dbPath = path.resolve(process.cwd(), "..", "data", "db", "learning.db");
  _db = new Database(dbPath, { readonly: true, fileMustExist: true });
  _db.pragma("journal_mode = WAL");
  return _db;
}

export type PortfolioState = {
  spot_initial: number;
  spot_balance: number;
  futures_initial: number;
  futures_balance: number;
  currency: string;
  total_trades: number;
  wins: number;
  losses: number;
  total_pnl: number;
  updated_at: string | null;
};

export type Trade = {
  id: string;
  symbol: string;
  side: string;
  portfolio_type: string;
  entry_price: number;
  exit_price: number | null;
  usd_amount: number;
  leverage: number;
  stop_loss: number | null;
  take_profit: number | null;
  strategy_type: string | null;
  opened_at: string;
  closed_at: string | null;
  close_reason: string | null;
  pnl_usd: number | null;
  pnl_percent: number | null;
  result: string | null;
  status: string;
  reasoning: string | null;
  key_assumptions: string | null;
  agent_signals: string | null;
  learning: string | null;
};

export type Prediction = {
  id: string;
  trade_id: string;
  symbol: string;
  agent: string;
  prediction_type: string;
  prediction: string;
  target_value: number | null;
  timeframe_hours: number | null;
  confidence: number | null;
  status: string;
  actual_outcome: string | null;
  error_margin: number | null;
  evaluation: string | null;
  created_at: string;
  validated_at: string | null;
};

export type Pattern = {
  name: string;
  conditions: string | null;
  occurrences: number;
  wins: number;
  losses: number;
  win_rate: number;
  avg_pnl_percent: number;
  first_seen: string | null;
  last_seen: string | null;
  recommendation: string | null;
  notes: string | null;
};

export function getPortfolioState(): PortfolioState | null {
  const db = getDb();
  return (
    (db.prepare("SELECT * FROM portfolio_state ORDER BY id DESC LIMIT 1").get() as PortfolioState | undefined) ?? null
  );
}

export function getOpenTrades(): Trade[] {
  const db = getDb();
  return db
    .prepare("SELECT * FROM trades WHERE status = 'open' ORDER BY opened_at DESC")
    .all() as Trade[];
}

/**
 * Extract liquidation price from a trade's agent_signals JSON, with a
 * conservative fallback for futures trades that omitted it: a naive
 * cross-margin approximation entry × (1 ∓ 1/leverage). This is rough but
 * good enough as a visual reference on the chart.
 */
export function extractLiquidationPrice(t: Trade): number | null {
  if (t.portfolio_type !== "futures") return null;
  if (t.agent_signals) {
    try {
      const sig = JSON.parse(t.agent_signals) as { liquidation_price?: number };
      if (typeof sig.liquidation_price === "number" && sig.liquidation_price > 0) {
        return sig.liquidation_price;
      }
    } catch {
      // fall through to computed default
    }
  }
  const lev = t.leverage || 1;
  if (lev <= 1) return null;
  const direction = t.side === "short" ? 1 : -1;
  // Subtract a small maintenance margin buffer (0.5%) to be slightly more
  // realistic than pure 1/leverage.
  const buffer = 0.005;
  return t.entry_price * (1 + direction * (1 / lev - buffer));
}

/**
 * Recently closed trades for the price chart's post-mortem overlay.
 * Filters to last N days so the markers stay within the visible candle
 * window. Most-recent first.
 */
export function getRecentClosedTradesForChart(daysBack = 14): Trade[] {
  const db = getDb();
  const cutoff = new Date(Date.now() - daysBack * 24 * 60 * 60 * 1000).toISOString();
  return db
    .prepare(
      "SELECT * FROM trades WHERE status = 'closed' AND closed_at IS NOT NULL AND closed_at >= ? ORDER BY closed_at DESC"
    )
    .all(cutoff) as Trade[];
}

export function getRecentTrades(limit = 25): Trade[] {
  const db = getDb();
  return db
    .prepare("SELECT * FROM trades ORDER BY COALESCE(closed_at, opened_at) DESC LIMIT ?")
    .all(limit) as Trade[];
}

export type TradeFilter = {
  symbol?: string | null;
  status?: "open" | "closed" | null;
  side?: "long" | "short" | null;
  limit?: number;
};

/**
 * Dynamic trades query — any combination of (symbol, status, side) filters.
 * Returns most-recent first by closed_at falling back to opened_at.
 */
export function getTradesFiltered(filter: TradeFilter = {}): Trade[] {
  const db = getDb();
  const where: string[] = [];
  const params: (string | number)[] = [];
  if (filter.symbol) {
    where.push("UPPER(symbol) = UPPER(?)");
    params.push(filter.symbol);
  }
  if (filter.status === "open" || filter.status === "closed") {
    where.push("status = ?");
    params.push(filter.status);
  }
  if (filter.side === "long" || filter.side === "short") {
    where.push("side = ?");
    params.push(filter.side);
  }
  const whereClause = where.length ? `WHERE ${where.join(" AND ")}` : "";
  const limit = filter.limit ?? 500;
  params.push(limit);
  const sql = `SELECT * FROM trades ${whereClause} ORDER BY COALESCE(closed_at, opened_at) DESC LIMIT ?`;
  return db.prepare(sql).all(...params) as Trade[];
}

export type SymbolStats = {
  symbol: string;
  total: number;
  open: number;
  closed: number;
  wins: number;
  losses: number;
  winRate: number;
  avgWinPct: number;
  avgLossPct: number;
  totalRealizedPnl: number;
  totalAllocated: number;
  bestPnlPct: number;
  worstPnlPct: number;
  firstTradeAt: string | null;
  lastTradeAt: string | null;
};

export function getSymbolStats(symbol: string): SymbolStats | null {
  const db = getDb();
  const row = db
    .prepare(
      `SELECT
         COUNT(*) AS total,
         SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) AS open_count,
         SUM(CASE WHEN status = 'closed' THEN 1 ELSE 0 END) AS closed_count,
         SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) AS wins,
         SUM(CASE WHEN result = 'loss' THEN 1 ELSE 0 END) AS losses,
         AVG(CASE WHEN result = 'win' THEN pnl_percent END) AS avg_win_pct,
         AVG(CASE WHEN result = 'loss' THEN pnl_percent END) AS avg_loss_pct,
         SUM(CASE WHEN status = 'closed' THEN pnl_usd ELSE 0 END) AS realized_pnl,
         SUM(CASE WHEN status = 'open' THEN usd_amount ELSE 0 END) AS allocated,
         MAX(pnl_percent) AS best_pct,
         MIN(pnl_percent) AS worst_pct,
         MIN(opened_at) AS first_at,
         MAX(COALESCE(closed_at, opened_at)) AS last_at
       FROM trades
       WHERE UPPER(symbol) = UPPER(?)`
    )
    .get(symbol) as Record<string, number | string | null>;
  const total = (row.total as number) ?? 0;
  if (total === 0) return null;
  const wins = (row.wins as number) ?? 0;
  const losses = (row.losses as number) ?? 0;
  const closed = wins + losses;
  return {
    symbol: symbol.toUpperCase(),
    total,
    open: (row.open_count as number) ?? 0,
    closed: (row.closed_count as number) ?? 0,
    wins,
    losses,
    winRate: closed > 0 ? (wins / closed) * 100 : 0,
    avgWinPct: (row.avg_win_pct as number) ?? 0,
    avgLossPct: (row.avg_loss_pct as number) ?? 0,
    totalRealizedPnl: (row.realized_pnl as number) ?? 0,
    totalAllocated: (row.allocated as number) ?? 0,
    bestPnlPct: (row.best_pct as number) ?? 0,
    worstPnlPct: (row.worst_pct as number) ?? 0,
    firstTradeAt: (row.first_at as string) ?? null,
    lastTradeAt: (row.last_at as string) ?? null,
  };
}

export type SymbolCount = { symbol: string; count: number; open_count: number };

/**
 * Distinct symbols that have at least one trade, with counts.
 * Used to build dynamic filter pills.
 */
export function getTradeSymbols(): SymbolCount[] {
  const db = getDb();
  return db
    .prepare(
      `SELECT
         UPPER(symbol) AS symbol,
         COUNT(*) AS count,
         SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) AS open_count
       FROM trades
       GROUP BY UPPER(symbol)
       ORDER BY count DESC, symbol ASC`
    )
    .all() as SymbolCount[];
}

export function getEquityCurve(): { t: string; equity: number; pnl: number }[] {
  const db = getDb();
  const state = getPortfolioState();
  const initial = (state?.spot_initial ?? 0) + (state?.futures_initial ?? 0);
  const closed = db
    .prepare(
      "SELECT closed_at, pnl_usd FROM trades WHERE status = 'closed' AND closed_at IS NOT NULL ORDER BY closed_at ASC"
    )
    .all() as { closed_at: string; pnl_usd: number | null }[];
  let running = initial;
  return closed.map((c) => {
    running += c.pnl_usd ?? 0;
    return { t: c.closed_at, equity: running, pnl: c.pnl_usd ?? 0 };
  });
}

/**
 * Equity curve broken down by portfolio_type (spot vs futures).
 * Each point includes spot, futures, and total running equity at that timestamp.
 * Useful for visualizing each book's contribution to portfolio PnL separately.
 */
export function getEquityCurveByBook(): {
  t: string;
  spot: number;
  futures: number;
  total: number;
}[] {
  const db = getDb();
  const state = getPortfolioState();
  const spotInit = state?.spot_initial ?? 0;
  const futInit = state?.futures_initial ?? 0;
  const closed = db
    .prepare(
      "SELECT closed_at, pnl_usd, portfolio_type FROM trades WHERE status = 'closed' AND closed_at IS NOT NULL ORDER BY closed_at ASC"
    )
    .all() as { closed_at: string; pnl_usd: number | null; portfolio_type: string }[];
  let spot = spotInit;
  let fut = futInit;
  return closed.map((c) => {
    const pnl = c.pnl_usd ?? 0;
    if (c.portfolio_type === "futures") fut += pnl;
    else spot += pnl;
    return { t: c.closed_at, spot, futures: fut, total: spot + fut };
  });
}

/**
 * Per-book stats (spot or futures). Mirrors getStats() but scoped by portfolio_type.
 * Used to show spot vs futures performance side by side.
 */
export function getStatsByBook(book: "spot" | "futures") {
  const db = getDb();
  const row = db
    .prepare(
      `SELECT
         COUNT(*) AS total,
         SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) AS open_count,
         SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) AS wins,
         SUM(CASE WHEN result = 'loss' THEN 1 ELSE 0 END) AS losses,
         SUM(CASE WHEN status = 'closed' THEN pnl_usd ELSE 0 END) AS realized_pnl,
         SUM(CASE WHEN status = 'open' THEN usd_amount ELSE 0 END) AS allocated_capital
       FROM trades
       WHERE portfolio_type = ?`
    )
    .get(book) as Record<string, number | null>;
  const wins = row.wins ?? 0;
  const losses = row.losses ?? 0;
  const closed = wins + losses;
  const winRate = closed > 0 ? (wins / closed) * 100 : 0;
  return {
    total: row.total ?? 0,
    open: row.open_count ?? 0,
    closed,
    wins,
    losses,
    winRate,
    realizedPnl: row.realized_pnl ?? 0,
    allocatedCapital: row.allocated_capital ?? 0,
  };
}

export function getStats() {
  const db = getDb();
  const row = db
    .prepare(
      `SELECT
         COUNT(*) AS total,
         SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) AS open_count,
         SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) AS wins,
         SUM(CASE WHEN result = 'loss' THEN 1 ELSE 0 END) AS losses,
         AVG(CASE WHEN result = 'win' THEN pnl_percent END) AS avg_win_pct,
         AVG(CASE WHEN result = 'loss' THEN pnl_percent END) AS avg_loss_pct,
         SUM(CASE WHEN result = 'win' THEN pnl_usd ELSE 0 END) AS gross_win,
         SUM(CASE WHEN result = 'loss' THEN ABS(pnl_usd) ELSE 0 END) AS gross_loss,
         SUM(CASE WHEN status = 'closed' THEN pnl_usd ELSE 0 END) AS realized_pnl,
         SUM(CASE WHEN status = 'open' THEN usd_amount ELSE 0 END) AS allocated_capital
       FROM trades`
    )
    .get() as Record<string, number | null>;
  const wins = row.wins ?? 0;
  const losses = row.losses ?? 0;
  const closed = wins + losses;
  const winRate = closed > 0 ? (wins / closed) * 100 : 0;
  const grossWin = row.gross_win ?? 0;
  const grossLoss = row.gross_loss ?? 0;
  const profitFactor = grossLoss > 0 ? grossWin / grossLoss : grossWin > 0 ? Infinity : 0;
  return {
    total: row.total ?? 0,
    open: row.open_count ?? 0,
    closed,
    wins,
    losses,
    winRate,
    avgWinPct: row.avg_win_pct ?? 0,
    avgLossPct: row.avg_loss_pct ?? 0,
    profitFactor,
    realizedPnl: row.realized_pnl ?? 0,
    allocatedCapital: row.allocated_capital ?? 0,
  };
}

export function getPredictions(status?: string, limit = 50): Prediction[] {
  const db = getDb();
  if (status) {
    return db
      .prepare("SELECT * FROM predictions WHERE status = ? ORDER BY created_at DESC LIMIT ?")
      .all(status, limit) as Prediction[];
  }
  return db
    .prepare("SELECT * FROM predictions ORDER BY created_at DESC LIMIT ?")
    .all(limit) as Prediction[];
}

export function getPredictionAccuracy() {
  const db = getDb();
  const row = db
    .prepare(
      `SELECT
         COUNT(*) AS total,
         SUM(CASE WHEN status IN ('correct','validated_correct') THEN 1 ELSE 0 END) AS correct,
         SUM(CASE WHEN status IN ('partial','validated_partial') THEN 1 ELSE 0 END) AS partial,
         SUM(CASE WHEN status IN ('incorrect','wrong','validated_wrong') THEN 1 ELSE 0 END) AS wrong,
         SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) AS pending
       FROM predictions`
    )
    .get() as Record<string, number | null>;
  const total = row.total ?? 0;
  const validated = (row.correct ?? 0) + (row.partial ?? 0) + (row.wrong ?? 0);
  const accuracy = validated > 0 ? (((row.correct ?? 0) + 0.5 * (row.partial ?? 0)) / validated) * 100 : 0;
  return {
    total,
    correct: row.correct ?? 0,
    partial: row.partial ?? 0,
    wrong: row.wrong ?? 0,
    pending: row.pending ?? 0,
    accuracy,
  };
}

export function getPatterns(): Pattern[] {
  const db = getDb();
  return db.prepare("SELECT * FROM patterns ORDER BY occurrences DESC").all() as Pattern[];
}

export type LatestDecision = {
  symbol: string;
  date: string;
  verdict: string | null;
  content: string;
  files: string[];
};

export type ReportSummary = {
  slug: string;
  date: string;
  symbol: string;
  verdict: string | null;
  files: string[];
};

export function getAllReports(): ReportSummary[] {
  const reportsDir = path.resolve(process.cwd(), "..", "data", "reports");
  if (!fs.existsSync(reportsDir)) return [];
  const dirs = fs
    .readdirSync(reportsDir, { withFileTypes: true })
    .filter((d) => d.isDirectory())
    .map((d) => d.name)
    .sort()
    .reverse();
  return dirs.map((slug) => {
    const parts = slug.split("-");
    const date = parts.slice(0, 3).join("-");
    const symbol = parts.slice(3).join("-");
    const dirPath = path.join(reportsDir, slug);
    const files = fs
      .readdirSync(dirPath)
      .filter((f) => f.endsWith(".md"))
      .sort();
    let verdict: string | null = null;
    const decisionPath = path.join(dirPath, "decision.md");
    if (fs.existsSync(decisionPath)) {
      const content = fs.readFileSync(decisionPath, "utf-8");
      const m = content.match(/VERDICT[:\s]*([A-Z_]+)/);
      verdict = m?.[1] ?? null;
    }
    return { slug, date, symbol, verdict, files };
  });
}

export type ReportDetail = {
  slug: string;
  date: string;
  symbol: string;
  verdict: string | null;
  files: { name: string; content: string }[];
};

export function getReportContent(slug: string): ReportDetail | null {
  const reportsDir = path.resolve(process.cwd(), "..", "data", "reports", slug);
  if (!fs.existsSync(reportsDir)) return null;
  const parts = slug.split("-");
  const date = parts.slice(0, 3).join("-");
  const symbol = parts.slice(3).join("-");
  const order = ["decision.md", "market-data.md", "technical-analysis.md", "news-sentiment.md", "risk-assessment.md"];
  const fileNames = fs
    .readdirSync(reportsDir)
    .filter((f) => f.endsWith(".md"))
    .sort((a, b) => {
      const ia = order.indexOf(a);
      const ib = order.indexOf(b);
      if (ia === -1 && ib === -1) return a.localeCompare(b);
      if (ia === -1) return 1;
      if (ib === -1) return -1;
      return ia - ib;
    });
  const files = fileNames.map((name) => ({
    name,
    content: fs.readFileSync(path.join(reportsDir, name), "utf-8"),
  }));
  let verdict: string | null = null;
  const decision = files.find((f) => f.name === "decision.md");
  if (decision) {
    const m = decision.content.match(/VERDICT[:\s]*([A-Z_]+)/);
    verdict = m?.[1] ?? null;
  }
  return { slug, date, symbol, verdict, files };
}

export function getLatestDecision(): LatestDecision | null {
  const reportsDir = path.resolve(process.cwd(), "..", "data", "reports");
  if (!fs.existsSync(reportsDir)) return null;
  const dirs = fs
    .readdirSync(reportsDir, { withFileTypes: true })
    .filter((d) => d.isDirectory())
    .map((d) => d.name)
    .sort()
    .reverse();
  for (const d of dirs) {
    const decisionPath = path.join(reportsDir, d, "decision.md");
    if (fs.existsSync(decisionPath)) {
      const content = fs.readFileSync(decisionPath, "utf-8");
      const verdictMatch = content.match(/VERDICT[:\s]*([A-Z_]+)/);
      const [date, ...symParts] = d.split("-").reduce<string[]>((acc, part, i) => {
        if (i < 3) {
          acc[0] = (acc[0] ? acc[0] + "-" : "") + part;
        } else {
          acc.push(part);
        }
        return acc;
      }, [""]);
      const files = fs
        .readdirSync(path.join(reportsDir, d))
        .filter((f) => f.endsWith(".md"));
      return {
        symbol: symParts.join("-") || d,
        date,
        verdict: verdictMatch?.[1] ?? null,
        content,
        files,
      };
    }
  }
  return null;
}
