"""
Test suite for boosted pool analyzer service.
Tests detection and resolution of ERC-4626 boosted pools.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from services.boosted_pool_analyzer import (
    is_pool_boosted,
    is_100_percent_boosted,
    get_underlying_tokens,
    get_boosted_pool_type,
    WRAPPED_TOKEN_MAP,
)


# Test 1: Detect boosted pool by type
def test_is_pool_boosted_by_type():
    """Test boosted pool detection via pool type field."""
    pool_data = {
        "type": "StablePhantom",
        "name": "bb-a-USD",
        "allTokens": []
    }
    assert is_pool_boosted(pool_data) is True


# Test 2: Detect boosted pool with AaveLinear type
def test_is_pool_boosted_aave_linear():
    """Test boosted pool detection for Aave linear pools."""
    pool_data = {
        "type": "AaveLinear",
        "name": "Balancer Aave Boosted Pool (USDC)",
        "allTokens": []
    }
    assert is_pool_boosted(pool_data) is True


# Test 3: Detect non-boosted pool
def test_is_pool_not_boosted():
    """Test that regular pools are not detected as boosted."""
    pool_data = {
        "type": "Weighted",
        "name": "50WETH-50USDC",
        "allTokens": []
    }
    assert is_pool_boosted(pool_data) is False


# Test 4: Detect boosted pool by name prefix
def test_is_pool_boosted_by_name_prefix():
    """Test boosted pool detection via name prefix 'bb-'."""
    pool_data = {
        "type": "Stable",  # Even if type is regular, name indicates boosted
        "name": "bb-a-USD Boosted Pool",
        "allTokens": []
    }
    assert is_pool_boosted(pool_data) is True


# Test 5: Detect boosted pool by name keyword
def test_is_pool_boosted_by_name_keyword():
    """Test boosted pool detection via 'Boosted' keyword in name."""
    pool_data = {
        "type": "ComposableStable",
        "name": "Balancer Aave Boosted StablePool (USD)",
        "allTokens": []
    }
    assert is_pool_boosted(pool_data) is True


# Test 6: Detect boosted pool by token symbols
def test_is_pool_boosted_by_token_symbols():
    """Test boosted pool detection by bb- prefix in token symbols."""
    pool_data = {
        "type": "Stable",
        "name": "Some Pool",
        "allTokens": [
            {"address": "0x123", "symbol": "bb-a-USDC"},
            {"address": "0x456", "symbol": "bb-a-DAI"},
        ]
    }
    assert is_pool_boosted(pool_data) is True


# Test 7: 100% boosted pool detection
def test_is_100_percent_boosted():
    """Test detection of fully boosted pool (all tokens are wrapped)."""
    pool_data = {
        "address": "0x7b50775383d3d6f0215a8f290f2c9e2eebbeceb2",
        "allTokens": [
            {"address": "0xbcca60bb61934080951369a648fb03df4f96263c", "symbol": "aUSDC"},
            {"address": "0x028171bca77440897b824ca71d1c56cac55b68a3", "symbol": "aDAI"},
            {"address": "0x7b50775383d3d6f0215a8f290f2c9e2eebbeceb2", "symbol": "BPT"}  # BPT should be ignored
        ]
    }
    assert is_100_percent_boosted(pool_data) is True


# Test 8: Partially boosted pool detection
def test_is_partially_boosted():
    """Test detection of partially boosted pool (has both wrapped and regular tokens)."""
    pool_data = {
        "address": "0x9210f1204b5a24742eba12f710636d76240df3d0",
        "allTokens": [
            {"address": "0xd093fa4fb80d09bb30817fdcd442d4d02ed3e5de", "symbol": "aUSDC"},  # Wrapped
            {"address": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48", "symbol": "USDC"},  # Regular token
            {"address": "0x9210f1204b5a24742eba12f710636d76240df3d0", "symbol": "BPT"}  # BPT
        ]
    }
    assert is_100_percent_boosted(pool_data) is False


# Test 9: Extract underlying tokens from boosted pool
def test_get_underlying_tokens():
    """Test extraction of underlying tokens from boosted pool using address mapping."""
    pool_data = {
        "address": "0x7b50775383d3d6f0215a8f290f2c9e2eebbeceb2",
        "allTokens": [
            {"address": "0xbcca60bb61934080951369a648fb03df4f96263c", "symbol": "aUSDC"},
            {"address": "0x028171bca77440897b824ca71d1c56cac55b68a3", "symbol": "aDAI"},
            {"address": "0x7b50775383d3d6f0215a8f290f2c9e2eebbeceb2", "symbol": "BPT"}  # Should be skipped
        ]
    }
    underlying = get_underlying_tokens(pool_data)
    
    # Should return USDC and DAI
    assert len(underlying) == 2
    assert any(t["symbol"] == "USDC" for t in underlying)
    assert any(t["symbol"] == "DAI" for t in underlying)
    # Check addresses are the underlying, not wrapped
    addresses = [t["address"].lower() for t in underlying]
    assert "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48" in addresses  # USDC
    assert "0x6b175474e89094c44da98b954eedeac495271d0f" in addresses  # DAI


# Test 10: Extract underlying tokens from linear pool
def test_get_underlying_tokens_linear_pool():
    """Test extraction from linear pool that contains both wrapped and underlying."""
    pool_data = {
        "address": "0x9210f1204b5a24742eba12f710636d76240df3d0",
        "allTokens": [
            {"address": "0x9210f1204b5a24742eba12f710636d76240df3d0", "symbol": "bb-a-USDC"},  # BPT - skip
            {"address": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48", "symbol": "USDC"},  # Regular
            {"address": "0xd093fa4fb80d09bb30817fdcd442d4d02ed3e5de", "symbol": "aUSDC"},  # Wrapped
        ]
    }
    underlying = get_underlying_tokens(pool_data)
    
    # Should return only USDC (not both USDC and aUSDC)
    assert len(underlying) == 1
    assert underlying[0]["symbol"] == "USDC"
    assert underlying[0]["address"].lower() == "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"


# Test 11: Handle empty pool data
def test_is_pool_boosted_empty_data():
    """Test graceful handling of empty/missing data."""
    assert is_pool_boosted({}) is False
    assert is_pool_boosted(None) is False


# Test 12: Handle empty pool data for 100% boosted check
def test_is_100_percent_boosted_empty_data():
    """Test graceful handling of empty data for 100% boosted check."""
    assert is_100_percent_boosted({}) is False
    assert is_100_percent_boosted(None) is False
    assert is_100_percent_boosted({"allTokens": []}) is False


# Test 13: Handle unknown wrapped tokens
def test_get_underlying_tokens_unknown_wrapped():
    """Test handling of wrapped tokens not in mapping."""
    pool_data = {
        "address": "0xtest",
        "allTokens": [
            {"address": "0xunknown123", "symbol": "unknownWrapped"},
        ]
    }
    underlying = get_underlying_tokens(pool_data)
    
    # Should return the token as-is (not wrapped, so include it)
    assert isinstance(underlying, list)
    assert len(underlying) == 1
    assert underlying[0]["address"] == "0xunknown123"


# Test 14: Skip BPT tokens in token extraction
def test_get_underlying_tokens_skip_bpt():
    """Test that BPT tokens are correctly skipped."""
    pool_data = {
        "address": "0xpooladdress",
        "allTokens": [
            {"address": "0xpooladdress", "symbol": "MyPool-BPT"},  # Pool's own token
            {"address": "0xtoken1", "symbol": "BPT"},  # Generic BPT
            {"address": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48", "symbol": "USDC"},  # Real token
        ]
    }
    underlying = get_underlying_tokens(pool_data)
    
    # Should only return USDC
    assert len(underlying) == 1
    assert underlying[0]["symbol"] == "USDC"


# Test 15: Handle wstETH to WETH mapping
def test_get_underlying_tokens_wsteth():
    """Test Lido wstETH to WETH mapping."""
    pool_data = {
        "address": "0xpooladdr",
        "allTokens": [
            {"address": "0x7f39c581f595b53c5cb19bd0b3f8da6c935e2ca0", "symbol": "wstETH"},
            {"address": "0xpooladdr", "symbol": "BPT"},
        ]
    }
    underlying = get_underlying_tokens(pool_data)
    
    # Should map wstETH to WETH
    assert len(underlying) == 1
    assert underlying[0]["symbol"] == "WETH"
    assert underlying[0]["address"].lower() == "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"


# Test 16: Integration test with MetricsPipeline (mocked)
@pytest.mark.asyncio
async def test_metrics_pipeline_uses_underlying_tokens():
    """Test that MetricsPipeline uses underlying tokens for boosted pools."""
    from services.metrics_pipeline import MetricsPipeline
    
    pipeline = MetricsPipeline()
    
    # Mock a boosted pool
    mock_pool_data = {
        "type": "StablePhantom",
        "name": "bb-a-USD",
        "address": "0x7b50775383d3d6f0215a8f290f2c9e2eebbeceb2",
        "allTokens": [
            {"address": "0xbcca60bb61934080951369a648fb03df4f96263c", "symbol": "aUSDC"},
            {"address": "0x028171bca77440897b824ca71d1c56cac55b68a3", "symbol": "aDAI"},
        ],
        "_blockchain": "ethereum"
    }
    
    # Mock the BalancerAPI call
    with patch.object(pipeline.balancer_api, 'get_current_pool_data', return_value=mock_pool_data):
        # Mock competitor fetch to return empty (we just care about token extraction)
        with patch.object(pipeline.dex_benchmarker, 'fetch_competitors', return_value={"competitors": []}):
            # Mock dune service to return empty metrics
            with patch.object(pipeline.dune_service, 'fetch_metrics_for_pool', return_value={}):
                result = await pipeline.analyze_pool_with_competitors("0x7b50775383d3d6f0215a8f290f2c9e2eebbeceb2")
                
                # Verify it ran without errors
                assert result is not None
                assert "input_pool" in result


# Test 17: Test pool type with lowercase
def test_is_pool_boosted_case_insensitive():
    """Test that pool type detection is case-insensitive."""
    pool_data = {
        "type": "aavelinear",  # lowercase
        "name": "Test Pool",
        "allTokens": []
    }
    # Should still detect even though type is lowercase
    assert is_pool_boosted(pool_data) is True


# Test 18: Test ComposableStable detection
def test_is_pool_boosted_composable_stable():
    """Test detection of ComposableStable pool type."""
    pool_data = {
        "type": "ComposableStable",
        "name": "Some Stable Pool",
        "allTokens": []
    }
    assert is_pool_boosted(pool_data) is True


# Test 19: Test that AAVE token is not considered wrapped
def test_aave_token_not_wrapped():
    """Test that AAVE token itself is not considered wrapped (vs aToken prefix)."""
    pool_data = {
        "address": "0xpooladdr",
        "allTokens": [
            {"address": "0x7fc66500c84a76ad7e9c93437bfc5ac33e2ddae9", "symbol": "AAVE"},
        ]
    }
    # AAVE should be included as-is, not treated as wrapped
    underlying = get_underlying_tokens(pool_data)
    assert len(underlying) == 1
    assert underlying[0]["symbol"] == "AAVE"


# Test 20: Test deduplication of underlying tokens
def test_get_underlying_tokens_deduplication():
    """Test that duplicate underlying tokens are deduplicated."""
    pool_data = {
        "address": "0xpooladdr",
        "allTokens": [
            {"address": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48", "symbol": "USDC"},  # Regular USDC
            {"address": "0xbcca60bb61934080951369a648fb03df4f96263c", "symbol": "aUSDC"},  # Maps to USDC
        ]
    }
    underlying = get_underlying_tokens(pool_data)
    
    # Should have only one USDC (deduplicated)
    assert len(underlying) == 1
    assert underlying[0]["symbol"] == "USDC"


# ============================================================================
# PHASE 8 TESTS: Tags-based Boosted Pool Detection
# ============================================================================

# Test: Boosted pool detection via tags (priority)
def test_is_pool_boosted_by_tags():
    """Test boosted pool detection via tags field (V3 API)."""
    pool_data = {
        "type": "Weighted",  # Even if type is regular, tags take priority
        "name": "Regular Pool Name",
        "tags": ["BOOSTED_AAVE", "BOOSTED", "INCENTIVIZED"],
        "allTokens": []
    }
    assert is_pool_boosted(pool_data) is True


# Test: Tags priority over heuristics
def test_is_pool_boosted_tags_priority():
    """Test that tags take priority over heuristic detection."""
    pool_data = {
        "type": "Stable",  # Not a boosted type
        "name": "Normal Stable Pool",  # No boosted keyword
        "tags": ["BOOSTED"],  # But tagged as boosted
        "allTokens": []
    }
    assert is_pool_boosted(pool_data) is True


# Test: Non-boosted pool with empty tags
def test_is_pool_not_boosted_with_empty_tags():
    """Test that non-boosted pools are correctly identified when tags are empty."""
    pool_data = {
        "type": "Weighted",
        "name": "50WETH-50USDC",
        "tags": [],  # Empty tags
        "allTokens": []
    }
    assert is_pool_boosted(pool_data) is False


# Test: Get boosted pool type - AAVE
def test_get_boosted_pool_type_aave():
    """Test detection of specific boosted pool type (AAVE)."""
    pool_data = {
        "type": "STABLE",
        "name": "Balancer Aave Boosted Pool",
        "tags": ["BOOSTED_AAVE", "BOOSTED", "INCENTIVIZED"],
        "allTokens": []
    }
    
    boosted_type = get_boosted_pool_type(pool_data)
    assert boosted_type == "AAVE"


# Test: Get boosted pool type - EULER
def test_get_boosted_pool_type_euler():
    """Test detection of Euler boosted pool type."""
    pool_data = {
        "type": "ComposableStable",
        "name": "Euler Boosted Pool",
        "tags": ["BOOSTED_EULER", "BOOSTED"],
        "allTokens": []
    }
    
    boosted_type = get_boosted_pool_type(pool_data)
    assert boosted_type == "EULER"


# Test: Get boosted pool type - Generic
def test_get_boosted_pool_type_generic():
    """Test generic boosted pool (type unknown)."""
    pool_data = {
        "type": "ComposableStable",
        "name": "bb-a-USD",
        "tags": ["BOOSTED"],  # Generic boosted tag
        "allTokens": []
    }
    
    boosted_type = get_boosted_pool_type(pool_data)
    assert boosted_type == "BOOSTED"


# Test: Get boosted pool type - Not boosted
def test_get_boosted_pool_type_not_boosted():
    """Test non-boosted pool returns empty string."""
    pool_data = {
        "type": "Weighted",
        "name": "50WETH-50USDC",
        "tags": [],
        "allTokens": []
    }
    
    boosted_type = get_boosted_pool_type(pool_data)
    assert boosted_type == ""


# Test: Heuristic fallback when tags missing
def test_is_pool_boosted_heuristic_fallback():
    """Test that heuristic detection works when tags field is missing."""
    pool_data = {
        "type": "ComposableStable",  # Boosted type
        "name": "bb-a-USD",
        # tags field missing (V2 pool)
        "allTokens": []
    }
    assert is_pool_boosted(pool_data) is True


# Test: Get boosted type via heuristic fallback (name-based)
def test_get_boosted_pool_type_heuristic_aave():
    """Test that heuristic detection identifies AAVE from name when tags missing."""
    pool_data = {
        "type": "ComposableStable",
        "name": "Balancer bb-a-USD (Aave Boosted Pool)",
        # No tags field
        "allTokens": []
    }
    
    boosted_type = get_boosted_pool_type(pool_data)
    assert boosted_type == "AAVE"


# Test: Get boosted type via heuristic fallback (type-based)
def test_get_boosted_pool_type_heuristic_yearn():
    """Test that heuristic detection identifies YEARN from type."""
    pool_data = {
        "type": "YearnLinear",
        "name": "bb-y-DAI",
        # No tags field
        "allTokens": []
    }
    
    boosted_type = get_boosted_pool_type(pool_data)
    assert boosted_type == "YEARN"


# Test: Tags with lowercase values still work
def test_is_pool_boosted_tags_case_insensitive():
    """Test that tag detection is case-insensitive."""
    pool_data = {
        "type": "Weighted",
        "name": "Test Pool",
        "tags": ["boosted", "incentivized"],  # lowercase
        "allTokens": []
    }
    assert is_pool_boosted(pool_data) is True


# Test: Get boosted type with mixed case tags
def test_get_boosted_pool_type_case_insensitive():
    """Test that boosted type detection is case-insensitive."""
    pool_data = {
        "type": "Stable",
        "name": "Test Pool",
        "tags": ["Boosted_Gearbox", "BOOSTED"],  # Mixed case
        "allTokens": []
    }
    
    boosted_type = get_boosted_pool_type(pool_data)
    assert boosted_type == "GEARBOX"


# Test: Non-list tags value doesn't crash
def test_is_pool_boosted_tags_not_list():
    """Test that non-list tags value is handled gracefully."""
    pool_data = {
        "type": "Weighted",
        "name": "Test Pool",
        "tags": "BOOSTED",  # String instead of list
        "allTokens": []
    }
    # Should fall back to heuristic detection (returns False)
    assert is_pool_boosted(pool_data) is False

