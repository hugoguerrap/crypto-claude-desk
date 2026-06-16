import {
  getPortfolioState,
  getStats,
  getStatsByBook,
  getEquityCurve,
  getEquityCurveByBook,
  getRecentTrades,
  getOpenTrades,
  getRecentClosedTradesForChart,
  extractLiquidationPrice,
  getPredictions,
  getPredictionAccuracy,
  getPatterns,
  getLatestDecision,
} from "@/lib/db";
import {
  getPolymarketCryptoSnapshot,
  getDefiFlowSnapshot,
} from "@/lib/market-intelligence";
import { getOhlcv, getCurrentPrice } from "@/lib/ohlcv";
import { KpiCards } from "@/components/kpi-cards";
import { EquityCurve } from "@/components/equity-curve";
import { TradesTable } from "@/components/trades-table";
import { PredictionsPanel } from "@/components/predictions-panel";
import { PatternsPanel } from "@/components/patterns-panel";
import { DecisionFeed } from "@/components/decision-feed";
import { MarketIntelligence } from "@/components/market-intelligence";
import { PriceChart } from "@/components/price-chart";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export default async function DashboardPage() {
  const portfolio = getPortfolioState();
  const stats = getStats();
  const spotStats = getStatsByBook("spot");
  const futuresStats = getStatsByBook("futures");
  const equityCurve = getEquityCurve();
  const equityByBook = getEquityCurveByBook();
  const trades = getRecentTrades(25);
  const openTrades = getOpenTrades();
  const predictions = getPredictions(undefined, 50);
  const accuracy = getPredictionAccuracy();
  const patterns = getPatterns();
  const decision = getLatestDecision();
  // Pick the symbol to chart: most recently opened trade, or fall back to BTC.
  const chartSymbol = openTrades[0]?.symbol ?? "BTC";
  const chartTrades = openTrades.map((t) => ({
    id: t.id,
    symbol: t.symbol,
    side: t.side,
    entry_price: t.entry_price,
    stop_loss: t.stop_loss,
    take_profit: t.take_profit,
    usd_amount: t.usd_amount,
    leverage: t.leverage,
    portfolio_type: t.portfolio_type,
    liquidation_price: extractLiquidationPrice(t),
  }));
  const closedChartTrades = getRecentClosedTradesForChart(14).map((t) => ({
    id: t.id,
    symbol: t.symbol,
    side: t.side,
    entry_price: t.entry_price,
    exit_price: t.exit_price,
    opened_at: t.opened_at,
    closed_at: t.closed_at,
    result: t.result,
    pnl_percent: t.pnl_percent,
  }));
  const [polymarket, defi, candles, currentPrice] = await Promise.all([
    getPolymarketCryptoSnapshot(),
    getDefiFlowSnapshot(),
    getOhlcv(chartSymbol, "1h", 200),
    getCurrentPrice(chartSymbol),
  ]);

  const spotInit = portfolio?.spot_initial ?? 0;
  const futInit = portfolio?.futures_initial ?? 0;
  const spotBal = portfolio?.spot_balance ?? 0;
  const futBal = portfolio?.futures_balance ?? 0;
  const initial = spotInit + futInit;
  const cashBalance = spotBal + futBal;
  // Total equity = available cash + capital locked in open positions (at cost) + realized PnL
  // Since open positions are valued at cost, equity = initial + realized PnL
  const realizedPnl = stats.realizedPnl;
  const equity = cashBalance + stats.allocatedCapital;
  const pnlPct = initial > 0 ? (realizedPnl / initial) * 100 : 0;

  // Per-book equity = cash in that book + capital allocated to open trades in that book
  const spotEquity = spotBal + spotStats.allocatedCapital;
  const futEquity = futBal + futuresStats.allocatedCapital;

  return (
    <div className="mx-auto max-w-7xl px-6 py-8 space-y-6">
      <header className="flex flex-col gap-1 mb-2">
        <div className="flex items-center gap-2">
          <span className="text-[10px] uppercase tracking-widest text-muted-foreground">
            Live · Paper Trading
          </span>
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full rounded-full bg-emerald-500/60 animate-ping" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
          </span>
        </div>
        <h1 className="text-3xl font-semibold tracking-tight">Trading Desk</h1>
        <p className="text-sm text-muted-foreground">
          Multi-agent intelligence · {stats.total} total trades · {accuracy.total} predictions
          logged
        </p>
      </header>

      <KpiCards
        equity={equity}
        pnl={realizedPnl}
        pnlPct={pnlPct}
        winRate={stats.winRate}
        openTrades={stats.open}
        allocated={stats.allocatedCapital}
        spot={{
          equity: spotEquity,
          realizedPnl: spotStats.realizedPnl,
          allocated: spotStats.allocatedCapital,
          open: spotStats.open,
          winRate: spotStats.winRate,
          closed: spotStats.closed,
        }}
        futures={{
          equity: futEquity,
          realizedPnl: futuresStats.realizedPnl,
          allocated: futuresStats.allocatedCapital,
          open: futuresStats.open,
          winRate: futuresStats.winRate,
          closed: futuresStats.closed,
        }}
      />

      <EquityCurve
        data={equityCurve}
        initial={initial}
        byBook={equityByBook}
        spotInitial={spotInit}
        futuresInitial={futInit}
      />

      <PriceChart
        initialSymbol={chartSymbol}
        initialInterval="1h"
        initialCandles={candles}
        initialPrice={currentPrice}
        openTrades={chartTrades}
        closedTrades={closedChartTrades}
      />

      <MarketIntelligence polymarket={polymarket} defi={defi} />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <TradesTable trades={trades} />
        </div>
        <div>
          <PatternsPanel patterns={patterns} />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <DecisionFeed decision={decision} />
        <PredictionsPanel predictions={predictions} accuracy={accuracy} />
      </div>

      <footer className="pt-4 pb-2 text-[11px] text-muted-foreground/60 text-center">
        Crypto Trading Desk · Local SQLite · {new Date().toLocaleDateString("en-US", {
          year: "numeric",
          month: "long",
          day: "numeric",
        })}
      </footer>
    </div>
  );
}
