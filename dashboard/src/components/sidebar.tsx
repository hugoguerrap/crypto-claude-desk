"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import {
  Activity,
  BarChart3,
  BookOpen,
  FileText,
  Settings2,
  Sparkles,
  Terminal,
} from "lucide-react";
import { cn } from "@/lib/utils";

const items = [
  { href: "/", icon: BarChart3, label: "Dashboard" },
  { href: "/trades", icon: Activity, label: "Trades" },
  { href: "/predictions", icon: BookOpen, label: "Predictions" },
  { href: "/patterns", icon: Sparkles, label: "Patterns" },
  { href: "/reports", icon: FileText, label: "Reports" },
  { href: "/console", icon: Terminal, label: "Console" },
  { href: "/settings", icon: Settings2, label: "Settings" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden lg:flex w-56 shrink-0 flex-col border-r border-border/40 bg-card/30 backdrop-blur-md sticky top-0 h-screen">
      <Link
        href="/"
        className="flex h-16 items-center gap-2 px-5 border-b border-border/40 hover:bg-foreground/5 transition-colors"
      >
        <div className="h-7 w-7 rounded-md bg-gradient-to-br from-violet-500 to-emerald-500 grid place-items-center">
          <Sparkles className="h-4 w-4 text-white" />
        </div>
        <div className="flex flex-col leading-tight">
          <span className="text-sm font-semibold">Crypto Desk</span>
          <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
            multi-agent
          </span>
        </div>
      </Link>
      <nav className="flex-1 p-3 space-y-1">
        {items.map((it, i) => {
          const isActive =
            it.href === "/" ? pathname === "/" : pathname.startsWith(it.href);
          return (
            <motion.div
              key={it.href}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.1 + i * 0.05 }}
            >
              <Link
                href={it.href}
                className={cn(
                  "flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors relative",
                  isActive
                    ? "bg-foreground/5 text-foreground"
                    : "text-muted-foreground hover:bg-foreground/5 hover:text-foreground"
                )}
              >
                {isActive && (
                  <motion.span
                    layoutId="active-pill"
                    className="absolute inset-y-1 left-0 w-0.5 rounded-full bg-gradient-to-b from-violet-500 to-emerald-500"
                  />
                )}
                <it.icon className="h-4 w-4" />
                {it.label}
              </Link>
            </motion.div>
          );
        })}
      </nav>
      <div className="p-3 border-t border-border/40">
        <div className="rounded-md bg-gradient-to-br from-violet-500/10 to-emerald-500/10 p-3 text-xs">
          <div className="font-medium mb-1">Paper trading</div>
          <div className="text-muted-foreground leading-snug">
            All trades shown are simulated. No real funds at risk.
          </div>
        </div>
      </div>
    </aside>
  );
}
