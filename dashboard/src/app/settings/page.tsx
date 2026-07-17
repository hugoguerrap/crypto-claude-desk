import path from "node:path";
import fs from "node:fs";
import { getPortfolioState } from "@/lib/db";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { CheckCircle2, Database, Sparkles, Server } from "lucide-react";
import { money } from "@/lib/format";

export const dynamic = "force-dynamic";
export const revalidate = 0;

const MCP_SERVERS = [
  { name: "crypto-data", tools: 11, description: "Market metadata (CoinGecko)" },
  { name: "crypto-exchange", tools: 15, description: "CCXT multi-exchange data" },
  { name: "crypto-technical", tools: 14, description: "Indicators + signals" },
  { name: "crypto-futures", tools: 10, description: "Funding, OI, long/short ratios" },
  { name: "crypto-advanced-indicators", tools: 8, description: "OBV, MFI, ADX, Ichimoku" },
  { name: "crypto-market-microstructure", tools: 6, description: "Orderbook + spoofing" },
  { name: "crypto-learning-db", tools: 18, description: "SQLite cognitive memory" },
  { name: "crypto-polymarket", tools: 6, description: "Prediction market probabilities" },
  { name: "crypto-defillama", tools: 7, description: "TVL, stablecoins, DEX volume" },
];

const AGENTS = [
  { name: "market-monitor", model: "haiku", role: "Fast market data + arbitrage" },
  { name: "technical-analyst", model: "sonnet", role: "Indicators, patterns, signals" },
  { name: "news-sentiment", model: "sonnet", role: "News + social sentiment" },
  { name: "risk-specialist", model: "sonnet", role: "Risk, volatility, microstructure" },
  { name: "portfolio-manager", model: "opus", role: "Final decisions + execution" },
  { name: "learning-agent", model: "opus", role: "Predictions, patterns, post-mortem" },
  { name: "system-builder", model: "opus", role: "Generate new MCPs/agents/skills" },
];

export default async function SettingsPage() {
  const dbPath = path.resolve(process.cwd(), "..", "data", "db", "learning.db");
  const dbExists = fs.existsSync(dbPath);
  const dbStat = dbExists ? fs.statSync(dbPath) : null;
  const portfolio = getPortfolioState();

  return (
    <div className="mx-auto max-w-7xl px-6 py-8 space-y-6">
      <PageHeader
        eyebrow="System"
        title="Settings"
        subtitle="Configuration and status of the trading desk"
      />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="border-border/50 bg-card/50 backdrop-blur">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base font-medium">
              <Database className="h-4 w-4 text-violet-400" />
              Database
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <Row label="Path" value={<code className="text-xs">../data/db/learning.db</code>} />
            <Row
              label="Status"
              value={
                dbExists ? (
                  <span className="flex items-center gap-1.5 text-emerald-500 text-xs">
                    <CheckCircle2 className="h-3.5 w-3.5" /> Connected
                  </span>
                ) : (
                  <span className="text-rose-500 text-xs">Not found</span>
                )
              }
            />
            {dbStat && (
              <>
                <Row
                  label="Size"
                  value={`${(dbStat.size / 1024).toFixed(1)} KB`}
                />
                <Row
                  label="Last modified"
                  value={new Date(dbStat.mtime).toLocaleString()}
                />
              </>
            )}
            <Row label="Mode" value={<Badge variant="outline" className="text-[10px]">read-only</Badge>} />
          </CardContent>
        </Card>

        <Card className="border-border/50 bg-card/50 backdrop-blur">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base font-medium">
              <Sparkles className="h-4 w-4 text-emerald-400" />
              Portfolio
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <Row label="Spot initial" value={money(portfolio?.spot_initial ?? 0)} />
            <Row label="Spot balance" value={money(portfolio?.spot_balance ?? 0)} />
            <Row label="Futures initial" value={money(portfolio?.futures_initial ?? 0)} />
            <Row label="Futures balance" value={money(portfolio?.futures_balance ?? 0)} />
            <Row label="Currency" value={portfolio?.currency ?? "USD"} />
            <Row label="Trading mode" value={<Badge variant="outline" className="text-[10px] border-blue-500/30 text-blue-500">paper</Badge>} />
          </CardContent>
        </Card>
      </div>

      <Card className="border-border/50 bg-card/50 backdrop-blur">
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-base font-medium">
            <Server className="h-4 w-4 text-blue-400" />
            MCP Servers
            <Badge variant="outline" className="text-[10px] font-normal ml-1">
              {MCP_SERVERS.reduce((s, m) => s + m.tools, 0)} tools total
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-2 md:grid-cols-2">
            {MCP_SERVERS.map((m) => (
              <div
                key={m.name}
                className="flex items-center justify-between rounded-md border border-border/40 bg-background/40 px-3 py-2 text-sm"
              >
                <div className="flex flex-col">
                  <code className="text-xs font-medium">{m.name}</code>
                  <span className="text-[11px] text-muted-foreground">{m.description}</span>
                </div>
                <Badge variant="outline" className="text-[10px] font-normal">
                  {m.tools} tools
                </Badge>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card className="border-border/50 bg-card/50 backdrop-blur">
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-medium">Agents</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-2 md:grid-cols-2 lg:grid-cols-3">
            {AGENTS.map((a) => (
              <div
                key={a.name}
                className="flex items-center justify-between rounded-md border border-border/40 bg-background/40 px-3 py-2 text-sm"
              >
                <div className="flex flex-col">
                  <code className="text-xs font-medium">{a.name}</code>
                  <span className="text-[11px] text-muted-foreground">{a.role}</span>
                </div>
                <Badge
                  variant="outline"
                  className={`text-[10px] font-normal ${
                    a.model === "opus"
                      ? "border-violet-500/30 text-violet-400"
                      : a.model === "sonnet"
                      ? "border-blue-500/30 text-blue-400"
                      : "border-emerald-500/30 text-emerald-400"
                  }`}
                >
                  {a.model}
                </Badge>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between text-sm py-1.5 border-b border-border/30 last:border-0">
      <span className="text-xs uppercase tracking-wider text-muted-foreground">{label}</span>
      <span className="tabular-nums">{value}</span>
    </div>
  );
}
