import {
  getStats,
  getTradesFiltered,
  getTradeSymbols,
  getSymbolStats,
} from "@/lib/db";
import { getOhlcv, getCurrentPrice } from "@/lib/ohlcv";
import { PageHeader } from "@/components/page-header";
import { TradesTable } from "@/components/trades-table";
import { TradesFilter } from "@/components/trades-filter";
import { SymbolDetail } from "@/components/symbol-detail";
import { Card, CardContent } from "@/components/ui/card";
import { money, pct } from "@/lib/format";

export const dynamic = "force-dynamic";
export const revalidate = 0;

type SP = {
  symbol?: string;
  status?: string;
  side?: string;
};

function normalizeStatus(s?: string): "open" | "closed" | null {
  return s === "open" || s === "closed" ? s : null;
}
function normalizeSide(s?: string): "long" | "short" | null {
  return s === "long" || s === "short" ? s : null;
}

export default async function TradesPage({
  searchParams,
}: {
  searchParams: Promise<SP>;
}) {
  const sp = await searchParams;
  const symbol = sp.symbol ? sp.symbol.toUpperCase() : null;
  const status = normalizeStatus(sp.status);
  const side = normalizeSide(sp.side);

  const all = getTradesFiltered({ symbol, status, side, limit: 500 });
  const stats = getStats();
  const symbols = getTradeSymbols();
  const open = all.filter((t) => t.status === "open");

  // When filtered to a symbol, fetch its detail + chart data
  let symbolDetail: Awaited<ReturnType<typeof loadSymbolDetail>> | null = null;
  if (symbol) {
    symbolDetail = await loadSymbolDetail(symbol);
  }

  return (
    <div className="mx-auto max-w-7xl px-6 py-8 space-y-6">
      <PageHeader
        eyebrow="History"
        title="Trades"
        subtitle={`${stats.total} total · ${stats.open} open · ${stats.closed} closed${
          symbol ? ` · filtered to ${symbol}` : ""
        }`}
      />

      {!symbol && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard label="Total Trades" value={stats.total.toString()} />
          <StatCard
            label="Win Rate"
            value={stats.closed > 0 ? `${stats.winRate.toFixed(1)}%` : "—"}
            tone={stats.winRate >= 50 ? "pos" : stats.winRate > 0 ? "neg" : "neu"}
          />
          <StatCard
            label="Avg Win"
            value={stats.wins > 0 ? pct(stats.avgWinPct) : "—"}
            tone="pos"
          />
          <StatCard
            label="Avg Loss"
            value={stats.losses > 0 ? pct(stats.avgLossPct) : "—"}
            tone="neg"
          />
        </div>
      )}

      <TradesFilter
        symbols={symbols}
        currentSymbol={symbol}
        currentStatus={status ?? "all"}
        currentSide={side ?? "all"}
        totalShown={all.length}
      />

      {symbol && symbolDetail && symbolDetail.stats && (
        <SymbolDetail
          symbol={symbol}
          stats={symbolDetail.stats}
          trades={all}
          initialCandles={symbolDetail.candles}
          initialInterval="1h"
          currentPrice={symbolDetail.price}
        />
      )}

      {!symbol && open.length > 0 && (
        <Card className="border-blue-500/30 bg-blue-500/5 backdrop-blur">
          <CardContent className="p-5">
            <div className="text-xs uppercase tracking-wider text-blue-400 mb-3">
              {open.length} Open Position{open.length === 1 ? "" : "s"}
            </div>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {open.map((t) => {
                const risk = t.stop_loss != null ? Math.abs(t.entry_price - t.stop_loss) : null;
                const reward = t.take_profit != null ? Math.abs(t.take_profit - t.entry_price) : null;
                const rr = risk && reward ? reward / risk : null;
                return (
                  <div
                    key={t.id}
                    className="rounded-md border border-border/40 bg-background/40 p-3 text-xs space-y-1.5"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-sm">{t.symbol}</span>
                      <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                        {t.side} · {t.leverage}x
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-muted-foreground">
                      <span>Entry</span>
                      <span className="tabular-nums text-foreground">{money(t.entry_price)}</span>
                    </div>
                    <div className="flex items-center justify-between text-muted-foreground">
                      <span>Stop / TP</span>
                      <span className="tabular-nums">
                        {t.stop_loss ? money(t.stop_loss) : "—"} /{" "}
                        <span className="text-emerald-500">{t.take_profit ? money(t.take_profit) : "—"}</span>
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-muted-foreground">
                      <span>Size · R/R</span>
                      <span className="tabular-nums">
                        {money(t.usd_amount)} · {rr ? `${rr.toFixed(2)}:1` : "—"}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}

      <TradesTable trades={all} />
    </div>
  );
}

async function loadSymbolDetail(symbol: string) {
  const [stats, candles, price] = await Promise.all([
    Promise.resolve(getSymbolStats(symbol)),
    getOhlcv(symbol, "1h", 300),
    getCurrentPrice(symbol),
  ]);
  return { stats, candles, price };
}

function StatCard({
  label,
  value,
  tone = "neu",
}: {
  label: string;
  value: string;
  tone?: "pos" | "neg" | "neu";
}) {
  return (
    <Card className="border-border/50 bg-card/50 backdrop-blur">
      <CardContent className="p-5">
        <div className="text-xs uppercase tracking-wider text-muted-foreground mb-2">
          {label}
        </div>
        <div
          className={
            tone === "pos"
              ? "text-2xl font-semibold tabular-nums text-emerald-500"
              : tone === "neg"
              ? "text-2xl font-semibold tabular-nums text-rose-500"
              : "text-2xl font-semibold tabular-nums"
          }
        >
          {value}
        </div>
      </CardContent>
    </Card>
  );
}
