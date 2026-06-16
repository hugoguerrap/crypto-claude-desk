"use client";

import { motion } from "framer-motion";
import { Activity, TrendingUp, TrendingDown, Target, Wallet, Layers, Zap } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { AnimatedNumber } from "./animated-number";
import { cn } from "@/lib/utils";

type BookStats = {
  equity: number;
  realizedPnl: number;
  allocated: number;
  open: number;
  winRate: number;
  closed: number;
};

export function KpiCards({
  equity,
  pnl,
  pnlPct,
  winRate,
  openTrades,
  allocated,
  spot,
  futures,
}: {
  equity: number;
  pnl: number;
  pnlPct: number;
  winRate: number;
  openTrades: number;
  allocated: number;
  spot?: BookStats;
  futures?: BookStats;
}) {
  // Row 1: 4 KPI cards (unchanged structure, total equity stays as main metric)
  const kpis = [
    {
      label: "Total Equity",
      value: equity,
      prefix: "$",
      decimals: 2,
      icon: <Wallet className="h-4 w-4" />,
      tone: "neu" as const,
      footer:
        spot && futures
          ? `Spot $${spot.equity.toFixed(0)} · Fut $${futures.equity.toFixed(0)}`
          : undefined,
    },
    {
      label: "Realized PnL",
      value: Math.abs(pnl),
      prefix: pnl >= 0 ? "+$" : "-$",
      decimals: 2,
      icon: pnl >= 0 ? <TrendingUp className="h-4 w-4" /> : <TrendingDown className="h-4 w-4" />,
      tone: (pnl > 0 ? "pos" : pnl < 0 ? "neg" : "neu") as "pos" | "neg" | "neu",
      footer: `${pnlPct >= 0 ? "+" : ""}${pnlPct.toFixed(2)}% on closed trades`,
    },
    {
      label: "Win Rate",
      value: winRate,
      suffix: "%",
      decimals: 1,
      icon: <Target className="h-4 w-4" />,
      tone: (winRate >= 50 ? "pos" : winRate > 0 ? "neg" : "neu") as "pos" | "neg" | "neu",
      footer:
        spot && futures
          ? `Spot ${spot.winRate.toFixed(0)}% · Fut ${futures.winRate.toFixed(0)}%`
          : undefined,
    },
    {
      label: "Open Positions",
      value: openTrades,
      decimals: 0,
      icon: <Activity className="h-4 w-4" />,
      tone: "neu" as const,
      footer:
        allocated > 0
          ? spot && futures
            ? `$${allocated.toFixed(0)} allocated · ${spot.open}S/${futures.open}F`
            : `$${allocated.toFixed(0)} allocated`
          : undefined,
    },
  ];

  // Row 2: Book-specific cards (only when data is provided)
  const bookCards =
    spot && futures
      ? [
          {
            label: "Spot Book",
            value: spot.equity,
            prefix: "$",
            decimals: 0,
            icon: <Layers className="h-4 w-4" />,
            tone: "neu" as const,
            footer: `${spot.open} open · PnL ${spot.realizedPnl >= 0 ? "+" : ""}$${spot.realizedPnl.toFixed(0)} · ${spot.closed} closed`,
            accent: "spot" as const,
          },
          {
            label: "Futures Book",
            value: futures.equity,
            prefix: "$",
            decimals: 0,
            icon: <Zap className="h-4 w-4" />,
            tone: "neu" as const,
            footer: `${futures.open} open · PnL ${futures.realizedPnl >= 0 ? "+" : ""}$${futures.realizedPnl.toFixed(0)} · ${futures.closed} closed`,
            accent: "futures" as const,
          },
        ]
      : [];

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {kpis.map((k, i) => (
          <motion.div
            key={k.label}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.08, duration: 0.4 }}
          >
            <Card className="overflow-hidden border-border/50 bg-card/50 backdrop-blur">
              <CardContent className="p-5">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs uppercase tracking-wider text-muted-foreground">
                    {k.label}
                  </span>
                  <span
                    className={cn(
                      "rounded-md p-1.5",
                      k.tone === "pos" && "bg-emerald-500/10 text-emerald-500",
                      k.tone === "neg" && "bg-rose-500/10 text-rose-500",
                      k.tone === "neu" && "bg-muted text-muted-foreground"
                    )}
                  >
                    {k.icon}
                  </span>
                </div>
                <div
                  className={cn(
                    "text-2xl font-semibold tabular-nums tracking-tight",
                    k.tone === "pos" && "text-emerald-500",
                    k.tone === "neg" && "text-rose-500"
                  )}
                >
                  <AnimatedNumber
                    value={Math.abs(k.value) === Infinity ? 0 : k.value}
                    decimals={k.decimals ?? 2}
                    prefix={k.prefix ?? ""}
                    suffix={k.suffix ?? ""}
                  />
                </div>
                {k.footer && (
                  <div className="text-xs text-muted-foreground mt-1 tabular-nums">{k.footer}</div>
                )}
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </div>

      {bookCards.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {bookCards.map((k, i) => (
            <motion.div
              key={k.label}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.35 + i * 0.08, duration: 0.4 }}
            >
              <Card
                className={cn(
                  "overflow-hidden border-border/50 bg-card/50 backdrop-blur relative",
                  k.accent === "spot" && "border-l-2 border-l-sky-500/60",
                  k.accent === "futures" && "border-l-2 border-l-amber-500/60"
                )}
              >
                <CardContent className="p-5">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="text-xs uppercase tracking-wider text-muted-foreground">
                        {k.label}
                      </span>
                      <span
                        className={cn(
                          "text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded",
                          k.accent === "spot" && "bg-sky-500/10 text-sky-500",
                          k.accent === "futures" && "bg-amber-500/10 text-amber-500"
                        )}
                      >
                        {k.accent === "spot" ? "long-term" : "tactical"}
                      </span>
                    </div>
                    <span
                      className={cn(
                        "rounded-md p-1.5",
                        k.accent === "spot" && "bg-sky-500/10 text-sky-500",
                        k.accent === "futures" && "bg-amber-500/10 text-amber-500"
                      )}
                    >
                      {k.icon}
                    </span>
                  </div>
                  <div className="text-xl font-semibold tabular-nums tracking-tight">
                    <AnimatedNumber
                      value={k.value}
                      decimals={k.decimals ?? 0}
                      prefix={k.prefix ?? ""}
                    />
                  </div>
                  <div className="text-xs text-muted-foreground mt-1 tabular-nums">{k.footer}</div>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}
