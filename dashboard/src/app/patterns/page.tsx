import { getPatterns } from "@/lib/db";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { pct, shortDate } from "@/lib/format";
import { Sparkles } from "lucide-react";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export default async function PatternsPage() {
  const patterns = getPatterns();
  const total = patterns.length;
  const profitable = patterns.filter((p) => p.win_rate >= 0.5).length;

  return (
    <div className="mx-auto max-w-7xl px-6 py-8 space-y-6">
      <PageHeader
        eyebrow="Strategy Library"
        title="Patterns"
        subtitle={`${total} pattern${total === 1 ? "" : "s"} identified · ${profitable} with >50% win rate`}
      />

      {total === 0 ? (
        <Card className="border-border/50 bg-card/50 backdrop-blur">
          <CardContent className="py-16 text-center">
            <Sparkles className="h-8 w-8 mx-auto text-muted-foreground/40 mb-3" />
            <div className="text-sm font-medium mb-1">No patterns identified yet</div>
            <div className="text-xs text-muted-foreground max-w-md mx-auto">
              Patterns emerge when the system observes repeated setups across trades. Once closed
              trades start accumulating, the learning agent will name and track them here with their
              win rates and average PnL.
            </div>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {patterns.map((p) => {
            const wr = p.win_rate * 100;
            return (
              <Card
                key={p.name}
                className="border-border/50 bg-card/50 backdrop-blur hover:bg-card/70 transition-colors"
              >
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between gap-2">
                    <CardTitle className="text-base font-medium leading-tight">
                      {p.name}
                    </CardTitle>
                    <span
                      className={`text-xs tabular-nums font-semibold ${
                        wr >= 60 ? "text-emerald-500" : wr >= 40 ? "text-amber-500" : "text-rose-500"
                      }`}
                    >
                      {wr.toFixed(0)}%
                    </span>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3 text-xs">
                  <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${
                        wr >= 60 ? "bg-emerald-500" : wr >= 40 ? "bg-amber-500" : "bg-rose-500"
                      }`}
                      style={{ width: `${wr}%` }}
                    />
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-center">
                    <Stat label="Runs" value={p.occurrences.toString()} />
                    <Stat label="W/L" value={`${p.wins}/${p.losses}`} />
                    <Stat label="Avg PnL" value={pct(p.avg_pnl_percent)} />
                  </div>
                  {p.recommendation && (
                    <p className="text-foreground/70 italic border-l-2 border-violet-500/40 pl-3 leading-snug">
                      {p.recommendation}
                    </p>
                  )}
                  <div className="flex items-center justify-between text-[10px] text-muted-foreground pt-1">
                    <span>First seen {shortDate(p.first_seen)}</span>
                    <span>Last {shortDate(p.last_seen)}</span>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="text-sm tabular-nums font-medium">{value}</div>
    </div>
  );
}
