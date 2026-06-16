"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";
import { Activity, Loader2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { money } from "@/lib/format";
import type { Candle, Interval } from "@/lib/ohlcv";
import type { Trade } from "@/lib/db";

const INTERVALS: Interval[] = ["1h", "4h", "1d"];
const DEFAULT_LIMIT = 300;

/**
 * Full-history chart for a single symbol — overlays EVERY trade on it.
 *
 * For each trade:
 *   - Entry marker (arrow, side-colored)
 *   - Exit marker (arrow, result-colored) — closed only
 *   - For OPEN trades: SL + TP price lines drawn extending across the chart
 */
export function SymbolHistoryChart({
  symbol,
  trades,
  initialCandles,
  initialInterval,
}: {
  symbol: string;
  trades: Trade[];
  initialCandles: Candle[];
  initialInterval: Interval;
}) {
  const [timeframe, setTimeframe] = useState<Interval>(initialInterval);
  const [candles, setCandles] = useState<Candle[]>(initialCandles);
  const [loading, setLoading] = useState(false);
  const [hover, setHover] = useState<Candle | null>(null);
  const hostRef = useRef<HTMLDivElement | null>(null);

  // Stats summary line above chart
  const summary = useMemo(() => {
    const opens = trades.filter((t) => t.status === "open").length;
    const wins = trades.filter((t) => t.result === "win").length;
    const losses = trades.filter((t) => t.result === "loss").length;
    return { opens, wins, losses, total: trades.length };
  }, [trades]);

  useEffect(() => {
    if (timeframe === initialInterval && candles === initialCandles) return;
    let cancelled = false;
    setLoading(true);
    (async () => {
      try {
        const r = await fetch(
          `/api/ohlcv?symbol=${encodeURIComponent(symbol)}&interval=${timeframe}&limit=${DEFAULT_LIMIT}`
        );
        const j = await r.json();
        if (!cancelled) setCandles((j.candles as Candle[]) ?? []);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [timeframe, symbol]);

  useEffect(() => {
    const host = hostRef.current;
    if (!host || candles.length === 0) return;
    let disposed = false;
    let chartRef: { remove: () => void } | null = null;
    let cleanupResize: (() => void) | undefined;

    (async () => {
      const {
        createChart,
        CandlestickSeries,
        HistogramSeries,
        LineStyle,
        CrosshairMode,
        createSeriesMarkers,
      } = await import("lightweight-charts");
      if (disposed) return;

      const chart = createChart(host, {
        width: host.clientWidth,
        height: host.clientHeight,
        layout: {
          background: { color: "transparent" } as unknown as { type: string; color: string },
          textColor: "#a3a3a3",
          fontFamily: '"Geist", system-ui, sans-serif',
          fontSize: 11,
        },
        grid: {
          vertLines: { color: "rgba(255,255,255,0.04)" },
          horzLines: { color: "rgba(255,255,255,0.04)" },
        },
        rightPriceScale: {
          borderColor: "rgba(255,255,255,0.08)",
          scaleMargins: { top: 0.05, bottom: 0.22 },
        },
        timeScale: {
          borderColor: "rgba(255,255,255,0.08)",
          timeVisible: true,
          secondsVisible: false,
        },
        crosshair: {
          mode: CrosshairMode.Normal,
          vertLine: { color: "rgba(167,139,250,0.5)", style: LineStyle.Dashed },
          horzLine: { color: "rgba(167,139,250,0.5)", style: LineStyle.Dashed },
        },
      });
      chartRef = chart;

      const candleSeries = chart.addSeries(CandlestickSeries, {
        upColor: "#10b981",
        downColor: "#f43f5e",
        wickUpColor: "#10b981",
        wickDownColor: "#f43f5e",
        borderVisible: false,
      });
      candleSeries.setData(
        candles.map((c) => ({
          time: c.time as unknown as import("lightweight-charts").Time,
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close,
        }))
      );

      const volumeSeries = chart.addSeries(HistogramSeries, {
        priceFormat: { type: "volume" },
        priceScaleId: "vol",
        color: "rgba(167,139,250,0.3)",
      });
      chart.priceScale("vol").applyOptions({
        scaleMargins: { top: 0.82, bottom: 0 },
      });
      volumeSeries.setData(
        candles.map((c) => ({
          time: c.time as unknown as import("lightweight-charts").Time,
          value: c.volume,
          color: c.close >= c.open ? "rgba(16,185,129,0.4)" : "rgba(244,63,94,0.4)",
        }))
      );

      // Plot trades: SL/TP lines for open, entry/exit markers for all
      const minTime = candles[0]?.time ?? 0;
      const maxTime = candles[candles.length - 1]?.time ?? 0;
      type Marker = {
        time: import("lightweight-charts").Time;
        position: "aboveBar" | "belowBar";
        color: string;
        shape: "arrowUp" | "arrowDown" | "circle";
        text: string;
      };
      const markers: Marker[] = [];

      for (const t of trades) {
        const entryUnix = Math.floor(new Date(t.opened_at).getTime() / 1000);
        if (entryUnix >= minTime && entryUnix <= maxTime) {
          markers.push({
            time: entryUnix as unknown as import("lightweight-charts").Time,
            position: t.side === "long" ? "belowBar" : "aboveBar",
            color: t.side === "long" ? "#a78bfa" : "#f59e0b",
            shape: t.side === "long" ? "arrowUp" : "arrowDown",
            text: `${t.side === "long" ? "L" : "S"} ${t.id.replace("trade_", "#")}`,
          });
        }
        if (t.exit_price != null && t.closed_at) {
          const exitUnix = Math.floor(new Date(t.closed_at).getTime() / 1000);
          if (exitUnix >= minTime && exitUnix <= maxTime) {
            const color = t.result === "win" ? "#10b981" : t.result === "loss" ? "#f43f5e" : "#71717a";
            markers.push({
              time: exitUnix as unknown as import("lightweight-charts").Time,
              position: "aboveBar",
              color,
              shape: "circle",
              text: t.pnl_percent != null ? `${t.pnl_percent >= 0 ? "+" : ""}${t.pnl_percent.toFixed(1)}%` : "x",
            });
          }
        }
        // Open trades: draw price lines extending across chart
        if (t.status === "open") {
          candleSeries.createPriceLine({
            price: t.entry_price,
            color: "#a78bfa",
            lineWidth: 2,
            lineStyle: LineStyle.Solid,
            axisLabelVisible: true,
            title: `Entry ${t.id.replace("trade_", "#")}`,
          });
          if (t.take_profit != null) {
            candleSeries.createPriceLine({
              price: t.take_profit,
              color: "#10b981",
              lineWidth: 1,
              lineStyle: LineStyle.Dashed,
              axisLabelVisible: true,
              title: "TP",
            });
          }
          if (t.stop_loss != null) {
            candleSeries.createPriceLine({
              price: t.stop_loss,
              color: "#f43f5e",
              lineWidth: 1,
              lineStyle: LineStyle.Dashed,
              axisLabelVisible: true,
              title: "SL",
            });
          }
        }
      }

      if (markers.length > 0) {
        const ms = await import("lightweight-charts");
        const createSeriesMarkers = (ms as unknown as { createSeriesMarkers?: (s: unknown, m: unknown[]) => void })
          .createSeriesMarkers;
        if (createSeriesMarkers) createSeriesMarkers(candleSeries, markers);
      }

      chart.subscribeCrosshairMove((param) => {
        if (!param.time || !param.seriesData.size) {
          setHover(null);
          return;
        }
        const cd = param.seriesData.get(candleSeries) as
          | { open: number; high: number; low: number; close: number }
          | undefined;
        if (!cd) {
          setHover(null);
          return;
        }
        const unix = typeof param.time === "number" ? param.time : Number(param.time);
        const orig = candles.find((c) => c.time === unix);
        setHover({
          time: unix,
          open: cd.open,
          high: cd.high,
          low: cd.low,
          close: cd.close,
          volume: orig?.volume ?? 0,
        });
      });

      chart.timeScale().fitContent();

      const ro = new ResizeObserver(() => {
        chart.applyOptions({ width: host.clientWidth, height: host.clientHeight });
      });
      ro.observe(host);
      cleanupResize = () => ro.disconnect();
    })();

    return () => {
      disposed = true;
      cleanupResize?.();
      chartRef?.remove();
    };
  }, [candles, trades]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.1, duration: 0.5 }}
    >
      <Card className="border-border/50 bg-card/50 backdrop-blur overflow-hidden">
        <CardHeader className="pb-2 flex flex-row items-center justify-between space-y-0 flex-wrap gap-3">
          <CardTitle className="flex items-center gap-2 text-base font-medium">
            <Activity className="h-4 w-4 text-violet-400" />
            {symbol} · price history with your trades
            <Badge variant="outline" className="font-mono text-[10px] font-normal ml-1">
              {timeframe}
            </Badge>
            {loading && <Loader2 className="h-3 w-3 ml-1 animate-spin text-muted-foreground" />}
          </CardTitle>
          <div className="flex items-center gap-3">
            <div className="text-xs text-muted-foreground flex items-center gap-2">
              <span className="flex items-center gap-1">
                <span className="inline-block h-2 w-2 rounded-full bg-violet-500" />
                {summary.opens} open
              </span>
              <span className="flex items-center gap-1">
                <span className="inline-block h-2 w-2 rounded-full bg-emerald-500" />
                {summary.wins}W
              </span>
              <span className="flex items-center gap-1">
                <span className="inline-block h-2 w-2 rounded-full bg-rose-500" />
                {summary.losses}L
              </span>
            </div>
            <div className="flex items-center gap-1 p-1 rounded-md bg-muted/40 border border-border/40">
              {INTERVALS.map((iv) => (
                <button
                  key={iv}
                  onClick={() => setTimeframe(iv)}
                  className={cn(
                    "px-2.5 py-1 text-[11px] font-mono rounded transition-colors",
                    iv === timeframe
                      ? "bg-background text-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  {iv}
                </button>
              ))}
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-0 relative">
          {candles.length === 0 && !loading ? (
            <div className="h-[420px] grid place-items-center text-sm text-muted-foreground">
              Unable to load candles for {symbol}
            </div>
          ) : (
            <>
              <div ref={hostRef} className="h-[420px] w-full" />
              {hover && (
                <div className="absolute top-2 left-2 z-10 rounded-md bg-background/80 backdrop-blur border border-border/40 px-2.5 py-1.5 text-[11px] tabular-nums font-mono pointer-events-none">
                  <span className="text-muted-foreground mr-2">
                    {new Date(hover.time * 1000).toLocaleString("en-US", {
                      month: "short",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                  <span>
                    O <span className="text-foreground">{money(hover.open)}</span> · H{" "}
                    <span className="text-foreground">{money(hover.high)}</span> · L{" "}
                    <span className="text-foreground">{money(hover.low)}</span> · C{" "}
                    <span
                      className={hover.close >= hover.open ? "text-emerald-500" : "text-rose-500"}
                    >
                      {money(hover.close)}
                    </span>
                  </span>
                </div>
              )}
              {loading && candles.length > 0 && (
                <div className="absolute inset-0 bg-background/40 backdrop-blur-sm grid place-items-center pointer-events-none">
                  <Loader2 className="h-6 w-6 animate-spin text-violet-400" />
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>
    </motion.div>
  );
}
