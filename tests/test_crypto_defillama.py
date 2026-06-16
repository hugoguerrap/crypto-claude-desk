"""
Tests for crypto_defillama.py (crypto-defillama) MCP server.

All HTTP calls to the DefiLlama and stablecoins APIs are mocked.
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

def _mock_resp(json_data, status=200):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock(return_value=None)
    return resp


CHAINS_SAMPLE = [
    {"name": "Ethereum", "tvl": 60_000_000_000, "tokenSymbol": "ETH"},
    {"name": "Solana", "tvl": 8_000_000_000, "tokenSymbol": "SOL"},
    {"name": "Tron", "tvl": 6_000_000_000, "tokenSymbol": "TRX"},
    {"name": "BSC", "tvl": 5_000_000_000, "tokenSymbol": "BNB"},
    {"name": "Arbitrum", "tvl": 4_000_000_000, "tokenSymbol": "ETH"},
]


PROTOCOLS_SAMPLE = [
    {"name": "Aave", "slug": "aave", "category": "Lending", "tvl": 15_000_000_000, "change_1d": 1.2, "change_7d": 4.5, "chains": ["Ethereum", "Polygon"], "mcap": 5_000_000_000},
    {"name": "Uniswap", "slug": "uniswap", "category": "Dexes", "tvl": 6_000_000_000, "change_1d": -0.3, "change_7d": 2.1, "chains": ["Ethereum", "Optimism"], "mcap": 8_000_000_000},
    {"name": "Lido", "slug": "lido", "category": "Liquid Staking", "tvl": 25_000_000_000, "change_1d": 0.5, "change_7d": 1.0, "chains": ["Ethereum"], "mcap": 2_000_000_000},
]


# ---------------------------------------------------------------------------
# get_total_tvl
# ---------------------------------------------------------------------------

class TestGetTotalTvl:
    def test_success(self):
        with patch("crypto_defillama.requests.get", return_value=_mock_resp(CHAINS_SAMPLE)):
            from crypto_defillama import get_total_tvl
            result = call_tool(get_total_tvl)
        assert result["success"] is True
        assert result["total_tvl_usd"] == 83_000_000_000
        assert result["total_chains"] == 5
        assert result["top_10_chains"][0]["name"] == "Ethereum"
        assert result["top_10_chains"][0]["share_pct"] == pytest.approx(72.29, rel=1e-2)

    def test_unexpected_shape_errors(self):
        with patch("crypto_defillama.requests.get", return_value=_mock_resp({"oops": "not a list"})):
            from crypto_defillama import get_total_tvl
            result = call_tool(get_total_tvl)
        assert result["success"] is False

    def test_http_error_handled(self):
        with patch("crypto_defillama.requests.get", side_effect=Exception("503")):
            from crypto_defillama import get_total_tvl
            result = call_tool(get_total_tvl)
        assert result["success"] is False


# ---------------------------------------------------------------------------
# get_chain_tvl
# ---------------------------------------------------------------------------

class TestGetChainTvl:
    def test_success_canonical(self):
        with patch("crypto_defillama.requests.get", return_value=_mock_resp(CHAINS_SAMPLE)):
            from crypto_defillama import get_chain_tvl
            result = call_tool(get_chain_tvl, "Ethereum")
        assert result["success"] is True
        assert result["chain"] == "Ethereum"
        assert result["rank"] == 1
        assert result["tvl_usd"] == 60_000_000_000

    def test_alias_normalization(self):
        with patch("crypto_defillama.requests.get", return_value=_mock_resp(CHAINS_SAMPLE)):
            from crypto_defillama import get_chain_tvl
            result = call_tool(get_chain_tvl, "eth")
        assert result["success"] is True
        assert result["chain"] == "Ethereum"

    def test_alias_solana(self):
        with patch("crypto_defillama.requests.get", return_value=_mock_resp(CHAINS_SAMPLE)):
            from crypto_defillama import get_chain_tvl
            result = call_tool(get_chain_tvl, "sol")
        assert result["chain"] == "Solana"

    def test_not_found(self):
        with patch("crypto_defillama.requests.get", return_value=_mock_resp(CHAINS_SAMPLE)):
            from crypto_defillama import get_chain_tvl
            result = call_tool(get_chain_tvl, "FakeChainXYZ")
        assert result["success"] is False
        assert result["error_type"] == "NotFound"

    def test_empty_chain_rejected(self):
        from crypto_defillama import get_chain_tvl
        result = call_tool(get_chain_tvl, "")
        assert result["success"] is False


# ---------------------------------------------------------------------------
# get_protocol_tvl
# ---------------------------------------------------------------------------

class TestGetProtocolTvl:
    def test_success(self):
        protocol_data = {
            "name": "Aave",
            "slug": "aave",
            "category": "Lending",
            "chains": ["Ethereum", "Polygon"],
            "currentChainTvls": {"Ethereum": 12_000_000_000, "Polygon": 3_000_000_000},
            "change_1d": 1.2,
            "change_7d": 4.5,
            "url": "https://aave.com",
            "twitter": "aave",
        }
        with patch("crypto_defillama.requests.get", return_value=_mock_resp(protocol_data)):
            from crypto_defillama import get_protocol_tvl
            result = call_tool(get_protocol_tvl, "aave")
        assert result["success"] is True
        assert result["protocol"] == "Aave"
        assert result["total_tvl_usd"] == 15_000_000_000
        assert result["per_chain_tvl"][0]["chain"] == "Ethereum"

    def test_not_found(self):
        with patch("crypto_defillama.requests.get", return_value=_mock_resp({"error": "not found"})):
            from crypto_defillama import get_protocol_tvl
            result = call_tool(get_protocol_tvl, "nonexistent")
        assert result["success"] is False

    def test_empty_protocol_rejected(self):
        from crypto_defillama import get_protocol_tvl
        result = call_tool(get_protocol_tvl, "")
        assert result["success"] is False


# ---------------------------------------------------------------------------
# get_top_protocols
# ---------------------------------------------------------------------------

class TestGetTopProtocols:
    def test_success(self):
        with patch("crypto_defillama.requests.get", return_value=_mock_resp(PROTOCOLS_SAMPLE)):
            from crypto_defillama import get_top_protocols
            result = call_tool(get_top_protocols, limit=10)
        assert result["success"] is True
        assert result["count"] == 3
        # Lido (25b) > Aave (15b) > Uniswap (6b)
        assert result["protocols"][0]["name"] == "Lido"

    def test_category_filter(self):
        with patch("crypto_defillama.requests.get", return_value=_mock_resp(PROTOCOLS_SAMPLE)):
            from crypto_defillama import get_top_protocols
            result = call_tool(get_top_protocols, limit=10, category="Lending")
        assert result["count"] == 1
        assert result["protocols"][0]["name"] == "Aave"

    def test_limit_capped(self):
        with patch("crypto_defillama.requests.get", return_value=_mock_resp(PROTOCOLS_SAMPLE)):
            from crypto_defillama import get_top_protocols
            result = call_tool(get_top_protocols, limit=9999)
        # Limit caps at 200 but we only have 3 protocols
        assert result["count"] == 3

    def test_invalid_limit_rejected(self):
        from crypto_defillama import get_top_protocols
        result = call_tool(get_top_protocols, limit=-5)
        assert result["success"] is False


# ---------------------------------------------------------------------------
# get_stablecoins_overview
# ---------------------------------------------------------------------------

class TestGetStablecoinsOverview:
    def test_success(self):
        sample = {
            "peggedAssets": [
                {"name": "Tether", "symbol": "USDT", "circulating": {"peggedUSD": 120_000_000_000}, "chains": ["Ethereum", "Tron"], "price": 1.0},
                {"name": "USD Coin", "symbol": "USDC", "circulating": {"peggedUSD": 35_000_000_000}, "chains": ["Ethereum"], "price": 1.0},
                {"name": "Dai", "symbol": "DAI", "circulating": {"peggedUSD": 5_000_000_000}, "chains": ["Ethereum"], "price": 1.0},
            ]
        }
        with patch("crypto_defillama.requests.get", return_value=_mock_resp(sample)):
            from crypto_defillama import get_stablecoins_overview
            result = call_tool(get_stablecoins_overview)
        assert result["success"] is True
        assert result["total_mcap_usd"] == 160_000_000_000
        assert result["top_10"][0]["symbol"] == "USDT"
        assert result["top_10"][0]["share_pct"] == 75.0

    def test_empty_response(self):
        with patch("crypto_defillama.requests.get", return_value=_mock_resp({"peggedAssets": []})):
            from crypto_defillama import get_stablecoins_overview
            result = call_tool(get_stablecoins_overview)
        assert result["success"] is True
        assert result["total_mcap_usd"] == 0


# ---------------------------------------------------------------------------
# get_dex_volume_24h
# ---------------------------------------------------------------------------

class TestGetDexVolume24h:
    def test_success_global(self):
        sample = {
            "total24h": 5_000_000_000,
            "total7d": 38_000_000_000,
            "change_1d": 2.5,
            "protocols": [
                {"name": "Uniswap", "total24h": 2_000_000_000, "total7d": 14_000_000_000, "change_1d": 1.0, "chains": ["Ethereum"]},
                {"name": "PancakeSwap", "total24h": 1_200_000_000, "total7d": 9_000_000_000, "change_1d": -0.5, "chains": ["BSC"]},
            ],
        }
        with patch("crypto_defillama.requests.get", return_value=_mock_resp(sample)) as mock_get:
            from crypto_defillama import get_dex_volume_24h
            result = call_tool(get_dex_volume_24h)
        assert result["success"] is True
        assert result["chain"] == "all_chains"
        assert result["total_volume_24h_usd"] == 5_000_000_000
        assert result["top_dexes"][0]["name"] == "Uniswap"

    def test_chain_specific_url(self):
        sample = {"total24h": 1, "total7d": 1, "change_1d": 0, "protocols": []}
        with patch("crypto_defillama.requests.get", return_value=_mock_resp(sample)) as mock_get:
            from crypto_defillama import get_dex_volume_24h
            call_tool(get_dex_volume_24h, "Ethereum")
        # Called URL should include the chain name
        called_url = mock_get.call_args.args[0]
        assert "Ethereum" in called_url

    def test_chain_alias_normalized(self):
        sample = {"total24h": 1, "total7d": 1, "change_1d": 0, "protocols": []}
        with patch("crypto_defillama.requests.get", return_value=_mock_resp(sample)) as mock_get:
            from crypto_defillama import get_dex_volume_24h
            call_tool(get_dex_volume_24h, "eth")
        called_url = mock_get.call_args.args[0]
        assert "Ethereum" in called_url


# ---------------------------------------------------------------------------
# get_chain_tvl_change
# ---------------------------------------------------------------------------

class TestGetChainTvlChange:
    def test_success_inflow(self):
        # 10 days of history, last value 10% above baseline
        history = [{"date": 1_000_000 + i * 86400, "tvl": 100 + i} for i in range(10)]
        with patch("crypto_defillama.requests.get", return_value=_mock_resp(history)):
            from crypto_defillama import get_chain_tvl_change
            result = call_tool(get_chain_tvl_change, "Ethereum", days=7)
        assert result["success"] is True
        assert result["change_pct"] > 0
        assert result["flow_classification"] in ("INFLOW", "STRONG_INFLOW", "FLAT")

    def test_outflow_classification(self):
        # Strong outflow: baseline 100, latest 50 = -50% change
        history = [
            {"date": 1_000_000, "tvl": 100},
            {"date": 1_000_000 + 86400, "tvl": 95},
            {"date": 1_000_000 + 172800, "tvl": 50},
        ]
        with patch("crypto_defillama.requests.get", return_value=_mock_resp(history)):
            from crypto_defillama import get_chain_tvl_change
            result = call_tool(get_chain_tvl_change, "Ethereum", days=2)
        assert result["change_pct"] == -50
        assert result["flow_classification"] == "STRONG_OUTFLOW"

    def test_invalid_days_rejected(self):
        from crypto_defillama import get_chain_tvl_change
        result = call_tool(get_chain_tvl_change, "Ethereum", days=0)
        assert result["success"] is False

    def test_days_too_large_rejected(self):
        from crypto_defillama import get_chain_tvl_change
        result = call_tool(get_chain_tvl_change, "Ethereum", days=999)
        assert result["success"] is False

    def test_empty_history(self):
        with patch("crypto_defillama.requests.get", return_value=_mock_resp([])):
            from crypto_defillama import get_chain_tvl_change
            result = call_tool(get_chain_tvl_change, "Ethereum", days=7)
        assert result["success"] is False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

class TestNormalizeChain:
    def test_known_aliases(self):
        from crypto_defillama import _normalize_chain
        assert _normalize_chain("eth") == "Ethereum"
        assert _normalize_chain("sol") == "Solana"
        assert _normalize_chain("bnb") == "BSC"
        assert _normalize_chain("matic") == "Polygon"

    def test_unknown_passthrough_titlecased(self):
        from crypto_defillama import _normalize_chain
        assert _normalize_chain("fantom") == "Fantom"

    def test_already_canonical(self):
        from crypto_defillama import _normalize_chain
        assert _normalize_chain("Ethereum") == "Ethereum"


class TestClassifyChange:
    def test_none(self):
        from crypto_defillama import _classify_change
        assert _classify_change(None) == "UNKNOWN"

    def test_strong_inflow(self):
        from crypto_defillama import _classify_change
        assert _classify_change(15) == "STRONG_INFLOW"

    def test_inflow(self):
        from crypto_defillama import _classify_change
        assert _classify_change(5) == "INFLOW"

    def test_flat(self):
        from crypto_defillama import _classify_change
        assert _classify_change(0.5) == "FLAT"
        assert _classify_change(-1) == "FLAT"

    def test_outflow(self):
        from crypto_defillama import _classify_change
        assert _classify_change(-5) == "OUTFLOW"

    def test_strong_outflow(self):
        from crypto_defillama import _classify_change
        assert _classify_change(-20) == "STRONG_OUTFLOW"
