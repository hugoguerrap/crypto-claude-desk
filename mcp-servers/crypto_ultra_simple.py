#!/usr/bin/env python3
"""
Crypto Data MCP Server - CoinGecko API
Market metadata: prices, rankings, history, global stats, fear/greed, dominance.
"""

from fastmcp import FastMCP
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Any
import logging

from validators import validate_coin_id, validate_positive_int

logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("crypto-ultra-simple")


@mcp.tool()
def get_bitcoin_price() -> dict:
    """Get current Bitcoin price in USD"""
    try:
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {"ids": "bitcoin", "vs_currencies": "usd"}

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        return {
            "bitcoin_price_usd": data["bitcoin"]["usd"],
            "status": "success"
        }

    except Exception as e:
        logger.exception("get_bitcoin_price failed")
        return {
            "error": str(e),
            "error_type": type(e).__name__,
            "status": "error"
        }

@mcp.tool()
def get_crypto_prices(coins: str = "bitcoin,ethereum") -> dict:
    """Get prices for multiple cryptocurrencies (comma-separated)"""
    try:
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {"ids": coins, "vs_currencies": "usd", "include_24hr_change": "true"}

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        return {
            "prices": data,
            "status": "success"
        }

    except Exception as e:
        logger.exception("get_crypto_prices failed")
        return {
            "error": str(e),
            "error_type": type(e).__name__,
            "status": "error"
        }

@mcp.tool()
def get_coin_details(coin_id: str = "bitcoin") -> dict:
    """Get detailed information about a specific cryptocurrency"""
    try:
        coin_id = validate_coin_id(coin_id)

        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}"
        params = {"localization": "false", "tickers": "false", "community_data": "false", "developer_data": "false"}

        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()

        return {
            "coin_details": {
                "id": data.get("id"),
                "symbol": data.get("symbol", "").upper(),
                "name": data.get("name"),
                "current_price_usd": data.get("market_data", {}).get("current_price", {}).get("usd"),
                "market_cap_usd": data.get("market_data", {}).get("market_cap", {}).get("usd"),
                "market_cap_rank": data.get("market_cap_rank"),
                "total_volume_usd": data.get("market_data", {}).get("total_volume", {}).get("usd"),
                "price_change_24h_pct": data.get("market_data", {}).get("price_change_percentage_24h"),
                "price_change_7d_pct": data.get("market_data", {}).get("price_change_percentage_7d"),
                "price_change_30d_pct": data.get("market_data", {}).get("price_change_percentage_30d"),
                "circulating_supply": data.get("market_data", {}).get("circulating_supply"),
                "max_supply": data.get("market_data", {}).get("max_supply"),
                "all_time_high_usd": data.get("market_data", {}).get("ath", {}).get("usd"),
                "all_time_low_usd": data.get("market_data", {}).get("atl", {}).get("usd"),
                "description": data.get("description", {}).get("en", "")[:500] + "...",
                "homepage": data.get("links", {}).get("homepage", [None])[0],
                "categories": data.get("categories", [])
            },
            "status": "success"
        }

    except Exception as e:
        logger.exception("get_coin_details failed")
        return {
            "error": str(e),
            "error_type": type(e).__name__,
            "status": "error"
        }

@mcp.tool()
def get_market_rankings(limit: int = 50) -> dict:
    """Get cryptocurrency market cap rankings"""
    try:
        limit = validate_positive_int(limit, "limit", max_value=250)

        url = "https://api.coingecko.com/api/v3/coins/markets"
        params = {
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": limit,
            "page": 1,
            "sparkline": "false"
        }

        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()

        rankings = []
        for coin in data:
            rankings.append({
                "rank": coin.get("market_cap_rank"),
                "id": coin.get("id"),
                "symbol": coin.get("symbol", "").upper(),
                "name": coin.get("name"),
                "current_price_usd": coin.get("current_price"),
                "market_cap_usd": coin.get("market_cap"),
                "total_volume_usd": coin.get("total_volume"),
                "price_change_24h_pct": coin.get("price_change_percentage_24h"),
                "circulating_supply": coin.get("circulating_supply")
            })

        return {
            "rankings": rankings,
            "total_coins": len(rankings),
            "status": "success"
        }

    except Exception as e:
        logger.exception("get_market_rankings failed")
        return {
            "error": str(e),
            "error_type": type(e).__name__,
            "status": "error"
        }

