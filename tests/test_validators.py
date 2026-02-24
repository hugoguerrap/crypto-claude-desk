"""
Tests for validators.py shared validation module.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mcp-servers"))

from validators import (
    validate_symbol,
    validate_coin_id,
    validate_exchange,
    validate_positive_int,
    validate_timeframe,
    SUPPORTED_EXCHANGES,
    VALID_TIMEFRAMES,
)


# ---------------------------------------------------------------------------
# validate_symbol
# ---------------------------------------------------------------------------

class TestValidateSymbol:
    def test_valid_uppercase(self):
        assert validate_symbol("BTC") == "BTC"

    def test_valid_lowercase_normalizes(self):
        assert validate_symbol("eth") == "ETH"

    def test_valid_mixed_case(self):
        assert validate_symbol("Sol") == "SOL"

    def test_strips_whitespace(self):
        assert validate_symbol("  BTC  ") == "BTC"

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            validate_symbol("")

    def test_none_raises(self):
        with pytest.raises(ValueError):
            validate_symbol(None)

    def test_numeric_raises(self):
        with pytest.raises(ValueError):
            validate_symbol("123")

    def test_special_chars_raises(self):
        with pytest.raises(ValueError):
            validate_symbol("BTC/USDT")

    def test_too_long_raises(self):
        with pytest.raises(ValueError):
            validate_symbol("A" * 11)

    def test_max_length_ok(self):
        assert validate_symbol("A" * 10) == "A" * 10


# ---------------------------------------------------------------------------
# validate_coin_id
# ---------------------------------------------------------------------------

class TestValidateCoinId:
    def test_valid_bitcoin(self):
        assert validate_coin_id("bitcoin") == "bitcoin"

    def test_valid_with_hyphens(self):
        assert validate_coin_id("matic-network") == "matic-network"

    def test_uppercase_normalizes(self):
        assert validate_coin_id("Bitcoin") == "bitcoin"

    def test_strips_whitespace(self):
        assert validate_coin_id("  bitcoin  ") == "bitcoin"

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            validate_coin_id("")

    def test_none_raises(self):
        with pytest.raises(ValueError):
            validate_coin_id(None)

    def test_special_chars_raises(self):
        with pytest.raises(ValueError):
            validate_coin_id("bit@coin")


# ---------------------------------------------------------------------------
# validate_exchange
# ---------------------------------------------------------------------------

class TestValidateExchange:
    def test_valid_binance(self):
        assert validate_exchange("binance") == "binance"

    def test_uppercase_normalizes(self):
        assert validate_exchange("BINANCE") == "binance"

    def test_strips_whitespace(self):
        assert validate_exchange("  kraken  ") == "kraken"

    def test_unsupported_raises(self):
        with pytest.raises(ValueError, match="Unsupported"):
            validate_exchange("fakexchange")

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            validate_exchange("")

    def test_custom_supported_set(self):
        assert validate_exchange("myex", supported={"myex", "other"}) == "myex"

    def test_custom_set_rejects_unknown(self):
        with pytest.raises(ValueError):
            validate_exchange("binance", supported={"myex"})

    def test_all_default_exchanges_valid(self):
        for ex in SUPPORTED_EXCHANGES:
            assert validate_exchange(ex) == ex


# ---------------------------------------------------------------------------
# validate_positive_int
# ---------------------------------------------------------------------------

class TestValidatePositiveInt:
    def test_valid(self):
        assert validate_positive_int(10, "test") == 10

    def test_zero_raises(self):
        with pytest.raises(ValueError):
            validate_positive_int(0, "test")

    def test_negative_raises(self):
        with pytest.raises(ValueError):
            validate_positive_int(-5, "test")

    def test_max_value_ok(self):
        assert validate_positive_int(100, "test", max_value=100) == 100

    def test_exceeds_max_raises(self):
        with pytest.raises(ValueError):
            validate_positive_int(101, "test", max_value=100)

    def test_float_raises(self):
        with pytest.raises(ValueError):
            validate_positive_int(3.5, "test")

    def test_string_raises(self):
        with pytest.raises(ValueError):
            validate_positive_int("10", "test")


# ---------------------------------------------------------------------------
# validate_timeframe
# ---------------------------------------------------------------------------

class TestValidateTimeframe:
    def test_valid_1h(self):
        assert validate_timeframe("1h") == "1h"

    def test_valid_1d(self):
        assert validate_timeframe("1d") == "1d"

    def test_strips_whitespace(self):
        assert validate_timeframe("  4h  ") == "4h"

    def test_invalid_raises(self):
        with pytest.raises(ValueError, match="Invalid timeframe"):
            validate_timeframe("2d")

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            validate_timeframe("")

    def test_none_raises(self):
        with pytest.raises(ValueError):
            validate_timeframe(None)

    def test_all_valid_timeframes(self):
        for tf in VALID_TIMEFRAMES:
            assert validate_timeframe(tf) == tf
