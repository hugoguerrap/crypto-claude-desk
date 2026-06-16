/**
 * Server-side fetchers for the Market Intelligence panel.
 *
 * These call the same upstream APIs that the Polymarket and DefiLlama MCP servers
 * wrap. Keeping the dashboard independent of a running MCP process — the panel
 * works even if Claude Code is closed.
 */

const POLYMARKET_BASE = "https://gamma-api.polymarket.com";
const DEFILLAMA_BASE = "https://api.llama.fi";
const STABLECOIN_BASE = "https://stablecoins.llama.fi";
const FETCH_TIMEOUT_MS = 8000;

async function fetchJson<T>(url: string): Promise<T | null> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  try {
    const res = await fetch(url, {
      signal: controller.signal,
      next: { revalidate: 300 },
    });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

export type PolymarketSnapshot = {
  question: string;
  slug: string;
  leader: string | null;
  leader_pct: number | null;
  volume_usd: number;
  end_date: string | null;
};

type GammaMarket = {
  question?: string;
  slug?: string;
  outcomes?: string | string[];
  outcomePrices?: string | string[];
  volumeNum?: number;
  volume?: number;
  endDate?: string;
};

function parseOutcomes(m: GammaMarket): { name: string; prob: number }[] {
  let names: string[] = [];
  let prices: string[] = [];
  try {
    names = typeof m.outcomes === "string" ? JSON.parse(m.outcomes) : (m.outcomes ?? []);
  } catch {
    names = [];
  }
  try {
    prices = typeof m.outcomePrices === "string" ? JSON.parse(m.outcomePrices) : (m.outcomePrices ?? []);
  } catch {
    prices = [];
  }
  return names.map((n, i) => ({ name: n, prob: parseFloat(prices[i] ?? "0") || 0 }));
}

export async function getPolymarketCryptoSnapshot(): Promise<PolymarketSnapshot[]> {
  const url = `${POLYMARKET_BASE}/markets?active=true&closed=false&limit=8&order=volume24hr&ascending=false&tag=crypto`;
  const data = await fetchJson<GammaMarket[]>(url);
  if (!data || !Array.isArray(data)) return [];
  return data.map((m) => {
    const outcomes = parseOutcomes(m);
    const leader = outcomes.reduce<{ name: string; prob: number } | null>(
      (best, o) => (best == null || o.prob > best.prob ? o : best),
      null
    );
    return {
      question: m.question ?? "",
      slug: m.slug ?? "",
      leader: leader?.name ?? null,
      leader_pct: leader ? Math.round(leader.prob * 1000) / 10 : null,
      volume_usd: m.volumeNum ?? m.volume ?? 0,
      end_date: m.endDate ?? null,
    };
  });
}

export type DefiFlowSnapshot = {
  totalTvlUsd: number | null;
  ethTvlUsd: number | null;
  ethTvlChange7dPct: number | null;
  ethFlowClassification: string | null;
  stablecoinMcapUsd: number | null;
  dexVolume24hUsd: number | null;
  dexVolume24hChangePct: number | null;
  topDex: { name: string; volume_24h_usd: number; change_pct: number } | null;
};

type Chain = { name?: string; tvl?: number };
type HistPoint = { date?: number; tvl?: number };
type StablecoinAsset = { circulating?: Record<string, number | string> };
type StablecoinList = { peggedAssets?: StablecoinAsset[] };
type DexProtocol = { name?: string; total24h?: number; change_1d?: number };
type DexOverview = { total24h?: number; change_1d?: number; protocols?: DexProtocol[] };

function classifyFlow(pct: number | null): string | null {
  if (pct == null) return null;
  if (pct > 10) return "STRONG_INFLOW";
  if (pct > 2) return "INFLOW";
  if (pct < -10) return "STRONG_OUTFLOW";
  if (pct < -2) return "OUTFLOW";
  return "FLAT";
}

export async function getDefiFlowSnapshot(): Promise<DefiFlowSnapshot> {
  const [chains, ethHist, stables, dexOverview] = await Promise.all([
    fetchJson<Chain[]>(`${DEFILLAMA_BASE}/v2/chains`),
    fetchJson<HistPoint[]>(`${DEFILLAMA_BASE}/v2/historicalChainTvl/Ethereum`),
    fetchJson<StablecoinList>(`${STABLECOIN_BASE}/stablecoins?includePrices=false`),
    fetchJson<DexOverview>(`${DEFILLAMA_BASE}/overview/dexs?excludeTotalDataChart=true`),
  ]);

  const totalTvl = chains
    ? chains.reduce((s, c) => s + (c.tvl ?? 0), 0)
    : null;
  const eth = chains?.find((c) => c.name?.toLowerCase() === "ethereum");

  let ethChange7dPct: number | null = null;
  if (ethHist && ethHist.length > 7) {
    const sorted = [...ethHist].sort((a, b) => (a.date ?? 0) - (b.date ?? 0));
    const latest = sorted[sorted.length - 1].tvl ?? 0;
    const baseline = sorted[sorted.length - 8].tvl ?? 0;
    if (baseline > 0) ethChange7dPct = Math.round(((latest - baseline) / baseline) * 10000) / 100;
  }

  const stablecoinMcap = stables?.peggedAssets
    ? stables.peggedAssets.reduce((s, c) => {
        const circ = c.circulating ?? {};
        return s + Object.values(circ).reduce<number>((ss, v) => ss + (typeof v === "number" ? v : 0), 0);
      }, 0)
    : null;

  const topDex = dexOverview?.protocols?.[0]
    ? {
        name: dexOverview.protocols[0].name ?? "?",
        volume_24h_usd: dexOverview.protocols[0].total24h ?? 0,
        change_pct: dexOverview.protocols[0].change_1d ?? 0,
      }
    : null;

  return {
    totalTvlUsd: totalTvl,
    ethTvlUsd: eth?.tvl ?? null,
    ethTvlChange7dPct: ethChange7dPct,
    ethFlowClassification: classifyFlow(ethChange7dPct),
    stablecoinMcapUsd: stablecoinMcap,
    dexVolume24hUsd: dexOverview?.total24h ?? null,
    dexVolume24hChangePct: dexOverview?.change_1d ?? null,
    topDex,
  };
}
