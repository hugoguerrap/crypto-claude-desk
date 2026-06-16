import Link from "next/link";
import { notFound } from "next/navigation";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ChevronLeft } from "lucide-react";
import { getReportContent } from "@/lib/db";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export default async function ReportDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const report = getReportContent(slug);
  if (!report) notFound();

  const labelOf = (name: string) => name.replace(".md", "").replace(/-/g, " ");

  return (
    <div className="mx-auto max-w-5xl px-6 py-8 space-y-6">
      <div>
        <Link
          href="/reports"
          className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors mb-3"
        >
          <ChevronLeft className="h-3.5 w-3.5" />
          All reports
        </Link>
        <PageHeader
          eyebrow={report.date}
          title={report.symbol || report.slug}
          subtitle={`${report.files.length} report file${report.files.length === 1 ? "" : "s"}`}
        >
          {report.verdict && (
            <Badge
              variant="outline"
              className={cn(
                "text-xs uppercase tracking-wider font-semibold",
                report.verdict === "EXECUTE" && "border-emerald-500/30 text-emerald-500 bg-emerald-500/5",
                report.verdict === "WAIT" && "border-amber-500/30 text-amber-500 bg-amber-500/5",
                report.verdict === "REJECT" && "border-rose-500/30 text-rose-500 bg-rose-500/5"
              )}
            >
              {report.verdict}
            </Badge>
          )}
        </PageHeader>
      </div>

      <Card className="border-border/50 bg-card/50 backdrop-blur">
        <CardContent className="p-2">
          <Tabs defaultValue={report.files[0]?.name}>
            <TabsList className="w-full justify-start overflow-x-auto bg-muted/40 p-1 h-auto flex-wrap">
              {report.files.map((f) => (
                <TabsTrigger
                  key={f.name}
                  value={f.name}
                  className="text-xs capitalize font-mono data-[state=active]:bg-background"
                >
                  {labelOf(f.name)}
                </TabsTrigger>
              ))}
            </TabsList>
            {report.files.map((f) => (
              <TabsContent key={f.name} value={f.name} className="mt-4 px-4 pb-4">
                <article className="prose prose-sm prose-invert max-w-none prose-headings:font-semibold prose-headings:text-foreground prose-p:text-foreground/80 prose-strong:text-foreground prose-code:text-violet-400 prose-code:bg-muted prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:before:hidden prose-code:after:hidden prose-table:text-xs prose-th:text-foreground prose-td:text-foreground/80 prose-li:text-foreground/80">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{f.content}</ReactMarkdown>
                </article>
              </TabsContent>
            ))}
          </Tabs>
        </CardContent>
      </Card>
    </div>
  );
}
