"use client";

import { Fragment, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronRight } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";
import { money, pct, shortDate } from "@/lib/format";
import type { Trade } from "@/lib/db";

export function TradesTable({ trades }: { trades: Trade[] }) {
  const [expanded, setExpanded] = useState<string | null>(null);

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.5, duration: 0.5 }}
    >
      <Card className="border-border/50 bg-card/50 backdrop-blur">
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-medium">Recent Trades</CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          {trades.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <div className="text-sm text-muted-foreground">No trades yet</div>
              <div className="text-xs text-muted-foreground/60 mt-1">
                Run <code className="px-1 py-0.5 rounded bg-muted text-foreground/80">/analyze</code> or{" "}
                <code className="px-1 py-0.5 rounded bg-muted text-foreground/80">/loop /monitor</code> to start
                generating trades
              </div>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow className="hover:bg-transparent border-border/50">
                  <TableHead className="w-8" />
                  <TableHead>Symbol</TableHead>
                  <TableHead>Side</TableHead>
                  <TableHead>Book</TableHead>
                  <TableHead className="text-right">Entry</TableHead>
                  <TableHead className="text-right">Exit</TableHead>
                  <TableHead className="text-right">PnL</TableHead>
                  <TableHead className="text-right">Risk (SL / TP)</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Opened</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {trades.map((t) => {
                  const isOpen = t.status === "open";
                  const isWin = t.result === "win";
                  const isLoss = t.result === "loss";
                  return (
                    <Fragment key={t.id}>
                      <TableRow
                        onClick={() => setExpanded(expanded === t.id ? null : t.id)}
                        className="cursor-pointer border-border/50 hover:bg-muted/30"
                      >
                        <TableCell>
                          <ChevronRight
                            className={cn(
                              "h-4 w-4 text-muted-foreground transition-transform duration-200",
                              expanded === t.id && "rotate-90"
                            )}
                          />
                        </TableCell>
                        <TableCell className="font-medium">{t.symbol}</TableCell>
                        <TableCell>
                          <Badge
                            variant="outline"
                            className={cn(
                              "uppercase text-[10px] tracking-wider font-medium",
                              t.side === "long"
                                ? "border-emerald-500/30 text-emerald-500 bg-emerald-500/5"
                                : "border-rose-500/30 text-rose-500 bg-rose-500/5"
                            )}
                          >
                            {t.side}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant="outline"
                            className={cn(
                              "uppercase text-[10px] tracking-wider font-medium",
                              t.portfolio_type === "futures"
                                ? "border-amber-500/30 text-amber-500 bg-amber-500/5"
                                : "border-sky-500/30 text-sky-500 bg-sky-500/5"
                            )}
                          >
                            {t.portfolio_type === "futures" ? `fut ${t.leverage}x` : "spot"}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right tabular-nums">{money(t.entry_price)}</TableCell>
                        <TableCell className="text-right tabular-nums text-muted-foreground">
                          {t.exit_price != null ? money(t.exit_price) : "—"}
                        </TableCell>
                        <TableCell
                          className={cn(
                            "text-right tabular-nums font-medium",
                            isWin && "text-emerald-500",
                            isLoss && "text-rose-500",
                            !t.pnl_usd && "text-muted-foreground"
                          )}
                        >
                          {t.pnl_usd != null
                            ? `${money(t.pnl_usd)} (${pct(t.pnl_percent ?? 0)})`
                            : "—"}
                        </TableCell>
                        <TableCell className="text-right">
                          <RiskCell trade={t} />
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant="outline"
                            className={cn(
                              "text-[10px] uppercase tracking-wider",
                              isOpen && "border-blue-500/30 text-blue-500 bg-blue-500/5",
                              isWin && "border-emerald-500/30 text-emerald-500 bg-emerald-500/5",
                              isLoss && "border-rose-500/30 text-rose-500 bg-rose-500/5"
                            )}
                          >
                            {t.status}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground tabular-nums">
                          {shortDate(t.opened_at)}
                        </TableCell>
                      </TableRow>
                      <AnimatePresence>
                        {expanded === t.id && (
                          <TableRow className="border-border/50 hover:bg-transparent">
                            <TableCell colSpan={10} className="p-0">
                              <motion.div
                                initial={{ height: 0, opacity: 0 }}
                                animate={{ height: "auto", opacity: 1 }}
                                exit={{ height: 0, opacity: 0 }}
                                transition={{ duration: 0.2 }}
                                className="overflow-hidden"
                              >
                                <div className="px-6 py-4 bg-muted/20 space-y-3 text-sm">
                                  <DetailRow label="Strategy" value={t.strategy_type ?? "—"} />
                                  <DetailRow
                                    label="Stop / Take"
                                    value={`${t.stop_loss != null ? money(t.stop_loss) : "—"} / ${
                                      t.take_profit != null ? money(t.take_profit) : "—"
                                    }`}
                                  />
                                  <DetailRow label="Position size" value={money(t.usd_amount)} />
                                  <DetailRow label="Close reason" value={t.close_reason ?? "—"} />
                                  {t.reasoning && (
                                    <div>
                                      <div className="text-xs uppercase tracking-wider text-muted-foreground mb-1">
                                        Reasoning
                                      </div>
                                      <div className="text-foreground/80 whitespace-pre-wrap leading-relaxed">
                                        {t.reasoning}
                                      </div>
                                    </div>
                                  )}
                                  {t.learning && (
                                    <div>
                                      <div className="text-xs uppercase tracking-wider text-muted-foreground mb-1">
                                        Learning
                                      </div>
                                      <div className="text-foreground/80 whitespace-pre-wrap leading-relaxed">
                                        {t.learning}
                                      </div>
                                    </div>
                                  )}
                                </div>
                              </motion.div>
                            </TableCell>
                          </TableRow>
                        )}
                      </AnimatePresence>
                    </Fragment>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </motion.div>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between border-b border-border/30 pb-2 last:border-0 last:pb-0">
      <span className="text-xs uppercase tracking-wider text-muted-foreground">{label}</span>
      <span className="text-foreground/90 tabular-nums">{value}</span>
    </div>
  );
}

/**
 * Compact two-line risk cell. Open trades show distance % to SL/TP from
 * the entry price — closed trades show just the static values so you can
 * post-mortem whether the SL did its job. Missing fields render as "—".
 */
function RiskCell({ trade }: { trade: Trade }) {
  const sl = trade.stop_loss;
  const tp = trade.take_profit;
  const entry = trade.entry_price;
  const isShort = trade.side === "short";

  if (sl == null && tp == null) {
    return <span className="text-xs text-muted-foreground">—</span>;
  }

  // Distance from entry (signed, in the trade's profit direction)
  const slPct = sl != null ? ((sl - entry) / entry) * 100 * (isShort ? -1 : 1) : null;
  const tpPct = tp != null ? ((tp - entry) / entry) * 100 * (isShort ? -1 : 1) : null;
  const showDistance = trade.status === "open";

  return (
    <div className="inline-flex flex-col items-end leading-tight tabular-nums">
      <span className="text-[11px]">
        <span className="text-rose-500/80 mr-1">SL</span>
        <span className="text-foreground/90">{sl != null ? money(sl) : "—"}</span>
        {showDistance && slPct != null && (
          <span className="text-muted-foreground ml-1 text-[10px]">
            ({slPct >= 0 ? "+" : ""}
            {slPct.toFixed(1)}%)
          </span>
        )}
      </span>
      <span className="text-[11px]">
        <span className="text-emerald-500/80 mr-1">TP</span>
        <span className="text-foreground/90">{tp != null ? money(tp) : "—"}</span>
        {showDistance && tpPct != null && (
          <span className="text-muted-foreground ml-1 text-[10px]">
            ({tpPct >= 0 ? "+" : ""}
            {tpPct.toFixed(1)}%)
          </span>
        )}
      </span>
    </div>
  );
}
