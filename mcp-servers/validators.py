"""
Shared input validation for all MCP servers.
Provides consistent validation and error messages across tools.
"""

import re
import logging

logger = logging.getLogger(__name__)

# Supported exchanges across the system
SUPPORTED_EXCHANGES = {
    "binance", "kraken", "bitfinex", "kucoin", "mexc",
    "bybit", "okx", "bitget"
}

# Valid symbol pattern: 1-10 uppercase letters
_SYMBOL_RE = re.compile(r"^[A-Za-z]{1,10}$")

# Valid CoinGecko coin ID pattern
_COIN_ID_RE = re.compile(r"^[a-z0-9\-]{1,100}$")

# Valid timeframes
VALID_TIMEFRAMES = {
    "1m", "3m", "5m", "15m", "30m",
    "1h", "2h", "4h", "6h", "8h", "12h",
    "1d", "3d", "1w", "1M"
}


def validate_symbol(symbol: str) -> str:
    """
    Validate and normalize a cryptocurrency symbol.

    Args:
        symbol: Raw symbol input (e.g. "BTC", "btc", "ETH")

    Returns:
        Uppercased symbol string

    Raises:
        ValueError: If symbol is empty or contains invalid characters
    """
    if not symbol or not isinstance(symbol, str):
        raise ValueError("Symbol must be a non-empty string")

    symbol = symbol.strip().upper()

    if not _SYMBOL_RE.match(symbol):
        raise ValueError(
            f"Invalid symbol '{symbol}': must be 1-10 letters (e.g. BTC, ETH)"
        )

    return symbol


def validate_coin_id(coin_id: str) -> str:
    """
    Validate a CoinGecko coin ID.

    Args:
        coin_id: CoinGecko identifier (e.g. "bitcoin", "ethereum")

    Returns:
        Lowercased coin ID

    Raises:
        ValueError: If coin_id is empty or invalid
    """
    if not coin_id or not isinstance(coin_id, str):
        raise ValueError("Coin ID must be a non-empty string")

    coin_id = coin_id.strip().lower()

    if not _COIN_ID_RE.match(coin_id):
        raise ValueError(
            f"Invalid coin ID '{coin_id}': must be lowercase alphanumeric with hyphens"
        )

    return coin_id


def validate_exchange(exchange: str, supported: set = None) -> str:
    """
    Validate an exchange name.

    Args:
        exchange: Exchange name (e.g. "binance", "kraken")
        supported: Optional set of supported exchanges (defaults to SUPPORTED_EXCHANGES)

    Returns:
        Lowercased exchange name

    Raises:
        ValueError: If exchange is not supported
    """
    if not exchange or not isinstance(exchange, str):
        raise ValueError("Exchange must be a non-empty string")

    exchange = exchange.strip().lower()
    allowed = supported or SUPPORTED_EXCHANGES

    if exchange not in allowed:
        raise ValueError(
            f"Unsupported exchange '{exchange}'. Supported: {sorted(allowed)}"
        )

    return exchange


def validate_positive_int(value: int, name: str, max_value: int = None) -> int:
    """
    Validate that a value is a positive integer.

    Args:
        value: The value to validate
        name: Parameter name for error messages
        max_value: Optional upper bound

    Returns:
        The validated integer

    Raises:
        ValueError: If value is not a positive integer or exceeds max_value
    """
    if not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer, got {value}")

    if max_value is not None and value > max_value:
        raise ValueError(f"{name} must be <= {max_value}, got {value}")

    return value


def validate_timeframe(timeframe: str) -> str:
    """
    Validate a candlestick timeframe.

    Args:
        timeframe: Timeframe string (e.g. "1h", "4h", "1d")

    Returns:
        Validated timeframe string

    Raises:
        ValueError: If timeframe is not valid
    """
    if not timeframe or not isinstance(timeframe, str):
        raise ValueError("Timeframe must be a non-empty string")

    timeframe = timeframe.strip()

    if timeframe not in VALID_TIMEFRAMES:
        raise ValueError(
            f"Invalid timeframe '{timeframe}'. Valid: {sorted(VALID_TIMEFRAMES)}"
        )

    return timeframe
