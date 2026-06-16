"use client";

import { motion } from "framer-motion";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { pct } from "@/lib/format";
import type { Pattern } from "@/lib/db";

export function PatternsPanel({ patterns }: { patterns: Pattern[] }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.6, duration: 0.5 }}
    >
      <Card className="border-border/50 bg-card/50 backdrop-blur h-full">
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-medium">Patterns</CardTitle>
        </CardHeader>
        <CardContent>
          {patterns.length === 0 ? (
            <div className="text-xs text-muted-foreground py-8 text-center">
              No patterns identified yet. Patterns emerge from repeated trade setups.
            </div>
          ) : (
            <div className="space-y-3">
              {patterns.slice(0, 8).map((p, i) => (
                <motion.div
                  key={p.name}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.6 + i * 0.05 }}
                  className="space-y-1.5"
                >
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-medium truncate pr-2">{p.name}</span>
                    <span className="tabular-nums text-xs text-muted-foreground shrink-0">
                      {p.occurrences} runs · {pct(p.avg_pnl_percent)}
                    </span>
                  </div>
                  <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${p.win_rate * 100}%` }}
                      transition={{ duration: 0.8, delay: 0.6 + i * 0.05 }}
                      className={`h-full rounded-full ${
                        p.win_rate >= 0.6
                          ? "bg-emerald-500"
                          : p.win_rate >= 0.4
                          ? "bg-amber-500"
                          : "bg-rose-500"
                      }`}
                    />
                  </div>
                  <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                    <span>{(p.win_rate * 100).toFixed(0)}% win rate</span>
                    <span>{p.wins}W / {p.losses}L</span>
                  </div>
                </motion.div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </motion.div>
  );
}
