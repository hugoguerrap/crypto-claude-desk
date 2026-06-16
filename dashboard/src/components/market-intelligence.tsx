"use client";

import { motion } from "framer-motion";
import { TrendingDown, TrendingUp, Activity, Brain, Coins, Droplet } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import type { PolymarketSnapshot, DefiFlowSnapshot } from "@/lib/market-intelligence";

function formatBillions(n: number | null): string {
  if (n == null) return "—";
  if (n >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(2)}M`;
  return `$${n.toLocaleString()}`;
}

export function MarketIntelligence({
  polymarket,
  defi,
}: {
  polymarket: PolymarketSnapshot[];
  defi: DefiFlowSnapshot;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.45, duration: 0.5 }}
      className="grid grid-cols-1 lg:grid-cols-2 gap-6"
    >
      <DefiFlowsCard defi={defi} />
      <PolymarketCard markets={polymarket} />
    </motion.div>
  );
}

function DefiFlowsCard({ defi }: { defi: DefiFlowSnapshot }) {
  const flow = defi.ethFlowClassification;
  const flowTone =
    flow === "STRONG_INFLOW" || flow === "INFLOW"
      ? "pos"
      : flow === "STRONG_OUTFLOW" || flow === "OUTFLOW"
      ? "neg"
      : "neu";
  const dexUp = (defi.dexVolume24hChangePct ?? 0) >= 0;

  return (
    <Card className="border-border/50 bg-card/50 backdrop-blur">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base font-medium">
          <Droplet className="h-4 w-4 text-cyan-400" />
          On-Chain Flows
          <Badge variant="outline" className="ml-auto text-[10px] font-normal">
            DefiLlama
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <Metric label="Total TVL" value={formatBillions(defi.totalTvlUsd)} icon={<Activity className="h-3 w-3" />} />
          <Metric
            label="Stablecoins"
            value={formatBillions(defi.stablecoinMcapUsd)}
            icon={<Coins className="h-3 w-3" />}
          />
        </div>

        <div className="rounded-md border border-border/40 bg-background/40 p-3 space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground uppercase tracking-wider">ETH TVL · 7d</span>
            <Badge
              variant="outline"
              className={cn(
                "text-[10px] uppercase tracking-wider font-semibold",
                flowTone === "pos" && "border-emerald-500/30 text-emerald-500 bg-emerald-500/5",
                flowTone === "neg" && "border-rose-500/30 text-rose-500 bg-rose-500/5",
                flowTone === "neu" && "border-muted text-muted-foreground"
              )}
            >
              {flow ?? "—"}
            </Badge>
          </div>
          <div className="flex items-baseline justify-between">
            <span className="text-2xl font-semibold tabular-nums">
              {formatBillions(defi.ethTvlUsd)}
            </span>
            <span
              className={cn(
                "text-sm tabular-nums font-medium",
                (defi.ethTvlChange7dPct ?? 0) >= 0 ? "text-emerald-500" : "text-rose-500"
              )}
            >
              {defi.ethTvlChange7dPct != null
                ? `${defi.ethTvlChange7dPct >= 0 ? "+" : ""}${defi.ethTvlChange7dPct.toFixed(2)}%`
                : "—"}
            </span>
          </div>
        </div>

        <div className="rounded-md border border-border/40 bg-background/40 p-3 space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground uppercase tracking-wider">DEX Volume · 24h</span>
            <span
              className={cn(
                "flex items-center gap-1 text-xs tabular-nums font-medium",
                dexUp ? "text-emerald-500" : "text-rose-500"
              )}
            >
              {dexUp ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
              {defi.dexVolume24hChangePct != null
                ? `${defi.dexVolume24hChangePct >= 0 ? "+" : ""}${defi.dexVolume24hChangePct.toFixed(2)}%`
                : "—"}
            </span>
          </div>
          <div className="flex items-baseline justify-between">
            <span className="text-2xl font-semibold tabular-nums">
              {formatBillions(defi.dexVolume24hUsd)}
            </span>
            {defi.topDex && (
              <span className="text-xs text-muted-foreground">
                top: <span className="text-foreground/80 font-medium">{defi.topDex.name}</span>
              </span>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function PolymarketCard({ markets }: { markets: PolymarketSnapshot[] }) {
  return (
    <Card className="border-border/50 bg-card/50 backdrop-blur">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base font-medium">
          <Brain className="h-4 w-4 text-violet-400" />
          Polymarket Consensus
          <Badge variant="outline" className="ml-auto text-[10px] font-normal">
            crypto · 24h vol
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {markets.length === 0 ? (
          <div className="text-xs text-muted-foreground py-8 text-center">
            Polymarket data unavailable right now.
          </div>
        ) : (
          <ScrollArea className="h-72 pr-3">
            <div className="space-y-2">
              {markets.map((m) => {
                const pct = m.leader_pct ?? 0;
                const tone =
                  pct >= 75 ? "pos" : pct <= 25 ? "neg" : pct >= 55 ? "info" : "neu";
                return (
                  <div
                    key={m.slug}
                    className="rounded-md border border-border/40 bg-background/40 p-3 text-xs space-y-1.5"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <span className="text-foreground/90 leading-snug font-medium pr-2">
                        {m.question}
                      </span>
                      <Badge
                        variant="outline"
                        className={cn(
                          "shrink-0 tabular-nums text-[10px] font-semibold",
                          tone === "pos" && "border-emerald-500/30 text-emerald-500 bg-emerald-500/5",
                          tone === "neg" && "border-rose-500/30 text-rose-500 bg-rose-500/5",
                          tone === "info" && "border-violet-500/30 text-violet-400 bg-violet-500/5",
                          tone === "neu" && "border-amber-500/30 text-amber-500 bg-amber-500/5"
                        )}
                      >
                        {m.leader ?? "—"} · {pct.toFixed(0)}%
                      </Badge>
                    </div>
                    <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                      <span>vol {formatBillions(m.volume_usd)}</span>
                      {m.end_date && (
                        <span>
                          ends {new Date(m.end_date).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </ScrollArea>
        )}
      </CardContent>
    </Card>
  );
}

function Metric({
  label,
  value,
  icon,
}: {
  label: string;
  value: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="rounded-md border border-border/40 bg-background/40 p-3">
      <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-muted-foreground">
        {icon}
        {label}
      </div>
      <div className="mt-1 text-xl font-semibold tabular-nums">{value}</div>
    </div>
  );
}
