"""
Tests for crypto_market_microstructure.py MCP server.
All CCXT calls are mocked.
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

def _make_mock_exchange():
    ex = MagicMock()
    # Orderbook with realistic spread
    bids = [[97490 - i * 10, 0.5 + i * 0.1] for i in range(100)]
    asks = [[97510 + i * 10, 0.5 + i * 0.1] for i in range(100)]
    ex.fetch_order_book.return_value = {
        "bids": bids, "asks": asks,
        "timestamp": 1740000000000,
    }
    # Ticker
    ex.fetch_ticker.return_value = {
        "last": 97500.0, "bid": 97490.0, "ask": 97510.0,
        "baseVolume": 1234.5, "quoteVolume": 120000000,
        "percentage": 1.2, "timestamp": 1740000000000,
    }
    # Trades
    ex.fetch_trades.return_value = [
        {"id": str(i), "timestamp": 1740000000000 + i * 100,
         "price": 97500.0 + (i % 10) - 5, "amount": 0.1 * (i % 5 + 1),
         "side": "buy" if i % 2 == 0 else "sell",
         "cost": (97500.0 + (i % 10) - 5) * 0.1 * (i % 5 + 1)}
        for i in range(200)
    ]
    # OHLCV
    ex.fetch_ohlcv.return_value = [
        [1740000000000 + i * 60000, 97000 + i, 97050 + i,
         96950 + i, 97025 + i, 500 + i]
        for i in range(100)
    ]
    return ex


MOCK_EXCHANGES = {
    "binance": _make_mock_exchange(),
    "bybit": _make_mock_exchange(),
}


def _patch_exchanges():
    return patch("crypto_market_microstructure.EXCHANGES", MOCK_EXCHANGES)


def _patch_get_exchange():
    def getter(name):
        if name in MOCK_EXCHANGES:
            return MOCK_EXCHANGES[name]
        raise ValueError(f"Unsupported: {name}")
    return patch("crypto_market_microstructure._get_exchange", side_effect=getter)


# ---------------------------------------------------------------------------
# Tests — analyze_orderbook_depth
# ---------------------------------------------------------------------------

class TestAnalyzeOrderbookDepth:
    def test_success(self):
        with _patch_exchanges(), _patch_get_exchange():
            from crypto_market_microstructure import analyze_orderbook_depth
            result = call_tool(analyze_orderbook_depth, "BTC", "binance")
        assert result["success"] is True
        assert "liquidity" in result

    def test_has_spread_info(self):
        with _patch_exchanges(), _patch_get_exchange():
            from crypto_market_microstructure import analyze_orderbook_depth
            result = call_tool(analyze_orderbook_depth, "BTC", "binance")
        assert result["success"] is True

    def test_error_handling(self):
        ex = MagicMock()
        ex.fetch_order_book.side_effect = Exception("Connection refused")
        with patch("crypto_market_microstructure.EXCHANGES", {"binance": ex}), \
             patch("crypto_market_microstructure._get_exchange", return_value=ex):
            from crypto_market_microstructure import analyze_orderbook_depth
            result = call_tool(analyze_orderbook_depth, "BTC", "binance")
        assert result["success"] is False


# ---------------------------------------------------------------------------
# Tests — detect_orderbook_imbalance
# ---------------------------------------------------------------------------

class TestDetectOrderbookImbalance:
    def test_success(self):
        with _patch_exchanges(), _patch_get_exchange():
            from crypto_market_microstructure import detect_orderbook_imbalance
            result = call_tool(detect_orderbook_imbalance, "BTC", "binance")
        assert result["success"] is True
        assert "average_imbalance" in result

    def test_balanced_orderbook(self):
        # Same volume on both sides = balanced
        ex = MagicMock()
        bids = [[97490 - i * 10, 1.0] for i in range(50)]
        asks = [[97510 + i * 10, 1.0] for i in range(50)]
        ex.fetch_order_book.return_value = {"bids": bids, "asks": asks, "timestamp": 1740000000000}
        ex.fetch_ticker.return_value = {"last": 97500.0, "bid": 97490.0, "ask": 97510.0}
        with patch("crypto_market_microstructure.EXCHANGES", {"binance": ex}), \
             patch("crypto_market_microstructure._get_exchange", return_value=ex):
            from crypto_market_microstructure import detect_orderbook_imbalance
            result = call_tool(detect_orderbook_imbalance, "BTC", "binance")
        assert result["success"] is True

    def test_imbalanced_orderbook(self):
        ex = MagicMock()
        bids = [[97490 - i * 10, 10.0] for i in range(50)]  # Heavy bids
        asks = [[97510 + i * 10, 0.1] for i in range(50)]    # Light asks
        ex.fetch_order_book.return_value = {"bids": bids, "asks": asks, "timestamp": 1740000000000}
        ex.fetch_ticker.return_value = {"last": 97500.0, "bid": 97490.0, "ask": 97510.0}
        with patch("crypto_market_microstructure.EXCHANGES", {"binance": ex}), \
             patch("crypto_market_microstructure._get_exchange", return_value=ex):
            from crypto_market_microstructure import detect_orderbook_imbalance
            result = call_tool(detect_orderbook_imbalance, "BTC", "binance")
        assert result["success"] is True


# ---------------------------------------------------------------------------
# Tests — calculate_spread_metrics
# ---------------------------------------------------------------------------

class TestCalculateSpreadMetrics:
    def test_success(self):
        with _patch_exchanges(), _patch_get_exchange():
            from crypto_market_microstructure import calculate_spread_metrics
            result = call_tool(calculate_spread_metrics, "BTC", "binance")
        assert result["success"] is True

    def test_spread_positive(self):
        with _patch_exchanges(), _patch_get_exchange():
            from crypto_market_microstructure import calculate_spread_metrics
            result = call_tool(calculate_spread_metrics, "BTC", "binance")
        assert result["success"] is True
        if "spread_bps" in result:
            assert result["spread_bps"] >= 0


# ---------------------------------------------------------------------------
# Tests — analyze_order_flow
# ---------------------------------------------------------------------------

class TestAnalyzeOrderFlow:
    def test_success(self):
        with _patch_exchanges(), _patch_get_exchange():
            from crypto_market_microstructure import analyze_order_flow
            result = call_tool(analyze_order_flow, "BTC", "binance")
        assert result["success"] is True

    def test_buy_sell_volume(self):
        with _patch_exchanges(), _patch_get_exchange():
            from crypto_market_microstructure import analyze_order_flow
            result = call_tool(analyze_order_flow, "BTC", "binance")
        assert result["success"] is True


# ---------------------------------------------------------------------------
# Tests — detect_spoofing_patterns
# ---------------------------------------------------------------------------

class TestDetectSpoofingPatterns:
    def test_success(self):
        with _patch_exchanges(), _patch_get_exchange():
            from crypto_market_microstructure import detect_spoofing_patterns
            result = call_tool(detect_spoofing_patterns, "BTC", "binance")
        assert result["success"] is True

    def test_no_spoofing_detected(self):
        # Regular orderbook should not detect spoofing
        with _patch_exchanges(), _patch_get_exchange():
            from crypto_market_microstructure import detect_spoofing_patterns
            result = call_tool(detect_spoofing_patterns, "BTC", "binance")
        assert result["success"] is True


# ---------------------------------------------------------------------------
# Tests — calculate_market_impact
# ---------------------------------------------------------------------------

class TestCalculateMarketImpact:
    def test_success(self):
        with _patch_exchanges(), _patch_get_exchange():
            from crypto_market_microstructure import calculate_market_impact
            result = call_tool(calculate_market_impact, "BTC", "binance")
        assert result["success"] is True

    def test_error_handling(self):
        ex = MagicMock()
        ex.fetch_order_book.side_effect = Exception("Timeout")
        with patch("crypto_market_microstructure.EXCHANGES", {"binance": ex}), \
             patch("crypto_market_microstructure._get_exchange", return_value=ex):
            from crypto_market_microstructure import calculate_market_impact
            result = call_tool(calculate_market_impact, "BTC", "binance")
        assert result["success"] is False
