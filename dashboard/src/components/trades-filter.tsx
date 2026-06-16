"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo, useState } from "react";
import { Search, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { SymbolCount } from "@/lib/db";

type Status = "all" | "open" | "closed";
type Side = "all" | "long" | "short";

const STATUS_OPTIONS: { value: Status; label: string }[] = [
  { value: "all", label: "All" },
  { value: "open", label: "Open" },
  { value: "closed", label: "Closed" },
];
const SIDE_OPTIONS: { value: Side; label: string }[] = [
  { value: "all", label: "Any side" },
  { value: "long", label: "Long" },
  { value: "short", label: "Short" },
];

export function TradesFilter({
  symbols,
  currentSymbol,
  currentStatus,
  currentSide,
  totalShown,
}: {
  symbols: SymbolCount[];
  currentSymbol: string | null;
  currentStatus: Status;
  currentSide: Side;
  totalShown: number;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const [manual, setManual] = useState("");

  const setParam = useCallback(
    (key: string, value: string | null) => {
      const next = new URLSearchParams(params.toString());
      if (!value || value === "all") next.delete(key);
      else next.set(key, value);
      const q = next.toString();
      router.push(q ? `${pathname}?${q}` : pathname);
    },
    [params, pathname, router]
  );

  const clearAll = () => router.push(pathname);

  const knownSymbols = useMemo(() => new Set(symbols.map((s) => s.symbol)), [symbols]);

  const submitManual = (e: React.FormEvent) => {
    e.preventDefault();
    const v = manual.trim().toUpperCase();
    if (v) setParam("symbol", v);
    setManual("");
  };

  const anyFilter =
    !!currentSymbol || currentStatus !== "all" || currentSide !== "all";

  return (
    <div className="rounded-lg border border-border/50 bg-card/40 backdrop-blur p-4 space-y-3">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span className="uppercase tracking-wider">Filter</span>
          <span className="tabular-nums">·</span>
          <span className="tabular-nums">{totalShown} match{totalShown === 1 ? "" : "es"}</span>
        </div>
        {anyFilter && (
          <button
            onClick={clearAll}
            className="text-xs text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1"
          >
            <X className="h-3 w-3" /> Clear all
          </button>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-1.5">
        <FilterPill
          active={!currentSymbol}
          onClick={() => setParam("symbol", null)}
          label="All symbols"
          count={symbols.reduce((s, x) => s + x.count, 0)}
        />
        {symbols.map((s) => (
          <FilterPill
            key={s.symbol}
            active={currentSymbol === s.symbol}
            onClick={() => setParam("symbol", s.symbol)}
            label={s.symbol}
            count={s.count}
            dot={s.open_count > 0}
          />
        ))}
        {currentSymbol && !knownSymbols.has(currentSymbol) && (
          <FilterPill
            active
            onClick={() => setParam("symbol", null)}
            label={currentSymbol}
            count={0}
            mute
          />
        )}
        <form onSubmit={submitManual} className="ml-auto flex items-center gap-1.5">
          <div className="relative">
            <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3 w-3 text-muted-foreground" />
            <input
              value={manual}
              onChange={(e) => setManual(e.target.value)}
              placeholder="Buscar símbolo..."
              className="pl-7 pr-2 py-1 text-xs bg-background/60 border border-border/50 rounded-md w-36 focus:outline-none focus:border-violet-500/50"
            />
          </div>
        </form>
      </div>

      <div className="flex flex-wrap items-center gap-4 pt-1">
        <SegmentedControl
          options={STATUS_OPTIONS}
          value={currentStatus}
          onChange={(v) => setParam("status", v)}
        />
        <SegmentedControl
          options={SIDE_OPTIONS}
          value={currentSide}
          onChange={(v) => setParam("side", v)}
        />
      </div>
    </div>
  );
}

function FilterPill({
  label,
  count,
  active,
  onClick,
  dot,
  mute,
}: {
  label: string;
  count: number;
  active: boolean;
  onClick: () => void;
  dot?: boolean;
  mute?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "relative px-2.5 py-1 text-xs font-medium rounded-md border transition-colors",
        active
          ? "bg-violet-500/10 border-violet-500/40 text-foreground"
          : "bg-background/40 border-border/40 text-muted-foreground hover:text-foreground hover:border-border/70",
        mute && "opacity-60"
      )}
    >
      {label}
      <span className="ml-1.5 text-[10px] tabular-nums text-muted-foreground/80">
        {count}
      </span>
      {dot && (
        <span className="absolute -top-0.5 -right-0.5 h-1.5 w-1.5 rounded-full bg-emerald-500" />
      )}
    </button>
  );
}

function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
}: {
  options: { value: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div className="flex items-center gap-1 p-1 rounded-md bg-muted/40 border border-border/40">
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          className={cn(
            "px-2.5 py-1 text-[11px] font-medium rounded transition-colors",
            o.value === value
              ? "bg-background text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
