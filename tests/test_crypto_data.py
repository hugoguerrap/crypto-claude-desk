"""
Tests for crypto_ultra_simple.py (crypto-data) MCP server.
All HTTP calls to CoinGecko are mocked.
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mcp-servers"))
from helpers import call_tool


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

def _mock_response(json_data, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.text = str(json_data)
    return resp


PRICE_RESPONSE = {"bitcoin": {"usd": 97500, "usd_24h_change": 1.5, "usd_market_cap": 1900000000000, "usd_24h_vol": 35000000000}}
PRICES_MULTI = {
    "bitcoin": {"usd": 97500, "usd_24h_change": 1.5, "usd_market_cap": 1900000000000, "usd_24h_vol": 35000000000},
    "ethereum": {"usd": 3200, "usd_24h_change": 2.1, "usd_market_cap": 380000000000, "usd_24h_vol": 15000000000},
}
COIN_DETAILS = {
    "id": "bitcoin", "symbol": "btc", "name": "Bitcoin",
    "market_data": {
        "current_price": {"usd": 97500},
        "market_cap": {"usd": 1900000000000},
        "total_volume": {"usd": 35000000000},
        "price_change_percentage_24h": 1.5,
        "price_change_percentage_7d": 5.2,
        "price_change_percentage_30d": 12.3,
        "ath": {"usd": 108000},
        "atl": {"usd": 67.81},
        "circulating_supply": 19600000,
        "total_supply": 21000000,
        "max_supply": 21000000,
    },
    "description": {"en": "Bitcoin is a cryptocurrency."},
    "links": {"homepage": ["https://bitcoin.org"]},
}
MARKET_RANKINGS = [
    {"id": "bitcoin", "symbol": "btc", "name": "Bitcoin", "current_price": 97500,
     "market_cap": 1900000000000, "market_cap_rank": 1, "total_volume": 35000000000,
     "price_change_percentage_24h": 1.5},
    {"id": "ethereum", "symbol": "eth", "name": "Ethereum", "current_price": 3200,
     "market_cap": 380000000000, "market_cap_rank": 2, "total_volume": 15000000000,
     "price_change_percentage_24h": 2.1},
]
PRICE_HISTORY = {"prices": [[1740000000000, 95000], [1740086400000, 96000], [1740172800000, 97500]]}
GLOBAL_DATA = {
    "data": {
        "total_market_cap": {"usd": 3500000000000},
        "total_volume": {"usd": 150000000000},
        "market_cap_change_percentage_24h_usd": 1.5,
        "market_cap_percentage": {"btc": 52.3, "eth": 17.1},
        "active_cryptocurrencies": 15000,
        "markets": 900,
    }
}
FEAR_GREED = {"data": [{"value": "65", "value_classification": "Greed", "timestamp": "1740000000"}]}
DOMINANCE = {
    "data": {
        "market_cap_percentage": {"btc": 52.3, "eth": 17.1, "usdt": 4.5}
    }
}
CATEGORIES = [
    {"id": "layer-1", "name": "Layer 1 (L1)", "market_cap": 2500000000000, "market_cap_change_24h": 1.5},
    {"id": "defi", "name": "Decentralized Finance (DeFi)", "market_cap": 90000000000, "market_cap_change_24h": -0.5},
]
TRENDING = {"coins": [{"item": {"id": "bitcoin", "symbol": "BTC", "name": "Bitcoin", "market_cap_rank": 1}}]}


def _patch_get(json_data, status_code=200):
    return patch("crypto_ultra_simple.requests.get", return_value=_mock_response(json_data, status_code))


def _patch_get_error():
    """Patch requests.get to raise an exception."""
    return patch("crypto_ultra_simple.requests.get", side_effect=Exception("Network error"))


# ---------------------------------------------------------------------------
# Tests — get_bitcoin_price
# ---------------------------------------------------------------------------

class TestGetBitcoinPrice:
    def test_success(self):
        with _patch_get(PRICE_RESPONSE):
            from crypto_ultra_simple import get_bitcoin_price
            result = call_tool(get_bitcoin_price, )
        assert result["status"] == "success"
        assert result["bitcoin_price_usd"] == 97500

    def test_api_error(self):
        with _patch_get_error():
            from crypto_ultra_simple import get_bitcoin_price
            result = call_tool(get_bitcoin_price, )
        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# Tests — get_crypto_prices
# ---------------------------------------------------------------------------

class TestGetCryptoPrices:
    def test_multiple_coins(self):
        with _patch_get(PRICES_MULTI):
            from crypto_ultra_simple import get_crypto_prices
            result = call_tool(get_crypto_prices, "bitcoin,ethereum")
        assert result["status"] == "success"
        assert "bitcoin" in result["prices"]
        assert "ethereum" in result["prices"]

    def test_single_coin(self):
        with _patch_get({"bitcoin": {"usd": 97500, "usd_24h_change": 1.5, "usd_market_cap": 1900000000000, "usd_24h_vol": 35000000000}}):
            from crypto_ultra_simple import get_crypto_prices
            result = call_tool(get_crypto_prices, "bitcoin")
        assert result["status"] == "success"

    def test_api_failure(self):
        with _patch_get_error():
            from crypto_ultra_simple import get_crypto_prices
            result = call_tool(get_crypto_prices, "bitcoin")
        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# Tests — get_coin_details
# ---------------------------------------------------------------------------

class TestGetCoinDetails:
    def test_bitcoin_details(self):
        with _patch_get(COIN_DETAILS):
            from crypto_ultra_simple import get_coin_details
            result = call_tool(get_coin_details, "bitcoin")
        assert result["status"] == "success"
        assert "status" in result

    def test_invalid_coin(self):
        with _patch_get_error():
            from crypto_ultra_simple import get_coin_details
            result = call_tool(get_coin_details, "fakecoin999")
        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# Tests — get_market_rankings
# ---------------------------------------------------------------------------

class TestGetMarketRankings:
    def test_top_coins(self):
        with _patch_get(MARKET_RANKINGS):
            from crypto_ultra_simple import get_market_rankings
            result = call_tool(get_market_rankings, 10)
        assert result["status"] == "success"
        assert "rankings" in result
        assert len(result["rankings"]) == 2

    def test_limit_respected(self):
        with _patch_get(MARKET_RANKINGS):
            from crypto_ultra_simple import get_market_rankings
            result = call_tool(get_market_rankings, 2)
        assert result["status"] == "success"


# ---------------------------------------------------------------------------
# Tests — get_price_history
# ---------------------------------------------------------------------------

class TestGetPriceHistory:
    def test_success(self):
        with _patch_get(PRICE_HISTORY):
            from crypto_ultra_simple import get_price_history
            result = call_tool(get_price_history, "bitcoin", 7)
        assert result["status"] == "success"
        assert "price_history" in result

    def test_api_error(self):
        with _patch_get_error():
            from crypto_ultra_simple import get_price_history
            result = call_tool(get_price_history, "bitcoin", 7)
        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# Tests — get_market_trends
# ---------------------------------------------------------------------------

class TestGetMarketTrends:
    def test_success(self):
        with _patch_get(TRENDING):
            from crypto_ultra_simple import get_market_trends
            result = call_tool(get_market_trends, )
        assert result["status"] == "success"

    def test_api_failure(self):
        with _patch_get_error():
            from crypto_ultra_simple import get_market_trends
            result = call_tool(get_market_trends, )
        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# Tests — compare_crypto_performance
# ---------------------------------------------------------------------------

class TestCompareCryptoPerformance:
    def test_two_coins(self):
        with _patch_get(PRICES_MULTI):
            from crypto_ultra_simple import compare_crypto_performance
            result = call_tool(compare_crypto_performance, "bitcoin,ethereum")
        assert result["status"] == "success"

    def test_api_error(self):
        with _patch_get_error():
            from crypto_ultra_simple import compare_crypto_performance
            result = call_tool(compare_crypto_performance, "bitcoin,ethereum")
        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# Tests — get_global_market_stats
# ---------------------------------------------------------------------------

class TestGetGlobalMarketStats:
    def test_success(self):
        with _patch_get(GLOBAL_DATA):
            from crypto_ultra_simple import get_global_market_stats
            result = call_tool(get_global_market_stats, )
        assert result["status"] == "success"
        assert "global_market_stats" in result

    def test_api_failure(self):
        with _patch_get_error():
            from crypto_ultra_simple import get_global_market_stats
            result = call_tool(get_global_market_stats, )
        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# Tests — get_fear_greed_index
# ---------------------------------------------------------------------------

class TestGetFearGreedIndex:
    def test_success(self):
        with _patch_get(FEAR_GREED):
            from crypto_ultra_simple import get_fear_greed_index
            result = call_tool(get_fear_greed_index, )
        assert result["status"] == "success"
        assert "fear_greed_index" in result

    def test_api_failure(self):
        with _patch_get_error():
            from crypto_ultra_simple import get_fear_greed_index
            result = call_tool(get_fear_greed_index, )
        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# Tests — get_dominance_stats
# ---------------------------------------------------------------------------

class TestGetDominanceStats:
    def test_success(self):
        with _patch_get(DOMINANCE):
            from crypto_ultra_simple import get_dominance_stats
            result = call_tool(get_dominance_stats, )
        assert result["status"] == "success"

    def test_api_failure(self):
        with _patch_get_error():
            from crypto_ultra_simple import get_dominance_stats
            result = call_tool(get_dominance_stats, )
        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# Tests — get_crypto_categories
# ---------------------------------------------------------------------------

class TestGetCryptoCategories:
    def test_success(self):
        with _patch_get(CATEGORIES):
            from crypto_ultra_simple import get_crypto_categories
            result = call_tool(get_crypto_categories, )
        assert result["status"] == "success"

    def test_api_failure(self):
        with _patch_get_error():
            from crypto_ultra_simple import get_crypto_categories
            result = call_tool(get_crypto_categories, )
        assert result["status"] == "error"
