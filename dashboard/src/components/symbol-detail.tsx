"use client";

import { motion } from "framer-motion";
import {
  Activity,
  Target,
  TrendingDown,
  TrendingUp,
  Wallet,
  Trophy,
  Skull,
} from "lucide-react";
import { SpotlightCard } from "./spotlight-card";
import { SymbolHistoryChart } from "./symbol-history-chart";
import type { Candle, Interval } from "@/lib/ohlcv";
import type { SymbolStats, Trade } from "@/lib/db";

export function SymbolDetail({
  symbol,
  stats,
  trades,
  initialCandles,
  initialInterval,
  currentPrice,
}: {
  symbol: string;
  stats: SymbolStats;
  trades: Trade[];
  initialCandles: Candle[];
  initialInterval: Interval;
  currentPrice: number | null;
}) {
  // Unrealized PnL across all open trades for this symbol
  let unrealizedPnl = 0;
  if (currentPrice != null) {
    for (const t of trades) {
      if (t.status !== "open") continue;
      const dir = t.side.toLowerCase() === "short" ? -1 : 1;
      const pct = ((currentPrice - t.entry_price) / t.entry_price) * dir;
      unrealizedPnl += t.usd_amount * pct;
    }
  }

  return (
    <motion.section
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.4 }}
      className="relative rounded-xl border border-border/50 bg-card/30 backdrop-blur overflow-hidden"
    >
      {/* Decorative gradient mesh */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden -z-0">
        <div className="absolute -top-32 -left-24 h-72 w-72 rounded-full bg-violet-500/10 blur-3xl" />
        <div className="absolute -bottom-32 -right-24 h-72 w-72 rounded-full bg-emerald-500/10 blur-3xl" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 h-64 w-64 rounded-full bg-cyan-500/5 blur-3xl" />
      </div>

      <div className="relative z-10 p-6 space-y-6">
        {/* Header */}
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div className="flex flex-col gap-1">
            <span className="text-[10px] uppercase tracking-widest text-muted-foreground">
              Symbol detail
            </span>
            <h2 className="text-3xl font-semibold tracking-tight flex items-center gap-3">
              {symbol}
              {currentPrice != null && (
                <span className="text-base font-mono tabular-nums text-muted-foreground">
                  ${currentPrice.toLocaleString("en-US", { minimumFractionDigits: 2 })}
                </span>
              )}
            </h2>
            <p className="text-xs text-muted-foreground">
              {stats.firstTradeAt &&
                `Tracked since ${new Date(stats.firstTradeAt).toLocaleDateString("en-US", {
                  month: "short",
                  day: "numeric",
                  year: "numeric",
                })}`}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
              On this symbol
            </span>
            <div className="text-2xl font-semibold tabular-nums">
              <span
                className={
                  stats.totalRealizedPnl > 0
                    ? "text-emerald-500"
                    : stats.totalRealizedPnl < 0
                    ? "text-rose-500"
                    : ""
                }
              >
                {stats.totalRealizedPnl >= 0 ? "+$" : "-$"}
                {Math.abs(stats.totalRealizedPnl).toFixed(2)}
              </span>
            </div>
          </div>
        </div>

        {/* Stats grid */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          <SpotlightCard
            label="Total Trades"
            value={stats.total}
            decimals={0}
            icon={<Activity className="h-3.5 w-3.5" />}
            delay={0.02}
          />
          <SpotlightCard
            label="Win Rate"
            value={stats.winRate}
            decimals={1}
            suffix="%"
            tone={stats.winRate >= 50 ? "pos" : stats.winRate > 0 ? "neg" : "neu"}
            icon={<Target className="h-3.5 w-3.5" />}
            hint={`${stats.wins}W · ${stats.losses}L`}
            delay={0.05}
          />
          <SpotlightCard
            label="Realized PnL"
            value={Math.abs(stats.totalRealizedPnl)}
            decimals={2}
            prefix={stats.totalRealizedPnl >= 0 ? "+$" : "-$"}
            tone={stats.totalRealizedPnl > 0 ? "pos" : stats.totalRealizedPnl < 0 ? "neg" : "neu"}
            icon={
              stats.totalRealizedPnl >= 0 ? (
                <TrendingUp className="h-3.5 w-3.5" />
              ) : (
                <TrendingDown className="h-3.5 w-3.5" />
              )
            }
            delay={0.08}
          />
          <SpotlightCard
            label="Unrealized"
            value={Math.abs(unrealizedPnl)}
            decimals={2}
            prefix={unrealizedPnl >= 0 ? "+$" : "-$"}
            tone={unrealizedPnl > 0 ? "pos" : unrealizedPnl < 0 ? "neg" : "neu"}
            icon={<Wallet className="h-3.5 w-3.5" />}
            hint={stats.open > 0 ? `${stats.open} open · $${stats.totalAllocated.toFixed(0)}` : "no open"}
            delay={0.11}
          />
          <SpotlightCard
            label="Best Trade"
            value={Math.abs(stats.bestPnlPct ?? 0)}
            decimals={2}
            prefix={stats.bestPnlPct >= 0 ? "+" : "-"}
            suffix="%"
            tone="pos"
            icon={<Trophy className="h-3.5 w-3.5" />}
            delay={0.14}
          />
          <SpotlightCard
            label="Worst Trade"
            value={Math.abs(stats.worstPnlPct ?? 0)}
            decimals={2}
            prefix={stats.worstPnlPct >= 0 ? "+" : "-"}
            suffix="%"
            tone="neg"
            icon={<Skull className="h-3.5 w-3.5" />}
            delay={0.17}
          />
        </div>

        {/* Chart */}
        <SymbolHistoryChart
          symbol={symbol}
          trades={trades}
          initialCandles={initialCandles}
          initialInterval={initialInterval}
        />
      </div>
    </motion.section>
  );
}
