"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";
import { Activity, TrendingUp, TrendingDown, Loader2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { money, pct } from "@/lib/format";
import type { Candle, Interval } from "@/lib/ohlcv";

type OpenTrade = {
  id: string;
  symbol: string;
  side: string;
  entry_price: number;
  stop_loss: number | null;
  take_profit: number | null;
  usd_amount: number;
  leverage?: number;
  portfolio_type?: string;
  liquidation_price?: number | null;
};

type ClosedTrade = {
  id: string;
  symbol: string;
  side: string;
  entry_price: number;
  exit_price: number | null;
  opened_at: string;
  closed_at: string | null;
  result: string | null;
  pnl_percent: number | null;
};

const DEFAULT_WATCHLIST = ["BTC", "ETH", "SOL", "BNB", "XRP"];

// Normalize "AVAX/USDT" or "avaxusdt" → "AVAX" for symbol equality checks.
function baseOf(sym: string): string {
  return sym
    .toUpperCase()
    .replace(/[/:]/g, "")
    .replace(/(USDT|BUSD|USDC|USD)$/, "");
}
function sameSymbol(a: string, b: string): boolean {
  return baseOf(a) === baseOf(b);
}
const INTERVALS: Interval[] = ["15m", "1h", "4h", "1d"];
// Refresh live price every 30s
const PRICE_REFRESH_MS = 30_000;

export function PriceChart({
  initialSymbol,
  initialInterval,
  initialCandles,
  initialPrice,
  openTrades,
  closedTrades = [],
}: {
  initialSymbol: string;
  initialInterval: Interval;
  initialCandles: Candle[];
  initialPrice: number | null;
  openTrades: OpenTrade[];
  closedTrades?: ClosedTrade[];
}) {
  // Build watchlist: defaults + open-trade symbols (priority) + closed-trade
  // symbols (so post-mortem markers are reachable via a tab). Deduped.
  const watchlist = useMemo(() => {
    const list = [...DEFAULT_WATCHLIST];
    for (const t of closedTrades) {
      const base = baseOf(t.symbol);
      if (base && !list.some((s) => baseOf(s) === base)) list.push(base);
    }
    for (const t of openTrades) {
      const base = baseOf(t.symbol);
      if (base && !list.some((s) => baseOf(s) === base)) list.unshift(base);
    }
    if (!list.some((s) => baseOf(s) === baseOf(initialSymbol))) list.unshift(baseOf(initialSymbol));
    return Array.from(new Set(list));
  }, [openTrades, closedTrades, initialSymbol]);

  const [symbol, setSymbol] = useState(baseOf(initialSymbol));
  const [timeframe, setTimeframe] = useState<Interval>(initialInterval);
  const [candles, setCandles] = useState<Candle[]>(initialCandles);
  const [currentPrice, setCurrentPrice] = useState<number | null>(initialPrice);
  const [loading, setLoading] = useState(false);
  const [hover, setHover] = useState<Candle | null>(null);
  const [showClosedOverlay, setShowClosedOverlay] = useState(true);
  const hostRef = useRef<HTMLDivElement | null>(null);

  // All trades matching the currently-selected symbol
  const tradesForSymbol = useMemo(
    () => openTrades.filter((t) => sameSymbol(t.symbol, symbol)),
    [openTrades, symbol]
  );
  const closedForSymbol = useMemo(
    () => closedTrades.filter((t) => sameSymbol(t.symbol, symbol)),
    [closedTrades, symbol]
  );
  const showTradeOverlay = tradesForSymbol.length > 0;

  // Fetch candles when symbol or interval changes (skip on first mount if data is already there)
  useEffect(() => {
    const isInitial =
      symbol === initialSymbol && timeframe === initialInterval && candles === initialCandles;
    if (isInitial) return;

    let cancelled = false;
    setLoading(true);
    (async () => {
      try {
        const [c, p] = await Promise.all([
          fetch(`/api/ohlcv?symbol=${encodeURIComponent(symbol)}&interval=${timeframe}&limit=200`)
            .then((r) => r.json())
            .then((j) => (j.candles as Candle[]) ?? []),
          fetch(`/api/price?symbol=${encodeURIComponent(symbol)}`)
            .then((r) => r.json())
            .then((j) => (typeof j.price === "number" ? (j.price as number) : null)),
        ]);
        if (!cancelled) {
          setCandles(c);
          setCurrentPrice(p);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbol, timeframe]);

  // Poll current price every 30s
  useEffect(() => {
    const tick = setInterval(async () => {
      try {
        const r = await fetch(`/api/price?symbol=${encodeURIComponent(symbol)}`);
        const j = await r.json();
        if (typeof j.price === "number") setCurrentPrice(j.price);
      } catch {
        /* ignore */
      }
    }, PRICE_REFRESH_MS);
    return () => clearInterval(tick);
  }, [symbol]);

  // Render chart
  useEffect(() => {
    const host = hostRef.current;
    if (!host || candles.length === 0) return;

    let disposed = false;
    let chartRef: { remove: () => void } | null = null;
    let cleanupResize: (() => void) | undefined;

    (async () => {
      const { createChart, CandlestickSeries, HistogramSeries, LineStyle, CrosshairMode } =
        await import("lightweight-charts");
      if (disposed) return;

      const chart = createChart(host, {
        width: host.clientWidth,
        height: host.clientHeight,
        layout: {
          background: { color: "transparent" } as unknown as { type: string; color: string },
          textColor: "#a3a3a3",
          fontFamily: '"Geist", system-ui, -apple-system, BlinkMacSystemFont, sans-serif',
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

      // Draw entry/SL/TP/LIQ lines for EVERY open trade matching this symbol
      for (const t of tradesForSymbol) {
        const shortId = t.id.replace("trade_", "#");
        const isShort = t.side.toLowerCase() === "short";
        candleSeries.createPriceLine({
          price: t.entry_price,
          color: isShort ? "#f59e0b" : "#a78bfa",
          lineWidth: 2,
          lineStyle: LineStyle.Solid,
          axisLabelVisible: true,
          title: `${shortId} ${t.side.toUpperCase()}`,
        });
        if (t.take_profit != null) {
          candleSeries.createPriceLine({
            price: t.take_profit,
            color: "#10b981",
            lineWidth: 1,
            lineStyle: LineStyle.Dashed,
            axisLabelVisible: true,
            title: `${shortId} TP`,
          });
        }
        if (t.stop_loss != null) {
          candleSeries.createPriceLine({
            price: t.stop_loss,
            color: "#f43f5e",
            lineWidth: 1,
            lineStyle: LineStyle.Dashed,
            axisLabelVisible: true,
            title: `${shortId} SL`,
          });
        }
        // Liquidation reference for leveraged futures (drawn in dark orange
        // so it's distinct from entry/TP/SL and reads as a "DANGER" zone)
        if (
          t.portfolio_type === "futures" &&
          t.liquidation_price != null &&
          (t.leverage ?? 1) > 1
        ) {
          candleSeries.createPriceLine({
            price: t.liquidation_price,
            color: "#dc2626",
            lineWidth: 1,
            lineStyle: LineStyle.LargeDashed,
            axisLabelVisible: true,
            title: `${shortId} LIQ`,
          });
        }
      }

      // Closed-trade post-mortem markers — entry triangle + exit triangle,
      // color-coded by win/loss. Only render when overlay is enabled and
      // there's something to show for the current symbol.
      if (showClosedOverlay && closedForSymbol.length > 0) {
        type Marker = {
          time: import("lightweight-charts").Time;
          position: "aboveBar" | "belowBar";
          color: string;
          shape: "arrowUp" | "arrowDown" | "circle";
          text: string;
        };
        const markers: Marker[] = [];
        for (const t of closedForSymbol) {
          if (!t.closed_at) continue;
          const isLong = t.side.toLowerCase() === "long";
          const isWin = t.result === "win";
          const color = isWin ? "#10b981" : t.result === "loss" ? "#f43f5e" : "#94a3b8";
          const entryTime = Math.floor(new Date(t.opened_at).getTime() / 1000);
          const exitTime = Math.floor(new Date(t.closed_at).getTime() / 1000);
          const shortId = t.id.replace("trade_", "#");
          const pnlTxt =
            t.pnl_percent != null ? `${t.pnl_percent >= 0 ? "+" : ""}${t.pnl_percent.toFixed(1)}%` : "";
          markers.push({
            time: entryTime as unknown as import("lightweight-charts").Time,
            position: isLong ? "belowBar" : "aboveBar",
            color,
            shape: isLong ? "arrowUp" : "arrowDown",
            text: `${shortId} in`,
          });
          markers.push({
            time: exitTime as unknown as import("lightweight-charts").Time,
            position: isLong ? "aboveBar" : "belowBar",
            color,
            shape: "circle",
            text: `${shortId} out ${pnlTxt}`,
          });
        }
        if (markers.length > 0) {
          // Markers must be sorted by time ascending per lightweight-charts API.
          markers.sort((a, b) => Number(a.time) - Number(b.time));
          // setMarkers moved off the series in v5 → import from the package.
          // We try the static fn first, fall back to the series method for v4.
          import("lightweight-charts")
            .then((lw) => {
              const lwAny = lw as unknown as {
                createSeriesMarkers?: (s: unknown, m: Marker[]) => void;
              };
              if (typeof lwAny.createSeriesMarkers === "function") {
                lwAny.createSeriesMarkers(candleSeries, markers);
              } else {
                const seriesAny = candleSeries as unknown as {
                  setMarkers?: (m: Marker[]) => void;
                };
                seriesAny.setMarkers?.(markers);
              }
            })
            .catch(() => {
              /* markers are nice-to-have, never fatal */
            });
        }
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
  }, [candles, tradesForSymbol, closedForSymbol, showClosedOverlay]);

  const last = candles[candles.length - 1];
  const prev = candles[candles.length - 2];
  const change24h = last && prev ? ((last.close - prev.close) / prev.close) * 100 : 0;
  const showPrice = currentPrice ?? last?.close ?? 0;

  // Aggregate unrealized PnL across all trades for this symbol
  let unrealizedPnl: number | null = null;
  let unrealizedPct: number | null = null;
  if (showTradeOverlay && currentPrice != null) {
    let totalPnl = 0;
    let totalNotional = 0;
    for (const t of tradesForSymbol) {
      const dir = t.side.toLowerCase() === "short" ? -1 : 1;
      const lev = t.leverage ?? 1;
      const pctMove = ((currentPrice - t.entry_price) / t.entry_price) * dir * lev;
      totalPnl += t.usd_amount * pctMove;
      totalNotional += t.usd_amount;
    }
    unrealizedPnl = totalPnl;
    unrealizedPct = totalNotional > 0 ? (totalPnl / totalNotional) * 100 : 0;
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.42, duration: 0.5 }}
    >
      <Card className="border-border/50 bg-card/50 backdrop-blur overflow-hidden">
        <CardHeader className="pb-2 space-y-3">
          {/* Top row: title + live price + open-trade summary */}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <CardTitle className="flex items-center gap-2 text-base font-medium">
                <Activity className="h-4 w-4 text-violet-400" />
                {symbol}
                <Badge variant="outline" className="font-mono text-[10px] font-normal ml-1">
                  {timeframe}
                </Badge>
                {loading && <Loader2 className="h-3 w-3 ml-1 animate-spin text-muted-foreground" />}
              </CardTitle>
              <div className="flex items-baseline gap-2">
                <span className="text-xl font-semibold tabular-nums">{money(showPrice)}</span>
                <span
                  className={cn(
                    "text-xs tabular-nums font-medium flex items-center gap-1",
                    change24h >= 0 ? "text-emerald-500" : "text-rose-500"
                  )}
                >
                  {change24h >= 0 ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
                  {pct(change24h)}
                </span>
              </div>
            </div>
            {showTradeOverlay && (
              <div className="text-right">
                <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
                  {tradesForSymbol.length} open ·{" "}
                  {tradesForSymbol
                    .map((t) => `${t.side.toUpperCase()} ${money(t.entry_price)}`)
                    .join(" · ")}
                </div>
                {unrealizedPnl != null && (
                  <div
                    className={cn(
                      "tabular-nums font-semibold text-sm",
                      unrealizedPnl > 0
                        ? "text-emerald-500"
                        : unrealizedPnl < 0
                        ? "text-rose-500"
                        : "text-muted-foreground"
                    )}
                  >
                    {unrealizedPnl >= 0 ? "+" : ""}
                    {money(unrealizedPnl)} · {pct(unrealizedPct ?? 0)} unrealized
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Tabs: symbol + interval + closed-overlay toggle */}
          <div className="flex flex-wrap items-center justify-between gap-3 -mb-1">
            <div className="flex items-center gap-1 p-1 rounded-md bg-muted/40 border border-border/40 flex-wrap">
              {watchlist.map((s) => {
                const active = sameSymbol(s, symbol);
                const openHere = openTrades.filter((t) => sameSymbol(t.symbol, s)).length;
                const closedHere = closedTrades.filter((t) => sameSymbol(t.symbol, s)).length;
                return (
                  <button
                    key={s}
                    onClick={() => setSymbol(s)}
                    className={cn(
                      "relative px-3 py-1 text-xs font-medium rounded transition-colors",
                      active
                        ? "bg-background text-foreground shadow-sm"
                        : "text-muted-foreground hover:text-foreground"
                    )}
                  >
                    {s}
                    {openHere > 0 && (
                      <span
                        className="absolute -top-0.5 -right-0.5 h-1.5 w-1.5 rounded-full bg-emerald-500"
                        title={`${openHere} open trade${openHere === 1 ? "" : "s"}`}
                      />
                    )}
                    {openHere === 0 && closedHere > 0 && (
                      <span
                        className="absolute -top-0.5 -right-0.5 h-1.5 w-1.5 rounded-full bg-slate-400/70"
                        title={`${closedHere} closed trade${closedHere === 1 ? "" : "s"} for post-mortem`}
                      />
                    )}
                  </button>
                );
              })}
            </div>
            <div className="flex items-center gap-2">
              {closedTrades.length > 0 && (
                <button
                  type="button"
                  onClick={() => setShowClosedOverlay((v) => !v)}
                  className={cn(
                    "text-[10px] uppercase tracking-wider px-2 py-1 rounded border transition-colors",
                    showClosedOverlay
                      ? "border-slate-400/40 bg-slate-400/10 text-slate-300"
                      : "border-border/40 text-muted-foreground hover:text-foreground"
                  )}
                  title="Show entry/exit markers for closed trades"
                >
                  {showClosedOverlay ? "● post-mortem" : "○ post-mortem"}
                </button>
              )}
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
          </div>
        </CardHeader>
        <CardContent className="p-0 relative">
          {candles.length === 0 && !loading ? (
            <div className="h-[380px] grid place-items-center text-sm text-muted-foreground">
              Unable to load candles for {symbol}
            </div>
          ) : (
            <>
              <div ref={hostRef} className="h-[380px] w-full" />
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
                    O <span className="text-foreground">{hover.open.toFixed(2)}</span>{" "}
                    H <span className="text-foreground">{hover.high.toFixed(2)}</span>{" "}
                    L <span className="text-foreground">{hover.low.toFixed(2)}</span>{" "}
                    C{" "}
                    <span className={hover.close >= hover.open ? "text-emerald-500" : "text-rose-500"}>
                      {hover.close.toFixed(2)}
                    </span>{" "}
                    V <span className="text-foreground/70">{Math.round(hover.volume).toLocaleString()}</span>
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
