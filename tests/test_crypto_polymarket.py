"""
Tests for crypto_polymarket.py (crypto-polymarket) MCP server.

All HTTP calls to the Gamma API are mocked.
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mcp-servers"))
from helpers import call_tool


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

def _mock_resp(json_data, status=200):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock(return_value=None)
    return resp


def _market(
    *,
    id="123",
    slug="will-btc-hit-100k-2026",
    question="Will BTC hit $100k by end of 2026?",
    outcomes=("Yes", "No"),
    prices=("0.62", "0.38"),
    volume=1_500_000.0,
    liquidity=120_000.0,
    active=True,
    closed=False,
    category="Crypto",
):
    return {
        "id": id,
        "slug": slug,
        "question": question,
        "outcomes": json.dumps(list(outcomes)),
        "outcomePrices": json.dumps(list(prices)),
        "volumeNum": volume,
        "liquidityNum": liquidity,
        "active": active,
        "closed": closed,
        "acceptingOrders": active and not closed,
        "category": category,
        "startDate": "2026-01-01T00:00:00Z",
        "endDate": "2026-12-31T23:59:59Z",
        "description": "Resolves YES if BTC trades at or above $100,000 on any major exchange by 2026-12-31.",
        "resolutionSource": "Coinbase, Binance, Kraken",
    }


# ---------------------------------------------------------------------------
# search_markets
# ---------------------------------------------------------------------------

class TestSearchMarkets:
    def test_success(self):
        resp = _mock_resp([_market(), _market(id="124", slug="fed-cut-sept", question="Will Fed cut in Sep?")])
        with patch("crypto_polymarket.requests.get", return_value=resp):
            from crypto_polymarket import search_markets
            result = call_tool(search_markets, "BTC", limit=10)
        assert result["success"] is True
        assert result["count"] == 2
        assert result["markets"][0]["question"] == "Will BTC hit $100k by end of 2026?"
        assert result["markets"][0]["outcomes"][0]["probability"] == pytest.approx(0.62)

    def test_empty_query_rejected(self):
        from crypto_polymarket import search_markets
        result = call_tool(search_markets, "", limit=10)
        assert result["success"] is False
        assert "non-empty" in result["error"]

    def test_invalid_limit_rejected(self):
        from crypto_polymarket import search_markets
        result = call_tool(search_markets, "BTC", limit=0)
        assert result["success"] is False

    def test_limit_capped(self):
        # Caller passes 999 — we should not blow up and should cap to 100
        resp = _mock_resp([_market()])
        with patch("crypto_polymarket.requests.get", return_value=resp) as mock_get:
            from crypto_polymarket import search_markets
            call_tool(search_markets, "BTC", limit=999)
        called_params = mock_get.call_args.kwargs["params"]
        assert called_params["limit"] == 100

    def test_active_only_flag_propagates(self):
        resp = _mock_resp([_market()])
        with patch("crypto_polymarket.requests.get", return_value=resp) as mock_get:
            from crypto_polymarket import search_markets
            call_tool(search_markets, "BTC", limit=5, active_only=True)
        called_params = mock_get.call_args.kwargs["params"]
        assert called_params.get("active") == "true"
        assert called_params.get("closed") == "false"

    def test_http_error_handled(self):
        with patch("crypto_polymarket.requests.get", side_effect=Exception("network down")):
            from crypto_polymarket import search_markets
            result = call_tool(search_markets, "BTC", limit=5)
        assert result["success"] is False
        assert "network down" in result["error"]


# ---------------------------------------------------------------------------
# get_market_probabilities
# ---------------------------------------------------------------------------

class TestGetMarketProbabilities:
    def test_success_by_slug(self):
        resp = _mock_resp([_market()])
        with patch("crypto_polymarket.requests.get", return_value=resp) as mock_get:
            from crypto_polymarket import get_market_probabilities
            result = call_tool(get_market_probabilities, "will-btc-hit-100k-2026")
        assert result["success"] is True
        assert result["outcomes"][0]["probability_pct"] == 62.0
        # Querying by slug should pass slug param, not id
        assert mock_get.call_args.kwargs["params"].get("slug") == "will-btc-hit-100k-2026"

    def test_success_by_numeric_id(self):
        resp = _mock_resp([_market()])
        with patch("crypto_polymarket.requests.get", return_value=resp) as mock_get:
            from crypto_polymarket import get_market_probabilities
            result = call_tool(get_market_probabilities, "123")
        assert result["success"] is True
        assert mock_get.call_args.kwargs["params"].get("id") == "123"

    def test_not_found(self):
        resp = _mock_resp([])
        with patch("crypto_polymarket.requests.get", return_value=resp):
            from crypto_polymarket import get_market_probabilities
            result = call_tool(get_market_probabilities, "nonexistent")
        assert result["success"] is False
        assert result["error_type"] == "NotFound"

    def test_consensus_high_confidence(self):
        # Yes at 0.85 — leader probability above HIGH_CONFIDENCE threshold (0.75)
        resp = _mock_resp([_market(prices=("0.85", "0.15"))])
        with patch("crypto_polymarket.requests.get", return_value=resp):
            from crypto_polymarket import get_market_probabilities
            result = call_tool(get_market_probabilities, "x")
        assert result["consensus"]["state"] == "HIGH_CONFIDENCE"
        assert result["consensus"]["leader"] == "Yes"

    def test_consensus_uncertain(self):
        resp = _mock_resp([_market(prices=("0.55", "0.45"))])
        with patch("crypto_polymarket.requests.get", return_value=resp):
            from crypto_polymarket import get_market_probabilities
            result = call_tool(get_market_probabilities, "x")
        assert result["consensus"]["state"] == "UNCERTAIN"

    def test_consensus_low_confidence(self):
        # Both outcomes below LOW_CONFIDENCE (0.25) is impossible with 2 outcomes
        # summing to ~1.0, but the leader at 0.20 is possible with many outcomes
        resp = _mock_resp([_market(
            outcomes=("A", "B", "C", "D", "E"),
            prices=("0.20", "0.20", "0.20", "0.20", "0.20"),
        )])
        with patch("crypto_polymarket.requests.get", return_value=resp):
            from crypto_polymarket import get_market_probabilities
            result = call_tool(get_market_probabilities, "x")
        # 5-way tie at 0.20 — leader 0.20 <= 0.25 -> LOW_CONFIDENCE
        assert result["consensus"]["state"] == "LOW_CONFIDENCE"


# ---------------------------------------------------------------------------
# get_trending_markets
# ---------------------------------------------------------------------------

class TestGetTrendingMarkets:
    def test_success(self):
        resp = _mock_resp([_market(), _market(id="124", slug="x", question="Q2")])
        with patch("crypto_polymarket.requests.get", return_value=resp):
            from crypto_polymarket import get_trending_markets
            result = call_tool(get_trending_markets, limit=5)
        assert result["success"] is True
        assert result["count"] == 2

    def test_category_filter_propagates(self):
        resp = _mock_resp([_market()])
        with patch("crypto_polymarket.requests.get", return_value=resp) as mock_get:
            from crypto_polymarket import get_trending_markets
            call_tool(get_trending_markets, limit=5, category="Sports")
        called_params = mock_get.call_args.kwargs["params"]
        assert called_params.get("category") == "Sports"

    def test_ordered_by_volume24hr(self):
        resp = _mock_resp([_market()])
        with patch("crypto_polymarket.requests.get", return_value=resp) as mock_get:
            from crypto_polymarket import get_trending_markets
            call_tool(get_trending_markets, limit=5)
        called_params = mock_get.call_args.kwargs["params"]
        assert called_params.get("order") == "volume24hr"
        assert called_params.get("ascending") == "false"


# ---------------------------------------------------------------------------
# get_crypto_markets
# ---------------------------------------------------------------------------

class TestGetCryptoMarkets:
    def test_success_with_crypto_category(self):
        resp = _mock_resp([_market(category="Crypto"), _market(id="124", slug="x", category="Bitcoin")])
        with patch("crypto_polymarket.requests.get", return_value=resp):
            from crypto_polymarket import get_crypto_markets
            result = call_tool(get_crypto_markets, limit=10)
        assert result["success"] is True
        assert result["count"] == 2

    def test_fallback_when_no_crypto_category(self):
        # API returns markets with non-crypto categories — fallback returns all
        resp = _mock_resp([_market(category="Politics"), _market(id="124", slug="x", category="Sports")])
        with patch("crypto_polymarket.requests.get", return_value=resp):
            from crypto_polymarket import get_crypto_markets
            result = call_tool(get_crypto_markets, limit=10)
        assert result["success"] is True
        assert result["count"] == 2  # fallback kicked in


# ---------------------------------------------------------------------------
# get_market_detail
# ---------------------------------------------------------------------------

class TestGetMarketDetail:
    def test_success(self):
        resp = _mock_resp([_market()])
        with patch("crypto_polymarket.requests.get", return_value=resp):
            from crypto_polymarket import get_market_detail
            result = call_tool(get_market_detail, "will-btc-hit-100k-2026")
        assert result["success"] is True
        assert result["description"].startswith("Resolves YES")
        assert result["resolution_source"] == "Coinbase, Binance, Kraken"

    def test_not_found(self):
        resp = _mock_resp([])
        with patch("crypto_polymarket.requests.get", return_value=resp):
            from crypto_polymarket import get_market_detail
            result = call_tool(get_market_detail, "missing")
        assert result["success"] is False

    def test_empty_slug(self):
        from crypto_polymarket import get_market_detail
        result = call_tool(get_market_detail, "")
        assert result["success"] is False


# ---------------------------------------------------------------------------
# get_top_volume_markets
# ---------------------------------------------------------------------------

class TestGetTopVolumeMarkets:
    def test_success(self):
        resp = _mock_resp([_market(), _market(id="124", slug="x", question="Q2")])
        with patch("crypto_polymarket.requests.get", return_value=resp):
            from crypto_polymarket import get_top_volume_markets
            result = call_tool(get_top_volume_markets, limit=10)
        assert result["success"] is True
        assert result["count"] == 2

    def test_ordered_by_total_volume(self):
        resp = _mock_resp([_market()])
        with patch("crypto_polymarket.requests.get", return_value=resp) as mock_get:
            from crypto_polymarket import get_top_volume_markets
            call_tool(get_top_volume_markets, limit=5)
        called_params = mock_get.call_args.kwargs["params"]
        assert called_params.get("order") == "volume"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

class TestOutcomeParsing:
    def test_handles_string_outcomes(self):
        from crypto_polymarket import _parse_outcomes
        m = {"outcomes": '["Yes", "No"]', "outcomePrices": '["0.7", "0.3"]'}
        result = _parse_outcomes(m)
        assert result[0]["probability"] == pytest.approx(0.7)
        assert result[1]["probability"] == pytest.approx(0.3)

    def test_handles_list_outcomes(self):
        from crypto_polymarket import _parse_outcomes
        m = {"outcomes": ["A", "B"], "outcomePrices": ["0.5", "0.5"]}
        result = _parse_outcomes(m)
        assert len(result) == 2

    def test_missing_prices_handled(self):
        from crypto_polymarket import _parse_outcomes
        m = {"outcomes": ["Yes", "No"], "outcomePrices": None}
        result = _parse_outcomes(m)
        assert result[0]["probability"] is None

    def test_malformed_json_handled(self):
        from crypto_polymarket import _parse_outcomes
        m = {"outcomes": "[not valid json]", "outcomePrices": '["0.5"]'}
        result = _parse_outcomes(m)
        assert result == []


class TestConsensusClassification:
    def test_no_outcomes(self):
        from crypto_polymarket import _classify_consensus
        assert _classify_consensus([])["state"] == "UNKNOWN"

    def test_no_prices(self):
        from crypto_polymarket import _classify_consensus
        result = _classify_consensus([{"outcome": "Y", "probability": None}])
        assert result["state"] == "NO_PRICES"

    def test_picks_highest_probability(self):
        from crypto_polymarket import _classify_consensus
        result = _classify_consensus([
            {"outcome": "A", "probability": 0.3},
            {"outcome": "B", "probability": 0.65},
            {"outcome": "C", "probability": 0.05},
        ])
        assert result["leader"] == "B"
        assert result["leader_probability"] == 0.65
