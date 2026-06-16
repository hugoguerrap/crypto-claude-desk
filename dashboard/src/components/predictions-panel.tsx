"use client";

import { motion } from "framer-motion";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { shortDate } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Prediction } from "@/lib/db";

type Accuracy = {
  total: number;
  correct: number;
  partial: number;
  wrong: number;
  pending: number;
  accuracy: number;
};

export function PredictionsPanel({
  predictions,
  accuracy,
}: {
  predictions: Prediction[];
  accuracy: Accuracy;
}) {
  const validated = accuracy.correct + accuracy.partial + accuracy.wrong;
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.55, duration: 0.5 }}
    >
      <Card className="border-border/50 bg-card/50 backdrop-blur h-full">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base font-medium">Predictions</CardTitle>
            <Badge variant="outline" className="font-normal">
              {accuracy.pending} pending
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {validated > 0 ? (
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs uppercase tracking-wider text-muted-foreground">
                  Accuracy
                </span>
                <span className="text-sm tabular-nums font-medium">
                  {accuracy.accuracy.toFixed(1)}%
                </span>
              </div>
              <div className="h-2 rounded-full bg-muted overflow-hidden flex">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${(accuracy.correct / validated) * 100}%` }}
                  transition={{ duration: 0.8 }}
                  className="bg-emerald-500"
                />
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${(accuracy.partial / validated) * 100}%` }}
                  transition={{ duration: 0.8, delay: 0.1 }}
                  className="bg-amber-500"
                />
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${(accuracy.wrong / validated) * 100}%` }}
                  transition={{ duration: 0.8, delay: 0.2 }}
                  className="bg-rose-500"
                />
              </div>
              <div className="flex items-center gap-3 mt-2 text-[11px] text-muted-foreground">
                <span className="flex items-center gap-1">
                  <span className="h-2 w-2 rounded-full bg-emerald-500" /> {accuracy.correct} correct
                </span>
                <span className="flex items-center gap-1">
                  <span className="h-2 w-2 rounded-full bg-amber-500" /> {accuracy.partial} partial
                </span>
                <span className="flex items-center gap-1">
                  <span className="h-2 w-2 rounded-full bg-rose-500" /> {accuracy.wrong} wrong
                </span>
              </div>
            </div>
          ) : (
            <div className="text-xs text-muted-foreground py-2">
              No validated predictions yet. Accuracy will appear here once trades close and predictions are evaluated.
            </div>
          )}

          <div className="border-t border-border/40 pt-3">
            <div className="text-xs uppercase tracking-wider text-muted-foreground mb-2">
              Recent
            </div>
            {predictions.length === 0 ? (
              <div className="text-xs text-muted-foreground py-4 text-center">
                No predictions logged yet
              </div>
            ) : (
              <ScrollArea className="h-64 pr-3">
                <div className="space-y-2">
                  {predictions.slice(0, 20).map((p) => (
                    <div
                      key={p.id}
                      className="rounded-md border border-border/50 bg-background/40 p-3 text-xs"
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-medium">{p.symbol}</span>
                        <Badge
                          variant="outline"
                          className={cn(
                            "text-[10px] uppercase tracking-wider",
                            p.status === "pending" && "border-blue-500/30 text-blue-500",
                            p.status === "validated_correct" && "border-emerald-500/30 text-emerald-500",
                            p.status === "validated_partial" && "border-amber-500/30 text-amber-500",
                            p.status === "validated_wrong" && "border-rose-500/30 text-rose-500"
                          )}
                        >
                          {p.status.replace("validated_", "")}
                        </Badge>
                      </div>
                      <div className="text-foreground/80 leading-relaxed mb-1.5">
                        {p.prediction}
                      </div>
                      <div className="flex items-center justify-between text-muted-foreground">
                        <span>by {p.agent}</span>
                        <span className="tabular-nums">{shortDate(p.created_at)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </ScrollArea>
            )}
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}
