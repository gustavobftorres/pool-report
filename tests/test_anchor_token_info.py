"""
Tests for the AnchorTokenInfo service.
Mocks GeckoTerminal API calls (GeckoTerminal-only flow).
"""
import pytest
import pandas as pd
from unittest.mock import patch

from services.anchor_token_info import AnchorTokenInfo

# Sample Mock Data
MOCK_TOKEN_ADDRESS = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
MOCK_BLOCKCHAIN = "ethereum"

MOCK_GECKO_POOLS = [
    {
        "protocol": "uniswap_v3",
        "chain": "ethereum",
        "symbol": "WETH / USDC 0.05%",
        "pool_address": "0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640",
        "volume": 236905677.62,
        "fees": 118452.84,
        "liquidity": 84946090.35,
        "dex": "uniswap_v3",
        "tvl_usd": 84946090.35,
        "fdv_usd": 51767550019.92,
        "market_cap_usd": 73902394902.78,
    },
    {
        "protocol": "curve",
        "chain": "ethereum",
        "symbol": "DAI / USDC / USDT",
        "pool_address": "0xbebc44782c7db0a1a60cb6fe97d0b483032ff1c7",
        "volume": 3909393.14,
        "fees": None,
        "liquidity": 162024857.49,
        "dex": "curve",
        "tvl_usd": 162024857.49,
        "fdv_usd": 51504569749.97,
        "market_cap_usd": 73526969143.72,
    },
]


@pytest.fixture
def anchor_service():
    """Fixture to initialize the service."""
    return AnchorTokenInfo()


@pytest.mark.asyncio
async def test_get_token_data_success(anchor_service):
    """Test fetching pools from GeckoTerminal."""
    with patch(
        "services.anchor_token_info.fetch_pools_for_token_gecko_only",
        return_value=MOCK_GECKO_POOLS,
    ):
        df = await anchor_service.get_token_data(MOCK_TOKEN_ADDRESS, MOCK_BLOCKCHAIN)

    assert not df.empty
    assert len(df) == 2
    assert "protocol" in df.columns
    assert "pool_address" in df.columns
    assert "volume" in df.columns
    assert "fees" in df.columns
    assert "liquidity" in df.columns
    assert "dex" in df.columns
    assert "fdv_usd" in df.columns
    assert "market_cap_usd" in df.columns
    assert df.iloc[0]["protocol"] == "uniswap_v3"
    assert df.iloc[0]["pool_address"] == "0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640"
    assert df.iloc[0]["volume"] == 236905677.62
    # All pools have pool_address - no empty rows
    assert df["pool_address"].notna().all()


@pytest.mark.asyncio
async def test_get_token_data_empty(anchor_service):
    """Test when no pools are found."""
    with patch(
        "services.anchor_token_info.fetch_pools_for_token_gecko_only",
        return_value=[],
    ):
        df = await anchor_service.get_token_data(MOCK_TOKEN_ADDRESS, MOCK_BLOCKCHAIN)

    assert df.empty


@pytest.mark.asyncio
async def test_get_token_data_integration(anchor_service):
    """Test the main orchestrator with GeckoTerminal data."""
    with patch(
        "services.anchor_token_info.fetch_pools_for_token_gecko_only",
        return_value=[
            {"protocol": "uniswap_v3", "pool_address": "0xabc", "volume": 1000, "fees": 5}
        ],
    ):
        df = await anchor_service.get_token_data(MOCK_TOKEN_ADDRESS, MOCK_BLOCKCHAIN)

    assert not df.empty
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 1
    assert "protocol" in df.columns
    assert "pool_address" in df.columns
    assert df.iloc[0]["protocol"] == "uniswap_v3"
    assert df.iloc[0]["pool_address"] == "0xabc"
    assert df.iloc[0]["volume"] == 1000


@pytest.mark.asyncio
async def test_get_token_data_debug_exports_to_spreadsheet(anchor_service):
    """Test that setting debug=True exports to Google Spreadsheet."""
    with patch(
        "services.anchor_token_info.fetch_pools_for_token_gecko_only",
        return_value=[{"protocol": "curve", "pool_address": "0x123", "volume": 500}],
    ), patch("services.spreadsheet_service.export_dataframe_to_sheet") as mock_export:
        df = await anchor_service.get_token_data(
            MOCK_TOKEN_ADDRESS, MOCK_BLOCKCHAIN, debug=True
        )

    mock_export.assert_called_once()
    call_args = mock_export.call_args
    assert call_args[0][0] is df
    assert not df.empty
    assert df.iloc[0]["protocol"] == "curve"


def test_get_summary_stats(anchor_service):
    """Test summary statistics generation."""
    data = {
        "volume": [100.0, 200.0, 300.0],
        "fdv_usd": [1e9, 2e9, 3e9],
    }
    df = pd.DataFrame(data)

    stats = anchor_service.get_summary_stats(df)

    assert stats["total_markets"] == 3
    assert stats["cumulative_volume"] == 600.0


def test_get_summary_stats_with_total_volume_usd(anchor_service):
    """Test summary stats fallback to total_volume_usd column."""
    data = {"total_volume_usd": [100.0, 200.0]}
    df = pd.DataFrame(data)

    stats = anchor_service.get_summary_stats(df)

    assert stats["cumulative_volume"] == 300.0
