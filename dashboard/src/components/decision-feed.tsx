"use client";

import { motion } from "framer-motion";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Brain } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import type { LatestDecision } from "@/lib/db";

export function DecisionFeed({ decision }: { decision: LatestDecision | null }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.65, duration: 0.5 }}
    >
      <Card className="border-border/50 bg-card/50 backdrop-blur">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2 text-base font-medium">
              <Brain className="h-4 w-4 text-violet-400" />
              Latest Decision
            </CardTitle>
            {decision && (
              <div className="flex items-center gap-2">
                <Badge variant="outline" className="font-mono text-[10px]">
                  {decision.symbol}
                </Badge>
                <Badge
                  variant="outline"
                  className={cn(
                    "text-[10px] uppercase tracking-wider font-semibold",
                    decision.verdict === "EXECUTE" && "border-emerald-500/30 text-emerald-500 bg-emerald-500/5",
                    decision.verdict === "WAIT" && "border-amber-500/30 text-amber-500 bg-amber-500/5",
                    decision.verdict === "REJECT" && "border-rose-500/30 text-rose-500 bg-rose-500/5"
                  )}
                >
                  {decision.verdict ?? "—"}
                </Badge>
              </div>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {!decision ? (
            <div className="text-xs text-muted-foreground py-8 text-center">
              No analysis reports found in <code className="px-1 py-0.5 rounded bg-muted">data/reports/</code> yet.
            </div>
          ) : (
            <ScrollArea className="h-96 pr-3">
              <article className="prose prose-sm prose-invert max-w-none prose-headings:font-semibold prose-headings:text-foreground prose-p:text-foreground/80 prose-strong:text-foreground prose-code:text-violet-400 prose-code:bg-muted prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:before:hidden prose-code:after:hidden prose-table:text-xs prose-th:text-foreground prose-td:text-foreground/80">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{decision.content}</ReactMarkdown>
              </article>
            </ScrollArea>
          )}
        </CardContent>
      </Card>
    </motion.div>
  );
}
