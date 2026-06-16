#!/usr/bin/env python3
"""
Polymarket Prediction Market MCP Server

Provides access to Polymarket prediction market data via the free public Gamma API.
No API keys required. Prediction markets give the "wisdom of crowds" probability
for real-world events priced by capital — a strong alternative-data signal.

6 Tools:
1. search_markets - Full-text search across active markets
2. get_market_probabilities - Outcome probabilities for a specific market
3. get_trending_markets - Most active markets by 24h volume
4. get_crypto_markets - Markets tagged with crypto-related categories
5. get_market_detail - Full detail for one market (description, dates, volume)
6. get_top_volume_markets - Largest markets by total volume

Data source: https://gamma-api.polymarket.com (public, no auth)
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests
from fastmcp import FastMCP

logger = logging.getLogger(__name__)

mcp = FastMCP("crypto-polymarket")

GAMMA_BASE = "https://gamma-api.polymarket.com"
DEFAULT_TIMEOUT = 15

# Categories that overlap with crypto trading decisions.
CRYPTO_TAGS = {
    "Crypto", "Bitcoin", "Ethereum", "Solana", "Cryptocurrency",
    "BTC", "ETH", "SOL", "DeFi", "Stablecoins",
}

# Sentiment thresholds (probability)
PROB_HIGH_CONFIDENCE = 0.75
PROB_LOW_CONFIDENCE = 0.25


def _request(path: str, params: Optional[Dict[str, Any]] = None) -> Any:
    """Issue a GET against the Gamma API and return parsed JSON."""
    url = f"{GAMMA_BASE}{path}"
    resp = requests.get(url, params=params or {}, timeout=DEFAULT_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _parse_outcomes(market: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Combine `outcomes` and `outcomePrices` arrays into a list of dicts."""
    raw_outcomes = market.get("outcomes")
    raw_prices = market.get("outcomePrices")
    if isinstance(raw_outcomes, str):
        try:
            raw_outcomes = json.loads(raw_outcomes)
        except json.JSONDecodeError:
            raw_outcomes = []
    if isinstance(raw_prices, str):
        try:
            raw_prices = json.loads(raw_prices)
        except json.JSONDecodeError:
            raw_prices = []
    raw_outcomes = raw_outcomes or []
    raw_prices = raw_prices or []
    result = []
    for i, name in enumerate(raw_outcomes):
        try:
            price = float(raw_prices[i]) if i < len(raw_prices) else None
        except (TypeError, ValueError):
            price = None
        result.append({
            "outcome": name,
            "probability": price,
            "probability_pct": round(price * 100, 2) if price is not None else None,
        })
    return result


