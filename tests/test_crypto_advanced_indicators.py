"""
Tests for crypto_advanced_indicators.py MCP server.
All CCXT calls are mocked.
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mcp-servers"))
from helpers import call_tool


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

def _make_ohlcv_df(n=200):
    """Generate a deterministic OHLCV DataFrame."""
    np.random.seed(42)
    base = 97000
    rets = np.random.normal(0.0002, 0.005, n)
    close = base * np.cumprod(1 + rets)
    high = close * (1 + np.abs(np.random.normal(0, 0.003, n)))
    low = close * (1 - np.abs(np.random.normal(0, 0.003, n)))
    open_ = close * (1 + np.random.normal(0, 0.001, n))
    volume = np.random.uniform(100, 5000, n)

    return pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=n, freq="1h"),
        "open": open_, "high": high, "low": low,
        "close": close, "volume": volume,
    })


MOCK_DF = _make_ohlcv_df()


def _patch_fetch():
    """Patch _fetch_ohlcv to return a DataFrame (no network calls)."""
    return patch("crypto_advanced_indicators._fetch_ohlcv", return_value=MOCK_DF.copy())


def _patch_fetch_error():
    """Patch _fetch_ohlcv to raise an exception."""
    return patch("crypto_advanced_indicators._fetch_ohlcv", side_effect=Exception("Connection refused"))


# ---------------------------------------------------------------------------
# Tests — calculate_obv
# ---------------------------------------------------------------------------

class TestCalculateOBV:
    def test_success(self):
        with _patch_fetch():
            from crypto_advanced_indicators import calculate_obv
            result = call_tool(calculate_obv, "BTC", "1h", 100)
        assert result["success"] is True
        assert "current_obv" in result
        assert "obv_trend" in result

    def test_trend_values(self):
        with _patch_fetch():
            from crypto_advanced_indicators import calculate_obv
            result = call_tool(calculate_obv, "BTC")
        assert result["obv_trend"] in ("RISING", "FALLING", "FLAT")

    def test_signal_values(self):
        with _patch_fetch():
            from crypto_advanced_indicators import calculate_obv
            result = call_tool(calculate_obv, "BTC")
        assert result.get("divergence", "NEUTRAL") in (
            "BULLISH", "BEARISH", "BULLISH_DIVERGENCE", "BEARISH_DIVERGENCE", "NEUTRAL"
        )


# ---------------------------------------------------------------------------
# Tests — calculate_mfi
# ---------------------------------------------------------------------------

class TestCalculateMFI:
    def test_success(self):
        with _patch_fetch():
            from crypto_advanced_indicators import calculate_mfi
            result = call_tool(calculate_mfi, "BTC", "1h")
        assert result["success"] is True
        assert "current_mfi" in result
        assert 0 <= result["current_mfi"] <= 100

    def test_signal_values(self):
        with _patch_fetch():
            from crypto_advanced_indicators import calculate_mfi
            result = call_tool(calculate_mfi, "BTC")
        assert result["signal"] in ("OVERBOUGHT", "OVERSOLD", "BULLISH", "BEARISH", "NEUTRAL")


# ---------------------------------------------------------------------------
# Tests — calculate_adx
# ---------------------------------------------------------------------------

class TestCalculateADX:
    def test_success(self):
        with _patch_fetch():
            from crypto_advanced_indicators import calculate_adx
            result = call_tool(calculate_adx, "BTC", "1h")
        assert result["success"] is True
        assert "current_adx" in result

    def test_trend_strength(self):
        with _patch_fetch():
            from crypto_advanced_indicators import calculate_adx
            result = call_tool(calculate_adx, "BTC")
        assert result["trend_strength"] in (
            "STRONG_TREND", "MODERATE_TREND", "WEAK_TREND", "NO_TREND"
        )

    def test_direction(self):
        with _patch_fetch():
            from crypto_advanced_indicators import calculate_adx
            result = call_tool(calculate_adx, "BTC")
        assert result["trend_direction"] in ("BULLISH", "BEARISH")


# ---------------------------------------------------------------------------
# Tests — calculate_ichimoku
# ---------------------------------------------------------------------------

class TestCalculateIchimoku:
    def test_success(self):
        with _patch_fetch():
            from crypto_advanced_indicators import calculate_ichimoku
            result = call_tool(calculate_ichimoku, "BTC", "1h", 100)
        assert result["success"] is True
        assert "tenkan_sen" in result
        assert "kijun_sen" in result

    def test_cloud_signal(self):
        with _patch_fetch():
            from crypto_advanced_indicators import calculate_ichimoku
            result = call_tool(calculate_ichimoku, "BTC")
        assert result["cloud_color"] in (
            "GREEN", "RED", "NEUTRAL",
            "STRONG_BULLISH", "BULLISH", "BULLISH_CLOUD",
            "BEARISH", "STRONG_BEARISH", "BEARISH_CLOUD"
        )


# ---------------------------------------------------------------------------
# Tests — calculate_vwap
# ---------------------------------------------------------------------------

class TestCalculateVWAP:
    def test_success(self):
        with _patch_fetch():
            from crypto_advanced_indicators import calculate_vwap
            result = call_tool(calculate_vwap, "BTC", "1h", 100)
        assert result["success"] is True
        assert "vwap" in result

    def test_position_signal(self):
        with _patch_fetch():
            from crypto_advanced_indicators import calculate_vwap
            result = call_tool(calculate_vwap, "BTC")
        assert result["signal"] in ("BULLISH", "BEARISH")


# ---------------------------------------------------------------------------
# Tests — calculate_pivot_points
# ---------------------------------------------------------------------------

class TestCalculatePivotPoints:
    def test_success(self):
        with _patch_fetch():
            from crypto_advanced_indicators import calculate_pivot_points
            result = call_tool(calculate_pivot_points, "BTC", "1d")
        assert result["success"] is True
        assert "pivot" in result
        assert "resistances" in result
        assert "supports" in result

    def test_levels_order(self):
        with _patch_fetch():
            from crypto_advanced_indicators import calculate_pivot_points
            result = call_tool(calculate_pivot_points, "BTC")
        # Resistances above pivot, supports below
        assert result["resistances"]["R1"] > result["pivot"]
        assert result["pivot"] > result["supports"]["S1"]


# ---------------------------------------------------------------------------
# Tests — calculate_williams_r
# ---------------------------------------------------------------------------

class TestCalculateWilliamsR:
    def test_success(self):
        with _patch_fetch():
            from crypto_advanced_indicators import calculate_williams_r
            result = call_tool(calculate_williams_r, "BTC", "1h")
        assert result["success"] is True
        assert "current_williams_r" in result
        assert -100 <= result["current_williams_r"] <= 0

    def test_signal_values(self):
        with _patch_fetch():
            from crypto_advanced_indicators import calculate_williams_r
            result = call_tool(calculate_williams_r, "BTC")
        assert result["signal"] in ("OVERBOUGHT", "OVERSOLD", "BULLISH", "BEARISH", "NEUTRAL")


# ---------------------------------------------------------------------------
# Tests — detect_divergences
# ---------------------------------------------------------------------------

class TestDetectDivergences:
    def test_success(self):
        with _patch_fetch():
            from crypto_advanced_indicators import detect_divergences
            result = call_tool(detect_divergences, "BTC", "1h", 100)
        assert result["success"] is True
        assert "divergences" in result

    def test_divergence_types(self):
        with _patch_fetch():
            from crypto_advanced_indicators import detect_divergences
            result = call_tool(detect_divergences, "BTC")
        for div in result.get("divergences", []):
            assert div["type"] in ("BULLISH_DIVERGENCE", "BEARISH_DIVERGENCE", "BULLISH", "BEARISH")


# ---------------------------------------------------------------------------
# Tests — error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    def test_exchange_error_obv(self):
        with _patch_fetch_error():
            from crypto_advanced_indicators import calculate_obv
            result = call_tool(calculate_obv, "BTC", "1h", 100)
        assert result["success"] is False

    def test_exchange_error_mfi(self):
        with _patch_fetch_error():
            from crypto_advanced_indicators import calculate_mfi
            result = call_tool(calculate_mfi, "BTC", "1h", 100)
        assert result["success"] is False
