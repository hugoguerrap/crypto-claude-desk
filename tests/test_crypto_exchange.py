"""
Tests for crypto_exchange_ccxt_ultra.py (crypto-exchange) MCP server.
All CCXT calls are mocked.
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mcp-servers"))
from helpers import call_tool


# ---------------------------------------------------------------------------
# Mock exchange factory
# ---------------------------------------------------------------------------

def _make_mock_exchange():
    ex = MagicMock()
    ex.fetch_ticker.return_value = {
        "last": 97500.0, "bid": 97490.0, "ask": 97510.0,
        "baseVolume": 1234.5, "quoteVolume": 120000000.0,
        "percentage": 1.2, "timestamp": 1740000000000,
        "high": 98000.0, "low": 96500.0, "open": 96800.0,
        "close": 97500.0, "vwap": 97200.0,
    }
    bids = [[97490 - i * 10, 0.5 + i * 0.1] for i in range(50)]
    asks = [[97510 + i * 10, 0.5 + i * 0.1] for i in range(50)]
    ex.fetch_order_book.return_value = {
        "bids": bids, "asks": asks, "timestamp": 1740000000000,
    }
    ex.fetch_ohlcv.return_value = [
        [1740000000000 + i * 3600000, 97000 + i * 10, 97100 + i * 10,
         96900 + i * 10, 97050 + i * 10, 500 + i * 10]
        for i in range(100)
    ]
    ex.fetch_trades.return_value = [
        {"id": str(i), "timestamp": 1740000000000 + i * 1000,
         "price": 97500.0 + (i % 5), "amount": 0.1 * (i + 1),
         "side": "buy" if i % 2 == 0 else "sell",
         "cost": (97500.0 + i % 5) * 0.1 * (i + 1)}
        for i in range(50)
    ]
    ex.load_markets.return_value = {
        "BTC/USDT": {"active": True, "base": "BTC", "quote": "USDT", "type": "spot"},
        "ETH/USDT": {"active": True, "base": "ETH", "quote": "USDT", "type": "spot"},
    }
    ex.fetch_tickers.return_value = {
        "BTC/USDT": {"last": 97500, "baseVolume": 1234, "quoteVolume": 120000000, "percentage": 1.2, "symbol": "BTC/USDT"},
        "ETH/USDT": {"last": 3200, "baseVolume": 5000, "quoteVolume": 16000000, "percentage": 2.1, "symbol": "ETH/USDT"},
    }
    ex.has = {"fetchOHLCV": True, "fetchTrades": True, "fetchOrderBook": True, "fetchTicker": True, "fetchTickers": True}
    ex.timeframes = {"1m": "1m", "5m": "5m", "1h": "1h", "1d": "1d"}
    ex.rateLimit = 1200
    ex.fees = {"trading": {"maker": 0.001, "taker": 0.001}}
    ex.version = "v3"
    return ex


MOCK_EXCHANGES = {
    "binance": _make_mock_exchange(),
    "kraken": _make_mock_exchange(),
    "bitfinex": _make_mock_exchange(),
    "kucoin": _make_mock_exchange(),
    "mexc": _make_mock_exchange(),
}


def _patch_exchanges():
    return patch("crypto_exchange_ccxt_ultra.EXCHANGES", MOCK_EXCHANGES)





# ---------------------------------------------------------------------------
# Tests — get_exchange_prices
# ---------------------------------------------------------------------------

class TestGetExchangePrices:
    def test_success(self):
        with _patch_exchanges():
            from crypto_exchange_ccxt_ultra import get_exchange_prices
            result = call_tool(get_exchange_prices, "BTC")
        assert result["status"] == "success"
        assert "exchanges" in result

    def test_multiple_exchanges(self):
        with _patch_exchanges():
            from crypto_exchange_ccxt_ultra import get_exchange_prices
            result = call_tool(get_exchange_prices, "BTC", ["binance", "kraken"])
        assert result["status"] == "success"

    def test_error_handling(self):
        bad_ex = _make_mock_exchange()
        bad_ex.fetch_ticker.side_effect = Exception("Connection refused")
        with patch("crypto_exchange_ccxt_ultra.EXCHANGES", {"binance": bad_ex}):
            from crypto_exchange_ccxt_ultra import get_exchange_prices
            result = call_tool(get_exchange_prices, "BTC", ["binance"])
        # Should handle gracefully
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# Tests — get_arbitrage_opportunities
# ---------------------------------------------------------------------------

class TestGetArbitrageOpportunities:
    def test_success(self):
        # Create exchanges with different prices for arbitrage
        exchanges = {}
        for i, name in enumerate(["binance", "kraken", "bitfinex", "kucoin", "mexc"]):
            ex = _make_mock_exchange()
            ex.fetch_ticker.return_value = {
                "last": 97500.0 + i * 100, "bid": 97490.0 + i * 100,
                "ask": 97510.0 + i * 100, "baseVolume": 1234.5,
                "quoteVolume": 120000000, "percentage": 1.2,
                "timestamp": 1740000000000,
                "high": 98000, "low": 96500, "open": 96800, "close": 97500 + i * 100,
            }
            exchanges[name] = ex

        with patch("crypto_exchange_ccxt_ultra.EXCHANGES", exchanges):
            from crypto_exchange_ccxt_ultra import get_arbitrage_opportunities
            result = call_tool(get_arbitrage_opportunities, "BTC")
        assert result["status"] == "success"


# ---------------------------------------------------------------------------
# Tests — get_orderbook_data
# ---------------------------------------------------------------------------

class TestGetOrderbookData:
    def test_success(self):
        with _patch_exchanges():
            from crypto_exchange_ccxt_ultra import get_orderbook_data
            result = call_tool(get_orderbook_data, "BTC", "binance")
        assert result["status"] == "success"
        assert "orderbook" in result or "status" in result

    def test_default_limit(self):
        with _patch_exchanges():
            from crypto_exchange_ccxt_ultra import get_orderbook_data
            result = call_tool(get_orderbook_data, "BTC", "binance", 20)
        assert result["status"] == "success"


# ---------------------------------------------------------------------------
# Tests — get_exchange_volume
# ---------------------------------------------------------------------------

class TestGetExchangeVolume:
    def test_success(self):
        with _patch_exchanges():
            from crypto_exchange_ccxt_ultra import get_exchange_volume
            result = call_tool(get_exchange_volume, "BTC")
        assert result["status"] == "success"

    def test_specific_exchanges(self):
        with _patch_exchanges():
            from crypto_exchange_ccxt_ultra import get_exchange_volume
            result = call_tool(get_exchange_volume, "BTC", ["binance"])
        assert result["status"] == "success"


# ---------------------------------------------------------------------------
# Tests — get_trading_pairs
# ---------------------------------------------------------------------------

class TestGetTradingPairs:
    def test_success(self):
        with _patch_exchanges():
            from crypto_exchange_ccxt_ultra import get_trading_pairs
            result = call_tool(get_trading_pairs, "binance")
        assert result["status"] == "success"

    def test_unsupported_exchange(self):
        with _patch_exchanges():
            from crypto_exchange_ccxt_ultra import get_trading_pairs
            result = call_tool(get_trading_pairs, "fakexchange")
        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# Tests — compare_exchange_prices
# ---------------------------------------------------------------------------

class TestCompareExchangePrices:
    def test_success(self):
        with _patch_exchanges():
            from crypto_exchange_ccxt_ultra import compare_exchange_prices
            result = call_tool(compare_exchange_prices, "BTC")
        assert result["status"] == "success"


# ---------------------------------------------------------------------------
# Tests — get_exchange_status
# ---------------------------------------------------------------------------

class TestGetExchangeStatus:
    def test_success(self):
        with _patch_exchanges():
            from crypto_exchange_ccxt_ultra import get_exchange_status
            result = call_tool(get_exchange_status, )
        assert result["status"] == "success"
        assert "exchange_status" in result


# ---------------------------------------------------------------------------
# Tests — fetch_ohlcv_data
# ---------------------------------------------------------------------------

class TestFetchOHLCVData:
    def test_success(self):
        with _patch_exchanges():
            from crypto_exchange_ccxt_ultra import fetch_ohlcv_data
            result = call_tool(fetch_ohlcv_data, "1h", "binance", "BTC")
        assert result["status"] == "success"
        assert "candles" in result

    def test_default_params(self):
        with _patch_exchanges():
            from crypto_exchange_ccxt_ultra import fetch_ohlcv_data
            result = call_tool(fetch_ohlcv_data, )
        assert result["status"] == "success"


# ---------------------------------------------------------------------------
# Tests — fetch_multiple_timeframes
# ---------------------------------------------------------------------------

class TestFetchMultipleTimeframes:
    def test_success(self):
        with _patch_exchanges():
            from crypto_exchange_ccxt_ultra import fetch_multiple_timeframes
            result = call_tool(fetch_multiple_timeframes, "binance", "BTC")
        assert result["status"] == "success"

    def test_custom_timeframes(self):
        with _patch_exchanges():
            from crypto_exchange_ccxt_ultra import fetch_multiple_timeframes
            result = call_tool(fetch_multiple_timeframes, "binance", "BTC", ["1h", "1d"])
        assert result["status"] == "success"


# ---------------------------------------------------------------------------
# Tests — fetch_recent_trades
# ---------------------------------------------------------------------------

class TestFetchRecentTrades:
    def test_success(self):
        with _patch_exchanges():
            from crypto_exchange_ccxt_ultra import fetch_recent_trades
            result = call_tool(fetch_recent_trades, "binance", "BTC")
        assert result["status"] == "success"

    def test_custom_limit(self):
        with _patch_exchanges():
            from crypto_exchange_ccxt_ultra import fetch_recent_trades
            result = call_tool(fetch_recent_trades, "binance", "BTC", 10)
        assert result["status"] == "success"


# ---------------------------------------------------------------------------
# Tests — get_exchange_markets_info
# ---------------------------------------------------------------------------

class TestGetExchangeMarketsInfo:
    def test_success(self):
        with _patch_exchanges():
            from crypto_exchange_ccxt_ultra import get_exchange_markets_info
            result = call_tool(get_exchange_markets_info, "binance")
        assert result["status"] == "success"


# ---------------------------------------------------------------------------
# Tests — get_all_tickers
# ---------------------------------------------------------------------------

class TestGetAllTickers:
    def test_success(self):
        with _patch_exchanges():
            from crypto_exchange_ccxt_ultra import get_all_tickers
            result = call_tool(get_all_tickers, "binance")
        assert result["status"] == "success"

    def test_quote_filter(self):
        with _patch_exchanges():
            from crypto_exchange_ccxt_ultra import get_all_tickers
            result = call_tool(get_all_tickers, "binance", "USDT")
        assert result["status"] == "success"


# ---------------------------------------------------------------------------
# Tests — analyze_volume_patterns
# ---------------------------------------------------------------------------

class TestAnalyzeVolumePatterns:
    def test_success(self):
        with _patch_exchanges():
            from crypto_exchange_ccxt_ultra import analyze_volume_patterns
            result = call_tool(analyze_volume_patterns, "binance", "BTC")
        assert result["status"] == "success"


# ---------------------------------------------------------------------------
# Tests — get_cross_exchange_liquidity
# ---------------------------------------------------------------------------

class TestGetCrossExchangeLiquidity:
    def test_success(self):
        with _patch_exchanges():
            from crypto_exchange_ccxt_ultra import get_cross_exchange_liquidity
            result = call_tool(get_cross_exchange_liquidity, "BTC")
        assert result["status"] == "success"

    def test_specific_exchanges(self):
        with _patch_exchanges():
            from crypto_exchange_ccxt_ultra import get_cross_exchange_liquidity
            result = call_tool(get_cross_exchange_liquidity, "BTC", ["binance", "kraken"])
        assert result["status"] == "success"


# ---------------------------------------------------------------------------
# Tests — get_market_depth_analysis
# ---------------------------------------------------------------------------

class TestGetMarketDepthAnalysis:
    def test_success(self):
        with _patch_exchanges():
            from crypto_exchange_ccxt_ultra import get_market_depth_analysis
            result = call_tool(get_market_depth_analysis, "binance", "BTC")
        assert result["status"] == "success"
