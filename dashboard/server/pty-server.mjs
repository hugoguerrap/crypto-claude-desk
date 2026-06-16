#!/usr/bin/env node
/**
 * PTY WebSocket server for the embedded dashboard terminal.
 *
 * Bridges xterm.js (browser) ↔ a real OS shell via node-pty.
 *
 * Architecture:
 *   Browser xterm.js  ──WebSocket──>  this server  ──PTY──>  shell (powershell/bash)
 *
 * Local-only. Binds to 127.0.0.1, no auth — the spawned shell has full user
 * privileges, so this MUST NOT be exposed to non-loopback interfaces.
 */

import { WebSocketServer } from "ws";
import { spawn } from "node-pty";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const PORT = Number(process.env.PTY_PORT || 3001);
const HOST = "127.0.0.1";

// Default working directory = project root (one level up from dashboard/)
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const PROJECT_ROOT = path.resolve(__dirname, "..", "..");

// Pick a sensible shell per platform
function pickShell() {
  if (process.platform === "win32") {
    return {
      cmd: process.env.PTY_SHELL || "powershell.exe",
      args: ["-NoLogo"],
    };
  }
  return {
    cmd: process.env.PTY_SHELL || process.env.SHELL || "/bin/bash",
    args: ["--login"],
  };
}

const wss = new WebSocketServer({ host: HOST, port: PORT });

wss.on("listening", () => {
  console.log(`[pty-server] listening on ws://${HOST}:${PORT}`);
  console.log(`[pty-server] project root: ${PROJECT_ROOT}`);
  console.log(`[pty-server] shell: ${pickShell().cmd}`);
});

wss.on("connection", (ws, req) => {
  const remote = req.socket.remoteAddress;
  if (remote !== "127.0.0.1" && remote !== "::1" && remote !== "::ffff:127.0.0.1") {
    console.warn(`[pty-server] rejected non-loopback connection from ${remote}`);
    ws.close(4403, "loopback only");
    return;
  }

  const shell = pickShell();
  const cols = 120;
  const rows = 30;

  const pty = spawn(shell.cmd, shell.args, {
    name: "xterm-256color",
    cols,
    rows,
    cwd: PROJECT_ROOT,
    env: { ...process.env, TERM: "xterm-256color" },
  });

  console.log(`[pty-server] spawned PID ${pty.pid} (${shell.cmd})`);

  // PTY output → browser
  pty.onData((data) => {
    if (ws.readyState === ws.OPEN) {
      ws.send(JSON.stringify({ type: "data", data }));
    }
  });

  pty.onExit(({ exitCode, signal }) => {
    console.log(`[pty-server] PID ${pty.pid} exited code=${exitCode} signal=${signal}`);
    if (ws.readyState === ws.OPEN) {
      ws.send(JSON.stringify({ type: "exit", exitCode, signal }));
      ws.close();
    }
  });

  // Browser → PTY
  ws.on("message", (raw) => {
    let msg;
    try {
      msg = JSON.parse(raw.toString());
    } catch {
      return;
    }
    if (msg.type === "input" && typeof msg.data === "string") {
      pty.write(msg.data);
    } else if (msg.type === "resize" && Number.isInteger(msg.cols) && Number.isInteger(msg.rows)) {
      try {
        pty.resize(msg.cols, msg.rows);
      } catch (e) {
        console.warn("[pty-server] resize failed:", e.message);
      }
    }
  });

  ws.on("close", () => {
    console.log(`[pty-server] websocket closed for PID ${pty.pid}, killing pty`);
    try {
      pty.kill();
    } catch {
      /* already dead */
    }
  });

  ws.on("error", (e) => {
    console.warn("[pty-server] ws error:", e.message);
  });
});

process.on("SIGINT", () => {
  console.log("[pty-server] SIGINT, shutting down");
  wss.close(() => process.exit(0));
});
