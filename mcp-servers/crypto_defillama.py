#!/usr/bin/env python3
"""
DefiLlama On-Chain Data MCP Server

Provides DeFi TVL, protocol metrics, stablecoin flows, and DEX volume data via
the free public DefiLlama API. No API keys required.

On-chain data is a different signal class than price action — it shows where
capital is actually flowing, not just what's quoting.

7 Tools:
1. get_total_tvl - Total DeFi TVL across all chains
2. get_chain_tvl - Current TVL for a specific chain (Ethereum, Solana, ...)
3. get_protocol_tvl - TVL for a specific protocol (Aave, Uniswap, ...)
4. get_top_protocols - Largest protocols ranked by TVL
5. get_stablecoins_overview - Total stablecoin mcap + breakdown by issuer
6. get_dex_volume_24h - DEX trading volume aggregates by chain
7. get_chain_tvl_change - TVL change over a window (24h/7d/30d) for a chain

Data source: https://api.llama.fi + https://stablecoins.llama.fi (public, no auth)
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import requests
from fastmcp import FastMCP

logger = logging.getLogger(__name__)

mcp = FastMCP("crypto-defillama")

API_BASE = "https://api.llama.fi"
STABLECOIN_BASE = "https://stablecoins.llama.fi"
DEFAULT_TIMEOUT = 30  # Some DefiLlama endpoints (historical TVL, /overview/dexs) return large payloads

# Chain name normalization — DefiLlama is case-sensitive.
CHAIN_ALIASES = {
    "eth": "Ethereum",
    "ethereum": "Ethereum",
    "sol": "Solana",
    "solana": "Solana",
    "bsc": "BSC",
    "bnb": "BSC",
    "arb": "Arbitrum",
    "arbitrum": "Arbitrum",
    "op": "Optimism",
    "optimism": "Optimism",
    "base": "Base",
    "polygon": "Polygon",
    "matic": "Polygon",
    "avalanche": "Avalanche",
    "avax": "Avalanche",
    "tron": "Tron",
    "trx": "Tron",
}


def _normalize_chain(chain: str) -> str:
    """Map common aliases to canonical DefiLlama chain names."""
    if not chain:
        return chain
    key = chain.strip().lower()
    return CHAIN_ALIASES.get(key, chain.strip().title())


def _request(url: str, params: Optional[Dict[str, Any]] = None, timeout: Optional[int] = None) -> Any:
    """GET helper that raises on HTTP errors. Accepts per-call timeout override."""
    resp = requests.get(url, params=params or {}, timeout=timeout or DEFAULT_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _classify_change(pct: Optional[float]) -> str:
    """Categorize a percentage change."""
    if pct is None:
        return "UNKNOWN"
    if pct > 10:
        return "STRONG_INFLOW"
    if pct > 2:
        return "INFLOW"
    if pct < -10:
        return "STRONG_OUTFLOW"
    if pct < -2:
        return "OUTFLOW"
    return "FLAT"


def _validate_limit(limit: int, max_limit: int = 200) -> int:
    if not isinstance(limit, int) or limit <= 0:
        raise ValueError(f"limit must be a positive integer, got {limit}")
    return min(limit, max_limit)


@mcp.tool()
def get_total_tvl() -> Dict[str, Any]:
    """
    Get total DeFi TVL aggregated across all chains.

    Returns the current aggregate value plus the all-chain ranking (top 10).
    Useful as a macro liquidity gauge: rising TVL = more capital allocated to DeFi.

    Returns:
        Total TVL in USD plus top 10 chains by TVL.
    """
    try:
        chains = _request(f"{API_BASE}/v2/chains")
        if not isinstance(chains, list):
            raise ValueError("Unexpected chains response shape")
        total = sum(c.get("tvl", 0) or 0 for c in chains)
        ranked = sorted(chains, key=lambda c: c.get("tvl", 0) or 0, reverse=True)
        top = [
            {
                "name": c.get("name"),
                "tvl_usd": c.get("tvl"),
                "tokenSymbol": c.get("tokenSymbol"),
                "share_pct": round(((c.get("tvl") or 0) / total) * 100, 2) if total else 0,
            }
            for c in ranked[:10]
        ]
        return {
            "success": True,
            "total_tvl_usd": total,
            "total_chains": len(chains),
            "top_10_chains": top,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.exception("get_total_tvl failed")
        return {"success": False, "error": str(e), "error_type": type(e).__name__}


@mcp.tool()
def get_chain_tvl(chain: str = "Ethereum") -> Dict[str, Any]:
    """
    Get current TVL for a specific chain.

    Args:
        chain: Chain name or alias (e.g. "Ethereum", "eth", "Solana", "Arbitrum")

    Returns:
        Current TVL and rank relative to all chains.
    """
    try:
        if not chain or not isinstance(chain, str):
            raise ValueError("chain must be a non-empty string")
        normalized = _normalize_chain(chain)
        chains = _request(f"{API_BASE}/v2/chains")
        if not isinstance(chains, list):
            raise ValueError("Unexpected chains response shape")

        target = next((c for c in chains if (c.get("name") or "").lower() == normalized.lower()), None)
        if not target:
            return {
                "success": False,
                "error": f"Chain '{chain}' not found (normalized: '{normalized}')",
                "error_type": "NotFound",
                "chain": chain,
            }
        ranked = sorted(chains, key=lambda c: c.get("tvl", 0) or 0, reverse=True)
        rank = next((i + 1 for i, c in enumerate(ranked) if c is target), None)
        return {
            "success": True,
            "chain": target.get("name"),
            "tvl_usd": target.get("tvl"),
            "token_symbol": target.get("tokenSymbol"),
            "rank": rank,
            "total_chains": len(chains),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.exception("get_chain_tvl failed")
        return {"success": False, "error": str(e), "error_type": type(e).__name__, "chain": chain}


@mcp.tool()
def get_protocol_tvl(protocol: str) -> Dict[str, Any]:
    """
    Get TVL detail for a specific DeFi protocol.

    Args:
        protocol: Protocol slug (e.g. "aave", "uniswap", "lido", "ethena")

    Returns:
        Current TVL plus per-chain breakdown if available.
    """
    try:
        if not protocol or not isinstance(protocol, str):
            raise ValueError("protocol must be a non-empty string")
        slug = protocol.strip().lower()
        data = _request(f"{API_BASE}/protocol/{slug}")
        if not isinstance(data, dict) or "name" not in data:
            return {
                "success": False,
                "error": f"Protocol '{protocol}' not found",
                "error_type": "NotFound",
                "protocol": protocol,
            }
        # currentChainTvls is a chain -> tvl mapping
        chains = data.get("currentChainTvls") or {}
        per_chain = sorted(
            ({"chain": k, "tvl_usd": v} for k, v in chains.items()),
            key=lambda c: c["tvl_usd"] or 0,
            reverse=True,
        )
        total = sum(c["tvl_usd"] or 0 for c in per_chain)
        return {
            "success": True,
            "protocol": data.get("name"),
            "slug": data.get("slug") or slug,
            "category": data.get("category"),
            "chains": data.get("chains"),
            "total_tvl_usd": total,
            "per_chain_tvl": per_chain[:20],
            "change_1d_pct": data.get("change_1d"),
            "change_7d_pct": data.get("change_7d"),
            "url": data.get("url"),
            "twitter": data.get("twitter"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.exception("get_protocol_tvl failed")
        return {"success": False, "error": str(e), "error_type": type(e).__name__, "protocol": protocol}


@mcp.tool()
def get_top_protocols(limit: int = 20, category: Optional[str] = None) -> Dict[str, Any]:
    """
    Get the largest DeFi protocols ranked by TVL.

    Args:
        limit: Number of protocols to return (1-200, default 20)
        category: Optional filter by category (e.g. "Lending", "Dexes", "Liquid Staking")

    Returns:
        Top protocols with TVL, category, chains, and recent change.
    """
    try:
        limit = _validate_limit(limit)
        protocols = _request(f"{API_BASE}/protocols")
        if not isinstance(protocols, list):
            raise ValueError("Unexpected protocols response shape")
        if category:
            cat_lower = category.strip().lower()
            protocols = [p for p in protocols if (p.get("category") or "").lower() == cat_lower]
        ranked = sorted(protocols, key=lambda p: p.get("tvl") or 0, reverse=True)
        top = [
            {
                "name": p.get("name"),
                "slug": p.get("slug"),
                "category": p.get("category"),
                "tvl_usd": p.get("tvl"),
                "change_1d_pct": p.get("change_1d"),
                "change_7d_pct": p.get("change_7d"),
                "chains": p.get("chains", [])[:5],
                "mcap": p.get("mcap"),
            }
            for p in ranked[:limit]
        ]
        return {
            "success": True,
            "count": len(top),
            "category": category,
            "protocols": top,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.exception("get_top_protocols failed")
        return {"success": False, "error": str(e), "error_type": type(e).__name__}


@mcp.tool()
def get_stablecoins_overview() -> Dict[str, Any]:
    """
    Get total stablecoin market cap and top issuers.

    Stablecoin supply changes are a leading indicator of crypto buying power:
    growing supply suggests fresh capital entering the system.

    Returns:
        Total mcap, count, and top 10 stablecoins by mcap.
    """
    try:
        data = _request(f"{STABLECOIN_BASE}/stablecoins", params={"includePrices": "true"})
        if not isinstance(data, dict):
            raise ValueError("Unexpected stablecoins response shape")
        coins = data.get("peggedAssets", [])
        # Each pegged asset has `circulating` with sub-keys like peggedUSD
        def mcap_of(coin):
            circ = coin.get("circulating") or {}
            return sum(v for v in circ.values() if isinstance(v, (int, float)))

        ranked = sorted(coins, key=mcap_of, reverse=True)
        total_mcap = sum(mcap_of(c) for c in coins)
        top = [
            {
                "name": c.get("name"),
                "symbol": c.get("symbol"),
                "mcap_usd": mcap_of(c),
                "share_pct": round((mcap_of(c) / total_mcap) * 100, 2) if total_mcap else 0,
                "chains": c.get("chains", [])[:5],
                "price": c.get("price"),
            }
            for c in ranked[:10]
        ]
        return {
            "success": True,
            "total_mcap_usd": total_mcap,
            "total_stablecoins": len(coins),
            "top_10": top,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.exception("get_stablecoins_overview failed")
        return {"success": False, "error": str(e), "error_type": type(e).__name__}


@mcp.tool()
def get_dex_volume_24h(chain: Optional[str] = None) -> Dict[str, Any]:
    """
    Get 24h DEX trading volume.

    Args:
        chain: Optional chain filter (e.g. "Ethereum", "Solana"). If omitted,
               returns the global cross-chain aggregate.

    Returns:
        Total 24h DEX volume plus top DEX protocols by volume.
    """
    try:
        if chain:
            normalized = _normalize_chain(chain)
            data = _request(f"{API_BASE}/overview/dexs/{normalized}", params={"excludeTotalDataChart": "true"}, timeout=60)
        else:
            data = _request(f"{API_BASE}/overview/dexs", params={"excludeTotalDataChart": "true"}, timeout=60)
        if not isinstance(data, dict):
            raise ValueError("Unexpected DEX overview response shape")
        protocols = data.get("protocols") or []
        ranked = sorted(protocols, key=lambda p: p.get("total24h") or 0, reverse=True)
        top = [
            {
                "name": p.get("name"),
                "volume_24h_usd": p.get("total24h"),
                "volume_7d_usd": p.get("total7d"),
                "change_24h_pct": p.get("change_1d"),
                "chains": p.get("chains", [])[:5],
            }
            for p in ranked[:10]
        ]
        return {
            "success": True,
            "chain": chain or "all_chains",
            "total_volume_24h_usd": data.get("total24h"),
            "total_volume_7d_usd": data.get("total7d"),
            "change_24h_pct": data.get("change_1d"),
            "top_dexes": top,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.exception("get_dex_volume_24h failed")
        return {"success": False, "error": str(e), "error_type": type(e).__name__, "chain": chain}


@mcp.tool()
def get_chain_tvl_change(chain: str = "Ethereum", days: int = 7) -> Dict[str, Any]:
    """
    Calculate TVL change over a window for a specific chain.

    Args:
        chain: Chain name or alias (default "Ethereum")
        days: Lookback window (1-365, default 7)

    Returns:
        TVL now vs `days` ago with absolute and percent change, classified as
        STRONG_INFLOW / INFLOW / FLAT / OUTFLOW / STRONG_OUTFLOW.
    """
    try:
        if not isinstance(days, int) or days <= 0 or days > 365:
            raise ValueError("days must be a positive integer <= 365")
        normalized = _normalize_chain(chain)
        history = _request(f"{API_BASE}/v2/historicalChainTvl/{normalized}", timeout=60)
        if not isinstance(history, list) or len(history) == 0:
            return {
                "success": False,
                "error": f"No TVL history found for chain '{chain}'",
                "error_type": "NotFound",
                "chain": chain,
            }
        # Each item: { date: unix_seconds, tvl: usd }
        sorted_hist = sorted(history, key=lambda h: h.get("date") or 0)
        latest = sorted_hist[-1]
        cutoff_idx = max(0, len(sorted_hist) - 1 - days)
        baseline = sorted_hist[cutoff_idx]
        latest_tvl = latest.get("tvl") or 0
        baseline_tvl = baseline.get("tvl") or 0
        change_usd = latest_tvl - baseline_tvl
        change_pct = ((latest_tvl - baseline_tvl) / baseline_tvl * 100) if baseline_tvl else None
        return {
            "success": True,
            "chain": normalized,
            "days": days,
            "latest_tvl_usd": latest_tvl,
            "baseline_tvl_usd": baseline_tvl,
            "change_usd": change_usd,
            "change_pct": round(change_pct, 2) if change_pct is not None else None,
            "flow_classification": _classify_change(change_pct),
            "latest_date_unix": latest.get("date"),
            "baseline_date_unix": baseline.get("date"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.exception("get_chain_tvl_change failed")
        return {"success": False, "error": str(e), "error_type": type(e).__name__, "chain": chain}


if __name__ == "__main__":
    mcp.run()
