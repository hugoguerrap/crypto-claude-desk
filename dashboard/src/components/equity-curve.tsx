"use client";

import { useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { motion } from "framer-motion";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

type Point = { t: string; equity: number; pnl: number };
type BookPoint = { t: string; spot: number; futures: number; total: number };

type View = "total" | "split";

export function EquityCurve({
  data,
  initial,
  byBook,
  spotInitial,
  futuresInitial,
}: {
  data: Point[];
  initial: number;
  byBook?: BookPoint[];
  spotInitial?: number;
  futuresInitial?: number;
}) {
  const [view, setView] = useState<View>("total");
  const hasBookData = byBook && byBook.length >= 0 && spotInitial != null && futuresInitial != null;

  const empty = data.length === 0;
  const series = empty
    ? [{ t: "start", equity: initial, pnl: 0 }]
    : [{ t: "start", equity: initial, pnl: 0 }, ...data];
  const last = series[series.length - 1].equity;
  const isUp = last >= initial;
  const stroke = isUp ? "#10b981" : "#f43f5e";
  const fill = isUp ? "url(#equityUp)" : "url(#equityDown)";

  const splitSeries: BookPoint[] =
    hasBookData && byBook
      ? [
          {
            t: "start",
            spot: spotInitial,
            futures: futuresInitial,
            total: spotInitial + futuresInitial,
          },
          ...byBook,
        ]
      : [];

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.4, duration: 0.5 }}
    >
      <Card className="border-border/50 bg-card/50 backdrop-blur">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-base font-medium">Equity Curve</CardTitle>
          <div className="flex items-center gap-3">
            {hasBookData && (
              <div className="inline-flex rounded-md border border-border/50 p-0.5 bg-muted/40">
                <button
                  type="button"
                  onClick={() => setView("total")}
                  className={cn(
                    "text-[10px] uppercase tracking-wider px-2 py-1 rounded transition-colors",
                    view === "total"
                      ? "bg-background text-foreground"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  Total
                </button>
                <button
                  type="button"
                  onClick={() => setView("split")}
                  className={cn(
                    "text-[10px] uppercase tracking-wider px-2 py-1 rounded transition-colors",
                    view === "split"
                      ? "bg-background text-foreground"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  Spot / Fut
                </button>
              </div>
            )}
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <span className="inline-block h-2 w-2 rounded-full" style={{ background: stroke }} />
              {empty
                ? "Awaiting first closed trade"
                : `${data.length} closed trade${data.length === 1 ? "" : "s"}`}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              {view === "total" || !hasBookData ? (
                <AreaChart data={series} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="equityUp" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#10b981" stopOpacity={0.35} />
                      <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="equityDown" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#f43f5e" stopOpacity={0.35} />
                      <stop offset="100%" stopColor="#f43f5e" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid
                    stroke="var(--border)"
                    strokeDasharray="3 3"
                    vertical={false}
                    opacity={0.3}
                  />
                  <XAxis
                    dataKey="t"
                    tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={(v) =>
                      v === "start"
                        ? "Init"
                        : new Date(v).toLocaleDateString("en-US", {
                            month: "short",
                            day: "numeric",
                          })
                    }
                  />
                  <YAxis
                    tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
                    tickLine={false}
                    axisLine={false}
                    width={60}
                    tickFormatter={(v) => `$${Number(v).toLocaleString()}`}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "var(--popover)",
                      border: "1px solid var(--border)",
                      borderRadius: 8,
                      fontSize: 12,
                    }}
                    labelFormatter={(v) =>
                      v === "start" ? "Initial" : new Date(v as string).toLocaleString()
                    }
                    formatter={(value: number) => [`$${value.toFixed(2)}`, "Equity"]}
                  />
                  <Area
                    type="monotone"
                    dataKey="equity"
                    stroke={stroke}
                    strokeWidth={2}
                    fill={fill}
                    isAnimationActive
                    animationDuration={800}
                  />
                </AreaChart>
              ) : (
                <AreaChart
                  data={splitSeries}
                  margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
                >
                  <defs>
                    <linearGradient id="spotGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#0ea5e9" stopOpacity={0.35} />
                      <stop offset="100%" stopColor="#0ea5e9" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="futGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#f59e0b" stopOpacity={0.35} />
                      <stop offset="100%" stopColor="#f59e0b" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid
                    stroke="var(--border)"
                    strokeDasharray="3 3"
                    vertical={false}
                    opacity={0.3}
                  />
                  <XAxis
                    dataKey="t"
                    tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={(v) =>
                      v === "start"
                        ? "Init"
                        : new Date(v).toLocaleDateString("en-US", {
                            month: "short",
                            day: "numeric",
                          })
                    }
                  />
                  <YAxis
                    tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
                    tickLine={false}
                    axisLine={false}
                    width={60}
                    tickFormatter={(v) => `$${Number(v).toLocaleString()}`}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "var(--popover)",
                      border: "1px solid var(--border)",
                      borderRadius: 8,
                      fontSize: 12,
                    }}
                    labelFormatter={(v) =>
                      v === "start" ? "Initial" : new Date(v as string).toLocaleString()
                    }
                    formatter={(value: number, name: string) => [
                      `$${value.toFixed(2)}`,
                      name.charAt(0).toUpperCase() + name.slice(1),
                    ]}
                  />
                  <Legend
                    wrapperStyle={{ fontSize: 11, paddingTop: 4 }}
                    iconType="circle"
                    iconSize={8}
                  />
                  <Area
                    type="monotone"
                    dataKey="spot"
                    stackId="book"
                    stroke="#0ea5e9"
                    strokeWidth={2}
                    fill="url(#spotGrad)"
                    isAnimationActive
                    animationDuration={800}
                  />
                  <Area
                    type="monotone"
                    dataKey="futures"
                    stackId="book"
                    stroke="#f59e0b"
                    strokeWidth={2}
                    fill="url(#futGrad)"
                    isAnimationActive
                    animationDuration={800}
                  />
                </AreaChart>
              )}
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}
