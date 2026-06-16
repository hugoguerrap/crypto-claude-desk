"use client";

import { useEffect, useRef, useState } from "react";
import { Terminal as TerminalIcon, RefreshCw, Circle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const PTY_PORT = 3001;

type ConnState = "connecting" | "open" | "closed" | "error";

export function TerminalEmbed({ height = 540 }: { height?: number }) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const termRef = useRef<unknown>(null);
  const fitRef = useRef<unknown>(null);
  const [state, setState] = useState<ConnState>("connecting");
  const [reconnectKey, setReconnectKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    let cleanup: (() => void) | undefined;

    async function setup() {
      const host = hostRef.current;
      if (!host) return;

      // Dynamically import (xterm needs window — must run in browser only)
      const [{ Terminal }, { FitAddon }, { WebLinksAddon }] = await Promise.all([
        import("@xterm/xterm"),
        import("@xterm/addon-fit"),
        import("@xterm/addon-web-links"),
      ]);
      await import("@xterm/xterm/css/xterm.css");
      if (cancelled) return;

      const term = new Terminal({
        cursorBlink: true,
        fontFamily: '"Geist Mono", "JetBrains Mono", Menlo, Consolas, monospace',
        fontSize: 13,
        lineHeight: 1.2,
        theme: {
          background: "#0a0a0a",
          foreground: "#e5e5e5",
          cursor: "#a78bfa",
          cursorAccent: "#0a0a0a",
          selectionBackground: "#a78bfa55",
          black: "#0a0a0a",
          red: "#f43f5e",
          green: "#10b981",
          yellow: "#f59e0b",
          blue: "#3b82f6",
          magenta: "#a78bfa",
          cyan: "#22d3ee",
          white: "#e5e5e5",
          brightBlack: "#525252",
          brightRed: "#fb7185",
          brightGreen: "#34d399",
          brightYellow: "#fbbf24",
          brightBlue: "#60a5fa",
          brightMagenta: "#c4b5fd",
          brightCyan: "#67e8f9",
          brightWhite: "#fafafa",
        },
        allowTransparency: false,
        convertEol: true,
        scrollback: 5000,
      });

      const fit = new FitAddon();
      term.loadAddon(fit);
      term.loadAddon(new WebLinksAddon());

      term.open(host);
      // Give layout a tick to settle, then fit
      requestAnimationFrame(() => {
        try {
          fit.fit();
        } catch {
          /* container not ready yet */
        }
      });

      termRef.current = term;
      fitRef.current = fit;

      const ws = new WebSocket(`ws://127.0.0.1:${PTY_PORT}`);
      wsRef.current = ws;
      setState("connecting");

      ws.onopen = () => {
        setState("open");
        const { cols, rows } = term;
        ws.send(JSON.stringify({ type: "resize", cols, rows }));
        term.writeln("\x1b[38;5;141m─ connected to pty-server (project root cwd) ─\x1b[0m");
      };

      ws.onmessage = (evt) => {
        try {
          const msg = JSON.parse(evt.data);
          if (msg.type === "data") {
            term.write(msg.data);
          } else if (msg.type === "exit") {
            term.writeln(`\r\n\x1b[38;5;196m─ shell exited (code=${msg.exitCode}) ─\x1b[0m`);
            setState("closed");
          }
        } catch {
          /* malformed */
        }
      };

      ws.onerror = () => setState("error");
      ws.onclose = () => setState((prev) => (prev === "error" ? "error" : "closed"));

      const dispose = term.onData((data: string) => {
        if (ws.readyState === ws.OPEN) {
          ws.send(JSON.stringify({ type: "input", data }));
        }
      });

      // Resize handling
      const ro = new ResizeObserver(() => {
        try {
          fit.fit();
          if (ws.readyState === ws.OPEN) {
            ws.send(JSON.stringify({ type: "resize", cols: term.cols, rows: term.rows }));
          }
        } catch {
          /* container size 0 momentarily */
        }
      });
      ro.observe(host);

      cleanup = () => {
        dispose.dispose();
        ro.disconnect();
        try {
          ws.close();
        } catch {
          /* ignore */
        }
        term.dispose();
        termRef.current = null;
        fitRef.current = null;
        wsRef.current = null;
      };
    }

    setup();

    return () => {
      cancelled = true;
      cleanup?.();
    };
  }, [reconnectKey]);

  const dotColor =
    state === "open"
      ? "text-emerald-500"
      : state === "connecting"
      ? "text-amber-500"
      : state === "error"
      ? "text-rose-500"
      : "text-muted-foreground";

  return (
    <Card className="border-border/50 bg-card/50 backdrop-blur overflow-hidden">
      <CardHeader className="pb-2 flex flex-row items-center justify-between space-y-0">
        <CardTitle className="flex items-center gap-2 text-base font-medium">
          <TerminalIcon className="h-4 w-4 text-violet-400" />
          Console
          <Badge variant="outline" className="ml-2 font-mono text-[10px] font-normal">
            ws://127.0.0.1:{PTY_PORT}
          </Badge>
        </CardTitle>
        <div className="flex items-center gap-2">
          <span className={cn("flex items-center gap-1.5 text-xs", dotColor)}>
            <Circle className="h-2 w-2 fill-current" />
            <span className="uppercase tracking-wider">{state}</span>
          </span>
          <Button
            variant="outline"
            size="sm"
            className="h-7 px-2 text-xs"
            onClick={() => setReconnectKey((k) => k + 1)}
          >
            <RefreshCw className="h-3 w-3 mr-1" /> Reconnect
          </Button>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        <div
          ref={hostRef}
          className="bg-[#0a0a0a]"
          style={{ height, padding: 8 }}
        />
      </CardContent>
    </Card>
  );
}
