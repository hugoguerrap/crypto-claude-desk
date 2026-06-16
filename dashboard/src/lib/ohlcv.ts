/**
 * Server-side OHLCV fetcher.
 *
 * Hits Binance's public klines endpoint — no auth, generous rate limits,
 * identical data to what CCXT serves. Decouples the dashboard from a running
 * MCP server process.
 */

const BINANCE_BASE = "https://api.binance.com/api/v3";
const FETCH_TIMEOUT_MS = 8000;

export type Candle = {
  time: number; // unix seconds
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

export type Interval = "1m" | "5m" | "15m" | "1h" | "4h" | "1d";

function toBinanceSymbol(symbol: string): string {
  // Accept "ETH", "ETH/USDT", "ETHUSDT" → all become "ETHUSDT"
  const cleaned = symbol.replace("/", "").toUpperCase();
  if (cleaned.endsWith("USDT") || cleaned.endsWith("BUSD") || cleaned.endsWith("USDC")) {
    return cleaned;
  }
  return `${cleaned}USDT`;
}

export async function getOhlcv(
  symbol: string,
  interval: Interval = "1h",
  limit = 200
): Promise<Candle[]> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  try {
    const binanceSym = toBinanceSymbol(symbol);
    const url = `${BINANCE_BASE}/klines?symbol=${binanceSym}&interval=${interval}&limit=${limit}`;
    const res = await fetch(url, {
      signal: controller.signal,
      next: { revalidate: 60 },
    });
    if (!res.ok) return [];
    const raw = (await res.json()) as unknown[];
    if (!Array.isArray(raw)) return [];
    return raw.map((row) => {
      const r = row as (string | number)[];
      return {
        time: Math.floor(Number(r[0]) / 1000),
        open: parseFloat(String(r[1])),
        high: parseFloat(String(r[2])),
        low: parseFloat(String(r[3])),
        close: parseFloat(String(r[4])),
        volume: parseFloat(String(r[5])),
      };
    });
  } catch {
    return [];
  } finally {
    clearTimeout(timer);
  }
}

export async function getCurrentPrice(symbol: string): Promise<number | null> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  try {
    const binanceSym = toBinanceSymbol(symbol);
    const url = `${BINANCE_BASE}/ticker/price?symbol=${binanceSym}`;
    const res = await fetch(url, {
      signal: controller.signal,
      next: { revalidate: 30 },
    });
    if (!res.ok) return null;
    const data = (await res.json()) as { price?: string };
    return data.price ? parseFloat(data.price) : null;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}
