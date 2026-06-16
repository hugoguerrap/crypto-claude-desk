"use client";

import { useRef, useState } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import { AnimatedNumber } from "./animated-number";

/**
 * Stat card with a cursor-following spotlight (radial gradient that tracks
 * the mouse position). Pure CSS + a single React state for the position —
 * no extra deps.
 */
export function SpotlightCard({
  label,
  value,
  decimals = 0,
  prefix = "",
  suffix = "",
  hint,
  tone = "neu",
  delay = 0,
  icon,
}: {
  label: string;
  value: number;
  decimals?: number;
  prefix?: string;
  suffix?: string;
  hint?: string;
  tone?: "pos" | "neg" | "neu";
  delay?: number;
  icon?: React.ReactNode;
}) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null);

  const onMove = (e: React.MouseEvent) => {
    const el = ref.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    setPos({ x: e.clientX - r.left, y: e.clientY - r.top });
  };

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.4 }}
      onMouseMove={onMove}
      onMouseLeave={() => setPos(null)}
      className={cn(
        "relative overflow-hidden rounded-lg border border-border/50 bg-card/50 backdrop-blur p-5 group transition-colors hover:border-border",
        tone === "pos" && "hover:border-emerald-500/40",
        tone === "neg" && "hover:border-rose-500/40"
      )}
    >
      {/* spotlight */}
      {pos && (
        <div
          className="pointer-events-none absolute -inset-px opacity-0 transition-opacity group-hover:opacity-100"
          style={{
            background: `radial-gradient(220px circle at ${pos.x}px ${pos.y}px, ${
              tone === "pos"
                ? "rgba(16,185,129,0.10)"
                : tone === "neg"
                ? "rgba(244,63,94,0.10)"
                : "rgba(167,139,250,0.10)"
            }, transparent 60%)`,
          }}
        />
      )}
      <div className="relative">
        <div className="flex items-center justify-between mb-3">
          <span className="text-[10px] uppercase tracking-widest text-muted-foreground">
            {label}
          </span>
          {icon && (
            <span
              className={cn(
                "rounded-md p-1.5",
                tone === "pos" && "bg-emerald-500/10 text-emerald-500",
                tone === "neg" && "bg-rose-500/10 text-rose-500",
                tone === "neu" && "bg-muted text-muted-foreground"
              )}
            >
              {icon}
            </span>
          )}
        </div>
        <div
          className={cn(
            "text-2xl font-semibold tabular-nums tracking-tight",
            tone === "pos" && "text-emerald-500",
            tone === "neg" && "text-rose-500"
          )}
        >
          <AnimatedNumber
            value={Number.isFinite(value) ? value : 0}
            decimals={decimals}
            prefix={prefix}
            suffix={suffix}
          />
        </div>
        {hint && <div className="text-xs text-muted-foreground mt-1 tabular-nums">{hint}</div>}
      </div>
    </motion.div>
  );
}
