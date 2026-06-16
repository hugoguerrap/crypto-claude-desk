import Link from "next/link";
import { getAllReports } from "@/lib/db";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { FileText, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export default async function ReportsPage() {
  const reports = getAllReports();

  return (
    <div className="mx-auto max-w-7xl px-6 py-8 space-y-6">
      <PageHeader
        eyebrow="Archive"
        title="Reports"
        subtitle={`${reports.length} analysis report${reports.length === 1 ? "" : "s"} generated`}
      />

      {reports.length === 0 ? (
        <Card className="border-border/50 bg-card/50 backdrop-blur">
          <CardContent className="py-16 text-center">
            <FileText className="h-8 w-8 mx-auto text-muted-foreground/40 mb-3" />
            <div className="text-sm font-medium mb-1">No reports yet</div>
            <div className="text-xs text-muted-foreground">
              Reports are saved under <code className="px-1 py-0.5 rounded bg-muted">data/reports/</code> when{" "}
              <code className="px-1 py-0.5 rounded bg-muted">/analyze</code> runs.
            </div>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {reports.map((r) => (
            <Link key={r.slug} href={`/reports/${r.slug}`}>
              <Card className="border-border/50 bg-card/50 backdrop-blur hover:bg-card/70 hover:border-border transition-all group h-full">
                <CardContent className="p-5">
                  <div className="flex items-start justify-between mb-3">
                    <div>
                      <div className="text-xs uppercase tracking-wider text-muted-foreground">
                        {r.date}
                      </div>
                      <div className="text-lg font-semibold mt-0.5">{r.symbol}</div>
                    </div>
                    {r.verdict && (
                      <Badge
                        variant="outline"
                        className={cn(
                          "text-[10px] uppercase tracking-wider font-semibold",
                          r.verdict === "EXECUTE" && "border-emerald-500/30 text-emerald-500 bg-emerald-500/5",
                          r.verdict === "WAIT" && "border-amber-500/30 text-amber-500 bg-amber-500/5",
                          r.verdict === "REJECT" && "border-rose-500/30 text-rose-500 bg-rose-500/5"
                        )}
                      >
                        {r.verdict}
                      </Badge>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-1.5 mb-3">
                    {r.files.map((f) => (
                      <Badge
                        key={f}
                        variant="outline"
                        className="font-mono text-[10px] font-normal"
                      >
                        {f.replace(".md", "")}
                      </Badge>
                    ))}
                  </div>
                  <div className="flex items-center justify-between text-xs text-muted-foreground border-t border-border/40 pt-3">
                    <span>{r.files.length} file{r.files.length === 1 ? "" : "s"}</span>
                    <ChevronRight className="h-4 w-4 group-hover:translate-x-0.5 transition-transform" />
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