def _classify_consensus(outcomes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Summarize the market's consensus state."""
    if not outcomes:
        return {"state": "UNKNOWN", "leader": None, "leader_probability": None}
    valid = [o for o in outcomes if o.get("probability") is not None]
    if not valid:
        return {"state": "NO_PRICES", "leader": None, "leader_probability": None}
    leader = max(valid, key=lambda o: o["probability"])
    prob = leader["probability"]
    if prob >= PROB_HIGH_CONFIDENCE:
        state = "HIGH_CONFIDENCE"
    elif prob <= PROB_LOW_CONFIDENCE:
        state = "LOW_CONFIDENCE"
    else:
        state = "UNCERTAIN"
    return {
        "state": state,
        "leader": leader["outcome"],
        "leader_probability": prob,
        "leader_probability_pct": round(prob * 100, 2),
    }


def _shape_market(market: Dict[str, Any]) -> Dict[str, Any]:
    """Trim the verbose Gamma market object down to the useful fields."""
    outcomes = _parse_outcomes(market)
    consensus = _classify_consensus(outcomes)
    return {
        "id": market.get("id"),
        "slug": market.get("slug"),
        "question": market.get("question"),
        "category": market.get("category"),
        "active": market.get("active"),
        "closed": market.get("closed"),
        "accepting_orders": market.get("acceptingOrders"),
        "volume_usd": market.get("volumeNum") or market.get("volume"),
        "liquidity_usd": market.get("liquidityNum") or market.get("liquidity"),
        "start_date": market.get("startDate"),
        "end_date": market.get("endDate"),
        "outcomes": outcomes,
        "consensus": consensus,
    }


def _validate_limit(limit: int, max_limit: int = 100) -> int:
    if not isinstance(limit, int) or limit <= 0:
        raise ValueError(f"limit must be a positive integer, got {limit}")
    return min(limit, max_limit)


@mcp.tool()
def search_markets(query: str, limit: int = 10, active_only: bool = True) -> Dict[str, Any]:
    """
    Search Polymarket prediction markets by question text.

    Args:
        query: Free-text search (e.g. "Fed rate cut", "BTC 100k", "Trump")
        limit: Maximum markets to return (1-100, default 10)
        active_only: Only return markets currently open for trading

    Returns:
        Matching markets with question, outcomes, current probabilities, and volume.
    """
    try:
        if not query or not isinstance(query, str):
            raise ValueError("query must be a non-empty string")
        limit = _validate_limit(limit)

        params: Dict[str, Any] = {
            "limit": limit,
            "order": "volume24hr",
            "ascending": "false",
        }
        if active_only:
            params["active"] = "true"
            params["closed"] = "false"

        data = _request("/markets", params={**params, "q": query.strip()})
        markets = data if isinstance(data, list) else data.get("data", [])

        results = [_shape_market(m) for m in markets]
        return {
            "success": True,
            "query": query,
            "active_only": active_only,
            "count": len(results),
            "markets": results,
        }
    except Exception as e:
        logger.exception("search_markets failed")
        return {"success": False, "error": str(e), "error_type": type(e).__name__, "query": query}


@mcp.tool()
def get_market_probabilities(slug_or_id: str) -> Dict[str, Any]:
    """
    Get the current outcome probabilities for a single market.

    This is the main consumption pattern: ask the market "what is the probability of X?"
    and let the wisdom of crowds answer.

    Args:
        slug_or_id: Market slug (e.g. "fed-cuts-in-september-2026") or numeric id

    Returns:
        Outcomes with probabilities (0-1) and consensus classification.
    """
    try:
        if not slug_or_id or not isinstance(slug_or_id, str):
            raise ValueError("slug_or_id must be a non-empty string")
        key = slug_or_id.strip()

        if key.isdigit():
            data = _request("/markets", params={"id": key})
        else:
            data = _request("/markets", params={"slug": key})
        markets = data if isinstance(data, list) else data.get("data", [])
        if not markets:
            return {
                "success": False,
                "error": f"No market found for '{slug_or_id}'",
                "error_type": "NotFound",
                "slug_or_id": slug_or_id,
            }
        shaped = _shape_market(markets[0])
        return {
            "success": True,
            "slug_or_id": slug_or_id,
            "question": shaped["question"],
            "outcomes": shaped["outcomes"],
            "consensus": shaped["consensus"],
            "volume_usd": shaped["volume_usd"],
            "liquidity_usd": shaped["liquidity_usd"],
            "active": shaped["active"],
            "closed": shaped["closed"],
            "end_date": shaped["end_date"],
        }
    except Exception as e:
        logger.exception("get_market_probabilities failed")
        return {"success": False, "error": str(e), "error_type": type(e).__name__, "slug_or_id": slug_or_id}


@mcp.tool()
def get_trending_markets(limit: int = 10, category: Optional[str] = None) -> Dict[str, Any]:
    """
    Get the most active prediction markets ordered by 24h volume.

    Args:
        limit: Maximum markets to return (1-100, default 10)
        category: Optional category filter (e.g. "Crypto", "Politics", "Sports")

    Returns:
        Trending markets with current consensus and volume.
    """
    try:
        limit = _validate_limit(limit)
        params: Dict[str, Any] = {
            "limit": limit,
            "active": "true",
            "closed": "false",
            "order": "volume24hr",
            "ascending": "false",
        }
        if category:
            params["category"] = category

        data = _request("/markets", params=params)
        markets = data if isinstance(data, list) else data.get("data", [])
        return {
            "success": True,
            "category": category,
            "count": len(markets),
            "markets": [_shape_market(m) for m in markets],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.exception("get_trending_markets failed")
        return {"success": False, "error": str(e), "error_type": type(e).__name__}


@mcp.tool()
def get_crypto_markets(limit: int = 20) -> Dict[str, Any]:
    """
    Get currently active markets tagged with crypto-related categories.

    Use this when an agent wants the market consensus for crypto-specific events:
    ETF approvals, price milestones, regulatory rulings, exchange listings, etc.

    Args:
        limit: Maximum markets to return (1-100, default 20)

    Returns:
        Crypto-tagged markets with probabilities.
    """
    try:
        limit = _validate_limit(limit)
        params = {
            "limit": limit,
            "active": "true",
            "closed": "false",
            "order": "volume24hr",
            "ascending": "false",
            "tag": "crypto",
        }
        data = _request("/markets", params=params)
        markets = data if isinstance(data, list) else data.get("data", [])

        # Best-effort filter: only keep those whose category/tags match known crypto labels.
        filtered = []
        for m in markets:
            cat = (m.get("category") or "").strip()
            if not cat or cat in CRYPTO_TAGS or any(t in (cat or "") for t in CRYPTO_TAGS):
                filtered.append(_shape_market(m))

        # If filter produced nothing meaningful, fall back to the raw list.
        if not filtered:
            filtered = [_shape_market(m) for m in markets]

        return {
            "success": True,
            "count": len(filtered),
            "markets": filtered,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.exception("get_crypto_markets failed")
        return {"success": False, "error": str(e), "error_type": type(e).__name__}


@mcp.tool()
def get_market_detail(slug: str) -> Dict[str, Any]:
    """
    Get full detail for a single market by its slug.

    Includes the human-readable description and resolution source, which often
    explain exactly what conditions must be met for each outcome.

    Args:
        slug: Market slug (e.g. "btc-above-100k-by-end-of-2026")

    Returns:
        Full market record with description, dates, volume, outcomes.
    """
    try:
        if not slug or not isinstance(slug, str):
            raise ValueError("slug must be a non-empty string")
        data = _request("/markets", params={"slug": slug.strip()})
        markets = data if isinstance(data, list) else data.get("data", [])
        if not markets:
            return {
                "success": False,
                "error": f"No market found for slug '{slug}'",
                "error_type": "NotFound",
                "slug": slug,
            }
        m = markets[0]
        shaped = _shape_market(m)
        shaped.update({
            "success": True,
            "description": m.get("description"),
            "resolution_source": m.get("resolutionSource"),
            "category": m.get("category"),
        })
        return shaped
    except Exception as e:
        logger.exception("get_market_detail failed")
        return {"success": False, "error": str(e), "error_type": type(e).__name__, "slug": slug}


@mcp.tool()
def get_top_volume_markets(limit: int = 10) -> Dict[str, Any]:
    """
    Get the largest active markets by all-time volume.

    These represent the highest-conviction collective bets where capital is actually
    at stake — usually the most informative signals.

    Args:
        limit: Maximum markets to return (1-100, default 10)

    Returns:
        Top markets sorted by total volume.
    """
    try:
        limit = _validate_limit(limit)
        params = {
            "limit": limit,
            "active": "true",
            "closed": "false",
            "order": "volume",
            "ascending": "false",
        }
        data = _request("/markets", params=params)
        markets = data if isinstance(data, list) else data.get("data", [])
        return {
            "success": True,
            "count": len(markets),
            "markets": [_shape_market(m) for m in markets],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.exception("get_top_volume_markets failed")
        return {"success": False, "error": str(e), "error_type": type(e).__name__}


if __name__ == "__main__":
    mcp.run()
