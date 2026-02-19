"""
Integration test for anchor token info feature in reports.
Tests that anchor data is properly retrieved and formatted for templates.
"""
import pytest
from unittest.mock import patch
import pandas as pd

from services.anchor_token_info import AnchorTokenInfo


@pytest.fixture
def mock_anchor_service():
    """Create a mock anchor service with sample data."""
    service = AnchorTokenInfo()
    return service


@pytest.mark.asyncio
async def test_anchor_data_formatting_for_template(mock_anchor_service):
    """Test that anchor data is properly formatted for template rendering."""
    mock_gecko_pools = [
        {
            "protocol": "uniswap_v3",
            "chain": "ethereum",
            "symbol": "WETH / USDC 0.05%",
            "pool_address": "0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640",
            "volume": 1500000.0,
            "fees": 750.0,
            "liquidity": 1000000.0,
            "dex": "uniswap_v3",
        },
        {
            "protocol": "curve",
            "chain": "ethereum",
            "symbol": "DAI / USDC / USDT",
            "pool_address": "0xbebc44782c7db0a1a60cb6fe97d0b483032ff1c7",
            "volume": 500000.0,
            "fees": None,
            "liquidity": 500000.0,
            "dex": "curve",
        },
    ]

    with patch(
        "services.anchor_token_info.fetch_pools_for_token_gecko_only",
        return_value=mock_gecko_pools,
    ):
        result_df = await mock_anchor_service.get_token_data(
            "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",  # USDC
            blockchain="ethereum",
        )

    assert not result_df.empty
    assert len(result_df) > 0

    anchor_data = {
        "token_address": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
        "token_symbol": mock_anchor_service._resolve_token_symbol(
            "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
        ),
        "stats": mock_anchor_service.get_summary_stats(result_df),
        "top_market": result_df.iloc[0].to_dict() if len(result_df) > 0 else None,
    }

    assert "token_symbol" in anchor_data
    assert anchor_data["token_symbol"] == "USDC"

    assert "stats" in anchor_data
    assert "total_markets" in anchor_data["stats"]
    assert "timestamp" in anchor_data["stats"]

    assert "top_market" in anchor_data
    assert anchor_data["top_market"] is not None

    top_market = anchor_data["top_market"]
    assert "volume" in top_market or "pool_address" in top_market

    print("✅ Anchor data structure is valid for template rendering")


@pytest.mark.asyncio
async def test_token_symbol_resolution():
    """Test that common token addresses are resolved correctly."""
    service = AnchorTokenInfo()
    
    test_cases = [
        ("0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48", "USDC"),
        ("0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2", "WETH"),
        ("0x7f39c581f595b53c5cb19bd0b3f8da6c935e2ca0", "wstETH"),
        ("0x6b175474e89094c44da98b954eedeac495271d0f", "DAI"),
        ("0x0000000000000000000000000000000000000000", "TOKEN"),  # Unknown
    ]
    
    for address, expected_symbol in test_cases:
        result = service._resolve_token_symbol(address)
        assert result == expected_symbol, f"Expected {expected_symbol} for {address}, got {result}"
    
    print("✅ Token symbol resolution working correctly")


@pytest.mark.asyncio
async def test_anchor_data_with_empty_results():
    """Test that empty results are handled gracefully."""
    service = AnchorTokenInfo()

    with patch(
        "services.anchor_token_info.fetch_pools_for_token_gecko_only",
        return_value=[],
    ):
        result_df = await service.get_token_data(
            "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
            blockchain="ethereum",
        )

    assert result_df.empty

    stats = service.get_summary_stats(result_df)
    assert stats == {"status": "No data available"}

    print("✅ Empty results handled gracefully")


if __name__ == "__main__":
    # Run with: PYTHONPATH=. python -m pytest tests/test_anchor_integration.py -v
    print("Run with: PYTHONPATH=. pytest tests/test_anchor_integration.py -v")