@mcp.tool()
def get_price_history(coin_id: str = "bitcoin", days: int = 30) -> dict:
    """Get historical price data for cryptocurrency"""
    try:
        coin_id = validate_coin_id(coin_id)
        days = validate_positive_int(days, "days", max_value=365)

        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
        params = {"vs_currency": "usd", "days": days}

        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()

        prices = data.get("prices", [])
        volumes = data.get("total_volumes", [])

        history = []
        for i, price_point in enumerate(prices):
            timestamp = price_point[0]
            price = price_point[1]
            volume = volumes[i][1] if i < len(volumes) else 0

            history.append({
                "timestamp": datetime.fromtimestamp(timestamp/1000).isoformat(),
                "price_usd": price,
                "volume_usd": volume
            })

        if len(prices) >= 2:
            start_price = prices[0][1]
            end_price = prices[-1][1]
            performance_pct = ((end_price - start_price) / start_price) * 100

            all_prices = [p[1] for p in prices]
            high_price = max(all_prices)
            low_price = min(all_prices)
        else:
            performance_pct = 0
            high_price = 0
            low_price = 0

        return {
            "coin_id": coin_id,
            "period_days": days,
            "performance_pct": performance_pct,
            "high_price_usd": high_price,
            "low_price_usd": low_price,
            "data_points": len(history),
            "price_history": history[-50:],
            "status": "success"
        }

    except Exception as e:
        logger.exception("get_price_history failed")
        return {
            "error": str(e),
            "error_type": type(e).__name__,
            "status": "error"
        }

@mcp.tool()
def get_market_trends() -> dict:
    """Get general market trends and statistics"""
    try:
        global_url = "https://api.coingecko.com/api/v3/global"
        global_response = requests.get(global_url, timeout=10)
        global_response.raise_for_status()
        global_data = global_response.json().get("data", {})

        trending_url = "https://api.coingecko.com/api/v3/search/trending"
        trending_response = requests.get(trending_url, timeout=10)
        trending_response.raise_for_status()
        trending_data = trending_response.json()

        trending_coins = []
        for coin in trending_data.get("coins", [])[:10]:
            coin_data = coin.get("item", {})
            trending_coins.append({
                "id": coin_data.get("id"),
                "name": coin_data.get("name"),
                "symbol": coin_data.get("symbol", "").upper(),
                "market_cap_rank": coin_data.get("market_cap_rank"),
                "score": coin_data.get("score")
            })

        return {
            "market_trends": {
                "total_market_cap_usd": global_data.get("total_market_cap", {}).get("usd"),
                "total_volume_24h_usd": global_data.get("total_volume", {}).get("usd"),
                "market_cap_change_24h_pct": global_data.get("market_cap_change_percentage_24h_usd"),
                "active_cryptocurrencies": global_data.get("active_cryptocurrencies"),
                "markets": global_data.get("markets"),
                "trending_searches": trending_coins
            },
            "status": "success"
        }

    except Exception as e:
        logger.exception("get_market_trends failed")
        return {
            "error": str(e),
            "error_type": type(e).__name__,
            "status": "error"
        }

@mcp.tool()
def compare_crypto_performance(coins_list: str = "bitcoin,ethereum,cardano") -> dict:
    """Compare performance of multiple cryptocurrencies"""
    try:
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {
            "ids": coins_list,
            "vs_currencies": "usd",
            "include_24hr_change": "true",
            "include_7d_change": "true",
            "include_30d_change": "true",
            "include_market_cap": "true"
        }

        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()

        comparison = []
        for coin_id, coin_data in data.items():
            comparison.append({
                "coin_id": coin_id,
                "current_price_usd": coin_data.get("usd"),
                "market_cap_usd": coin_data.get("usd_market_cap"),
                "change_24h_pct": coin_data.get("usd_24h_change"),
                "change_7d_pct": coin_data.get("usd_7d_change"),
                "change_30d_pct": coin_data.get("usd_30d_change")
            })

        comparison.sort(key=lambda x: x.get("change_24h_pct", 0), reverse=True)

        best_24h = comparison[0] if comparison else None
        worst_24h = comparison[-1] if comparison else None

        return {
            "coins_compared": coins_list.split(","),
            "comparison": comparison,
            "best_performer_24h": best_24h,
            "worst_performer_24h": worst_24h,
            "status": "success"
        }

    except Exception as e:
        logger.exception("compare_crypto_performance failed")
        return {
            "error": str(e),
            "error_type": type(e).__name__,
            "status": "error"
        }

@mcp.tool()
def get_global_market_stats() -> dict:
    """Get comprehensive global cryptocurrency market statistics"""
    try:
        url = "https://api.coingecko.com/api/v3/global"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json().get("data", {})

        return {
            "global_market_stats": {
                "total_market_cap_usd": data.get("total_market_cap", {}).get("usd"),
                "total_volume_24h_usd": data.get("total_volume", {}).get("usd"),
                "market_cap_change_24h_pct": data.get("market_cap_change_percentage_24h_usd"),
                "bitcoin_dominance_pct": data.get("market_cap_percentage", {}).get("btc"),
                "ethereum_dominance_pct": data.get("market_cap_percentage", {}).get("eth"),
                "active_cryptocurrencies": data.get("active_cryptocurrencies"),
                "upcoming_icos": data.get("upcoming_icos"),
                "ongoing_icos": data.get("ongoing_icos"),
                "ended_icos": data.get("ended_icos"),
                "markets": data.get("markets"),
                "market_cap_change_24h_usd": data.get("total_market_cap", {}).get("usd", 0) * (data.get("market_cap_change_percentage_24h_usd", 0) / 100)
            },
            "status": "success"
        }

    except Exception as e:
        logger.exception("get_global_market_stats failed")
        return {
            "error": str(e),
            "error_type": type(e).__name__,
            "status": "error"
        }

