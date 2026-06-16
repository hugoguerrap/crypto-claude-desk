import { PageHeader } from "@/components/page-header";

export const dynamic = "force-dynamic";

/**
 * The actual <TerminalEmbed /> is mounted once in the root layout via
 * <PersistentTerminal />. That keeps the PTY + xterm scrollback alive across
 * route changes — leaving and returning here finds the same shell intact.
 *
 * This page only renders the header and tips. The terminal itself slots in
 * below, rendered by the persistent component when pathname === "/console".
 */
export default function ConsolePage() {
  return (
    <div className="mx-auto max-w-7xl px-6 py-8 space-y-4">
      <PageHeader
        eyebrow="Local Shell"
        title="Console"
        subtitle="Embedded terminal — persists across page navigation. Local-only, full shell access."
      />
      <div className="text-xs text-muted-foreground space-y-1">
        <p>
          <span className="font-mono text-foreground/70">Tips:</span> use any normal shell command.
          Try <code className="px-1 py-0.5 rounded bg-muted text-foreground/80">claude</code> to
          enter Claude Code, <code className="px-1 py-0.5 rounded bg-muted text-foreground/80">./bin/autopilot.sh monitor</code>{" "}
          for headless monitor, or <code className="px-1 py-0.5 rounded bg-muted text-foreground/80">uv run pytest</code>{" "}
          to run tests.
        </p>
        <p>
          The terminal connects to <code className="px-1 py-0.5 rounded bg-muted">ws://127.0.0.1:3001</code> (loopback only).
          It stays alive while you navigate the dashboard — closing the browser tab is what kills the shell.
        </p>
      </div>
    </div>
  );
}
