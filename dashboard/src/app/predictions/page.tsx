import { getPredictions, getPredictionAccuracy } from "@/lib/db";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { shortDate } from "@/lib/format";
import { cn } from "@/lib/utils";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export default async function PredictionsPage() {
  const predictions = getPredictions(undefined, 200);
  const accuracy = getPredictionAccuracy();
  const validated = accuracy.correct + accuracy.partial + accuracy.wrong;

  const byAgent = predictions.reduce<Record<string, number>>((acc, p) => {
    acc[p.agent] = (acc[p.agent] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div className="mx-auto max-w-7xl px-6 py-8 space-y-6">
      <PageHeader
        eyebrow="Forecasts"
        title="Predictions"
        subtitle={`${accuracy.total} logged · ${accuracy.pending} pending · ${validated} validated`}
      />

      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <AccuracyStat label="Accuracy" value={validated > 0 ? `${accuracy.accuracy.toFixed(1)}%` : "—"} highlight />
        <AccuracyStat label="Correct" value={accuracy.correct.toString()} tone="pos" />
        <AccuracyStat label="Partial" value={accuracy.partial.toString()} tone="amber" />
        <AccuracyStat label="Wrong" value={accuracy.wrong.toString()} tone="neg" />
        <AccuracyStat label="Pending" value={accuracy.pending.toString()} tone="info" />
      </div>

      {Object.keys(byAgent).length > 0 && (
        <Card className="border-border/50 bg-card/50 backdrop-blur">
          <CardHeader className="pb-3">
            <CardTitle className="text-base font-medium">By Agent</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {Object.entries(byAgent).map(([agent, n]) => (
                <Badge key={agent} variant="outline" className="font-normal">
                  <span className="font-medium mr-1.5">{agent}</span>
                  <span className="text-muted-foreground">{n}</span>
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      <Card className="border-border/50 bg-card/50 backdrop-blur">
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-medium">All Predictions</CardTitle>
        </CardHeader>
        <CardContent>
          {predictions.length === 0 ? (
            <div className="py-12 text-center text-sm text-muted-foreground">
              No predictions logged yet.
            </div>
          ) : (
            <div className="space-y-3">
              {predictions.map((p) => (
                <div
                  key={p.id}
                  className="rounded-md border border-border/40 bg-background/40 p-4 space-y-2"
                >
                  <div className="flex items-center justify-between gap-3 flex-wrap">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-sm">{p.symbol}</span>
                      <Badge variant="outline" className="font-mono text-[10px]">
                        {p.id}
                      </Badge>
                      <Badge variant="outline" className="font-normal text-[10px]">
                        {p.prediction_type.replace(/_/g, " ")}
                      </Badge>
                    </div>
                    <Badge
                      variant="outline"
                      className={cn(
                        "text-[10px] uppercase tracking-wider",
                        p.status === "pending" && "border-blue-500/30 text-blue-500 bg-blue-500/5",
                        p.status === "validated_correct" && "border-emerald-500/30 text-emerald-500 bg-emerald-500/5",
                        p.status === "validated_partial" && "border-amber-500/30 text-amber-500 bg-amber-500/5",
                        p.status === "validated_wrong" && "border-rose-500/30 text-rose-500 bg-rose-500/5"
                      )}
                    >
                      {p.status.replace("validated_", "")}
                    </Badge>
                  </div>
                  <p className="text-sm text-foreground/80 leading-relaxed">{p.prediction}</p>
                  <div className="flex items-center justify-between text-[11px] text-muted-foreground pt-1 border-t border-border/30">
                    <span>
                      by <span className="font-medium text-foreground/70">{p.agent}</span>
                      {p.confidence != null && (
                        <span className="ml-2">conf. {(p.confidence * 100).toFixed(0)}%</span>
                      )}
                      {p.timeframe_hours != null && p.timeframe_hours > 0 && (
                        <span className="ml-2">{p.timeframe_hours}h horizon</span>
                      )}
                    </span>
                    <span className="tabular-nums">{shortDate(p.created_at)}</span>
                  </div>
                  {p.evaluation && (
                    <div className="text-xs text-foreground/70 bg-muted/30 rounded p-2 mt-2">
                      <span className="text-muted-foreground uppercase tracking-wider text-[10px]">
                        Evaluation:{" "}
                      </span>
                      {p.evaluation}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function AccuracyStat({
  label,
  value,
  tone = "neu",
  highlight = false,
}: {
  label: string;
  value: string;
  tone?: "pos" | "neg" | "neu" | "amber" | "info";
  highlight?: boolean;
}) {
  return (
    <Card
      className={cn(
        "border-border/50 bg-card/50 backdrop-blur",
        highlight && "border-violet-500/30 bg-violet-500/5"
      )}
    >
      <CardContent className="p-5">
        <div className="text-xs uppercase tracking-wider text-muted-foreground mb-2">
          {label}
        </div>
        <div
          className={cn(
            "text-2xl font-semibold tabular-nums",
            tone === "pos" && "text-emerald-500",
            tone === "neg" && "text-rose-500",
            tone === "amber" && "text-amber-500",
            tone === "info" && "text-blue-500"
          )}
        >
          {value}
        </div>
      </CardContent>
    </Card>
  );
}