@mcp.tool()
def get_fear_greed_index() -> dict:
    """Get crypto Fear & Greed Index from alternative.me"""
    try:
        url = "https://api.alternative.me/fng/"
        params = {"limit": 30}

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if "data" not in data:
            raise Exception("No data in Fear & Greed API response")

        current = data["data"][0] if data["data"] else {}
        historical = data["data"][:7] if len(data["data"]) >= 7 else data["data"]

        if historical:
            avg_7d = sum(int(item["value"]) for item in historical) / len(historical)
        else:
            avg_7d = 0

        return {
            "fear_greed_index": {
                "current_value": int(current.get("value", 0)),
                "current_classification": current.get("value_classification", "Unknown"),
                "timestamp": current.get("timestamp", ""),
                "average_7d": round(avg_7d, 1),
                "interpretation": {
                    "0-24": "Extreme Fear",
                    "25-44": "Fear",
                    "45-55": "Neutral",
                    "56-75": "Greed",
                    "76-100": "Extreme Greed"
                },
                "last_7_days": [{
                    "value": int(item["value"]),
                    "classification": item["value_classification"],
                    "timestamp": item["timestamp"]
                } for item in historical]
            },
            "status": "success"
        }

    except Exception as e:
        logger.exception("get_fear_greed_index failed")
        return {
            "error": str(e),
            "error_type": type(e).__name__,
            "status": "error"
        }

@mcp.tool()
def get_dominance_stats() -> dict:
    """Get Bitcoin and Ethereum market dominance statistics"""
    try:
        url = "https://api.coingecko.com/api/v3/global"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json().get("data", {})

        btc_dominance = data.get("market_cap_percentage", {}).get("btc", 0)
        eth_dominance = data.get("market_cap_percentage", {}).get("eth", 0)
        others_dominance = 100 - btc_dominance - eth_dominance

        return {
            "dominance_stats": {
                "bitcoin_dominance_pct": round(btc_dominance, 2),
                "ethereum_dominance_pct": round(eth_dominance, 2),
                "others_dominance_pct": round(others_dominance, 2),
                "btc_eth_combined_pct": round(btc_dominance + eth_dominance, 2),
                "total_market_cap_usd": data.get("total_market_cap", {}).get("usd"),
                "dominance_interpretation": {
                    "btc_status": "High" if btc_dominance > 50 else "Medium" if btc_dominance > 40 else "Low",
                    "eth_status": "High" if eth_dominance > 20 else "Medium" if eth_dominance > 15 else "Low",
                    "market_concentration": "High" if (btc_dominance + eth_dominance) > 70 else "Medium" if (btc_dominance + eth_dominance) > 60 else "Low"
                }
            },
            "status": "success"
        }

    except Exception as e:
        logger.exception("get_dominance_stats failed")
        return {
            "error": str(e),
            "error_type": type(e).__name__,
            "status": "error"
        }

@mcp.tool()
def get_crypto_categories() -> dict:
    """Get cryptocurrency categories (DeFi, Layer1, Meme coins, etc.)"""
    try:
        categories_url = "https://api.coingecko.com/api/v3/coins/categories"
        response = requests.get(categories_url, timeout=15)
        response.raise_for_status()
        categories_data = response.json()

        categories_sorted = sorted(categories_data, key=lambda x: x.get("market_cap", 0), reverse=True)
        top_categories = categories_sorted[:20]

        categories_info = []
        for category in top_categories:
            categories_info.append({
                "id": category.get("id"),
                "name": category.get("name"),
                "market_cap_usd": category.get("market_cap"),
                "market_cap_change_24h_pct": category.get("market_cap_change_24h"),
                "volume_24h_usd": category.get("volume_24h"),
                "top_3_coins": category.get("top_3_coins", [])[:3]
            })

        key_categories = {}
        for cat in categories_info:
            cat_name = cat["name"].lower()
            if "defi" in cat_name or "decentralized finance" in cat_name:
                key_categories["DeFi"] = cat
            elif "layer 1" in cat_name or "smart contract" in cat_name:
                key_categories["Layer1"] = cat
            elif "meme" in cat_name:
                key_categories["Memes"] = cat
            elif "nft" in cat_name or "collectible" in cat_name:
                key_categories["NFT"] = cat
            elif "gaming" in cat_name:
                key_categories["Gaming"] = cat

        return {
            "crypto_categories": {
                "total_categories": len(categories_data),
                "top_categories": categories_info,
                "key_categories": key_categories,
                "market_overview": {
                    "largest_category": categories_info[0] if categories_info else None,
                    "fastest_growing_24h": max(categories_info, key=lambda x: x.get("market_cap_change_24h_pct", 0)) if categories_info else None
                }
            },
            "status": "success"
        }

    except Exception as e:
        logger.exception("get_crypto_categories failed")
        return {
            "error": str(e),
            "error_type": type(e).__name__,
            "status": "error"
        }

if __name__ == "__main__":
    mcp.run()
