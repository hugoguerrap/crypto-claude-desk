"use client";

import { usePathname } from "next/navigation";
import { TerminalEmbed } from "./terminal-embed";
import { cn } from "@/lib/utils";

/**
 * Mounted once at the root layout. The PTY + xterm instance lives across
 * route navigations — visiting /trades and coming back to /console finds the
 * same shell with full scrollback intact.
 *
 * When pathname !== "/console", the wrapper is hidden via CSS — the React
 * subtree remains mounted, the WebSocket remains open, the shell keeps
 * running.
 */
export function PersistentTerminal() {
  const pathname = usePathname();
  const visible = pathname === "/console";

  return (
    <div
      className={cn(
        "mx-auto max-w-7xl px-6 pb-8",
        visible ? "block" : "hidden"
      )}
      aria-hidden={!visible}
    >
      <TerminalEmbed height={620} />
    </div>
  );
}
