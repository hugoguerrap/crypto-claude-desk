"""
Shared fixtures and mocks for all MCP server tests.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

# Add mcp-servers to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mcp-servers"))


def call_tool(tool_obj, *args, **kwargs):
    """Call a FastMCP @mcp.tool() decorated function.

    FastMCP wraps functions in FunctionTool objects.  The raw callable
    lives at ``tool_obj.fn``.  This helper transparently unwraps it so
    tests can call ``call_tool(module.some_tool, ...)`` regardless of
    whether the object is a plain function or a FunctionTool.
    """
    fn = getattr(tool_obj, "fn", tool_obj)
    return fn(*args, **kwargs)


# ---------------------------------------------------------------------------
# OHLCV data fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_ohlcv_df():
    """Return a realistic 100-row OHLCV DataFrame for BTC/USDT."""
    np.random.seed(42)
    n = 100
    timestamps = pd.date_range("2026-01-01", periods=n, freq="1h")
    base_price = 97000.0
    # Random walk
    returns = np.random.normal(0.0002, 0.005, n)
    close = base_price * np.cumprod(1 + returns)
    high = close * (1 + np.abs(np.random.normal(0, 0.003, n)))
    low = close * (1 - np.abs(np.random.normal(0, 0.003, n)))
    open_ = close * (1 + np.random.normal(0, 0.001, n))
    volume = np.random.uniform(100, 5000, n)

    df = pd.DataFrame({
        "timestamp": timestamps,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    })
    return df


@pytest.fixture
def sample_ohlcv_raw(sample_ohlcv_df):
    """Return raw OHLCV list-of-lists as CCXT returns."""
    rows = []
    for _, r in sample_ohlcv_df.iterrows():
        rows.append([
            int(r["timestamp"].timestamp() * 1000),
            r["open"], r["high"], r["low"], r["close"], r["volume"],
        ])
    return rows


# ---------------------------------------------------------------------------
# Mock CCXT exchange
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_exchange(sample_ohlcv_raw):
    """Return a MagicMock that behaves like a ccxt exchange instance."""
    ex = MagicMock()
    ex.fetch_ohlcv.return_value = sample_ohlcv_raw

    # Ticker
    ex.fetch_ticker.return_value = {
        "last": 97500.0,
        "bid": 97490.0,
        "ask": 97510.0,
        "baseVolume": 1234.5,
        "percentage": 1.2,
        "timestamp": 1740000000000,
    }

    # Orderbook
    bids = [[97490 - i * 10, 0.5 + i * 0.1] for i in range(50)]
    asks = [[97510 + i * 10, 0.5 + i * 0.1] for i in range(50)]
    ex.fetch_order_book.return_value = {
        "bids": bids,
        "asks": asks,
        "timestamp": 1740000000000,
    }

    # Trades
    ex.fetch_trades.return_value = [
        {"id": str(i), "timestamp": 1740000000000 + i * 1000,
         "price": 97500.0 + (i % 5), "amount": 0.1 * (i + 1),
         "side": "buy" if i % 2 == 0 else "sell",
         "cost": (97500.0 + (i % 5)) * 0.1 * (i + 1)}
        for i in range(50)
    ]

    # Markets
    ex.load_markets.return_value = {
        "BTC/USDT": {"active": True, "base": "BTC", "quote": "USDT", "type": "spot"},
        "ETH/USDT": {"active": True, "base": "ETH", "quote": "USDT", "type": "spot"},
    }
    ex.sandbox = False
    ex.rateLimit = 1200
    ex.has = {
        "fetchOHLCV": True,
        "fetchTrades": True,
        "fetchOrderBook": True,
        "fetchTicker": True,
        "fetchTickers": True,
    }
    ex.timeframes = {"1m": "1m", "1h": "1h", "1d": "1d"}
    ex.fees = {"trading": {"maker": 0.001, "taker": 0.001}, "funding": {}}
    ex.version = "v3"
    return ex


# ---------------------------------------------------------------------------
# Mock CoinGecko responses
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_coingecko_price_response():
    """Simple price response from CoinGecko."""
    return {"bitcoin": {"usd": 97500, "usd_24h_change": 1.5}}


@pytest.fixture
def mock_coingecko_global_response():
    """Global market data response."""
    return {
        "data": {
            "total_market_cap": {"usd": 3_500_000_000_000},
            "total_volume": {"usd": 150_000_000_000},
            "market_cap_change_percentage_24h_usd": 1.5,
            "market_cap_percentage": {"btc": 52.3, "eth": 17.1},
            "active_cryptocurrencies": 15000,
            "markets": 900,
            "upcoming_icos": 0,
            "ongoing_icos": 0,
            "ended_icos": 3000,
        }
    }


# ---------------------------------------------------------------------------
# Funding rate fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_funding_rate():
    """Mock funding rate response from CCXT."""
    return {
        "fundingRate": 0.0001,
        "fundingTimestamp": 1740000000000,
        "timestamp": 1740000000000,
    }


@pytest.fixture
def mock_funding_rate_history():
    """Mock funding rate history from CCXT."""
    return [
        {"fundingRate": 0.0001 + i * 0.00001, "timestamp": 1740000000000 + i * 28800000}
        for i in range(20)
    ]


@pytest.fixture
def mock_open_interest():
    """Mock open interest response."""
    return {
        "openInterestAmount": 5_000_000_000,
        "openInterestValue": 50000,
        "timestamp": 1740000000000,
    }
