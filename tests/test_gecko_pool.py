"""
Tests for the gecko_pool service (pool address lookup by protocol).
"""
import pytest
from unittest.mock import patch

from services.gecko_pool import (
    BIG_DEXES,
    CHAIN_TO_NETWORK,
    DEX_PROTOCOL_MAPPING,
    LENDING_PROTOCOLS,
    fetch_pools,
    get_pool_address_for_big_dex,
    get_pool_address_for_protocol,
    is_resolvable_protocol,
)


def test_chain_to_network():
    """Test chain to network mapping."""
    assert CHAIN_TO_NETWORK.get("ethereum") == "eth"
    assert CHAIN_TO_NETWORK.get("arbitrum") == "arbitrum"
    assert CHAIN_TO_NETWORK.get("base") == "base"
    assert CHAIN_TO_NETWORK.get("unknown") is None


def test_fetch_pools_invalid_input():
    """Test fetch_pools returns [] for invalid inputs."""
    assert fetch_pools("", "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48") == []
    assert fetch_pools("ethereum", "") == []
    assert fetch_pools("UnknownChain", "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48") == []


def test_fetch_pools_success():
    """Test fetch_pools returns pool list."""
    mock_data = [
        {"id": "eth_0x88e6", "attributes": {"address": "0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640"}},
    ]
    with patch("httpx.get") as mock_get:
        mock_get.return_value.json.return_value = {"data": mock_data}
        mock_get.return_value.raise_for_status = lambda: None
        pools = fetch_pools("ethereum", "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48")
    assert len(pools) == 1
    assert pools[0]["attributes"]["address"] == "0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640"


def test_get_pool_address_for_protocol_matching_dex():
    """Test get_pool_address_for_protocol returns address when dex matches."""
    gecko_pools = [
        {
            "id": "eth_0xabc",
            "attributes": {"address": "0xabc1234567890123456789012345678901234567"},
            "relationships": {"dex": {"data": {"id": "uniswap_v3"}}},
        },
    ]
    addr = get_pool_address_for_protocol(gecko_pools, "uniswap-v3")
    assert addr == "0xabc1234567890123456789012345678901234567"


def test_get_pool_address_for_protocol_balancer():
    """Test get_pool_address_for_protocol for Balancer."""
    gecko_pools = [
        {
            "id": "eth_0xdef",
            "attributes": {"address": "0xdef1234567890123456789012345678901234567"},
            "relationships": {"dex": {"data": {"id": "balancer_ethereum"}}},
        },
    ]
    addr = get_pool_address_for_protocol(gecko_pools, "balancer")
    assert addr == "0xdef1234567890123456789012345678901234567"


def test_get_pool_address_for_protocol_lending_returns_big_dex():
    """Test lending protocols fall back to big DEX pool."""
    gecko_pools = [
        {"attributes": {"address": "0x123"}, "relationships": {"dex": {"data": {"id": "aave"}}}},
        {"attributes": {"address": "0xcurve"}, "relationships": {"dex": {"data": {"id": "curve-ethereum"}}}},
    ]
    assert get_pool_address_for_protocol(gecko_pools, "aave-v3") == "0xcurve"
    assert get_pool_address_for_protocol(gecko_pools, "compound-v3") == "0xcurve"


def test_get_pool_address_for_protocol_lending_no_big_dex_returns_none():
    """Test lending protocols return None when no big DEX pool exists."""
    gecko_pools = [{"attributes": {"address": "0x123"}, "relationships": {"dex": {"data": {"id": "aave"}}}}]
    assert get_pool_address_for_protocol(gecko_pools, "aave-v3") is None


def test_get_pool_address_for_big_dex():
    """Test get_pool_address_for_big_dex returns first matching big DEX pool."""
    gecko_pools = [
        {"attributes": {"address": "0xsushi"}, "relationships": {"dex": {"data": {"id": "sushiswap"}}}},
        {"attributes": {"address": "0xcurve"}, "relationships": {"dex": {"data": {"id": "curve-ethereum"}}}},
    ]
    assert get_pool_address_for_big_dex(gecko_pools) == "0xcurve"


def test_get_pool_address_for_protocol_balancer_v3():
    """Test get_pool_address_for_protocol for Balancer V3."""
    gecko_pools = [
        {
            "id": "base_0xbal3",
            "attributes": {"address": "0xbal3v3pool123456789012345678901234567"},
            "relationships": {"dex": {"data": {"id": "balancer-v3-base"}}},
        },
    ]
    addr = get_pool_address_for_protocol(gecko_pools, "balancer-v3")
    assert addr == "0xbal3v3pool123456789012345678901234567"


def test_get_pool_address_for_protocol_no_match_returns_none():
    """Test returns None when no dex match."""
    gecko_pools = [
        {
            "attributes": {"address": "0xabc"},
            "relationships": {"dex": {"data": {"id": "balancer_ethereum"}}},
        },
    ]
    assert get_pool_address_for_protocol(gecko_pools, "uniswap-v3") is None


def test_get_pool_address_for_protocol_unknown_protocol_returns_none():
    """Test unknown protocol returns None."""
    gecko_pools = [{"attributes": {"address": "0xabc"}, "relationships": {}}]
    assert get_pool_address_for_protocol(gecko_pools, "unknown-dex") is None


def test_is_resolvable_protocol():
    """Test is_resolvable_protocol for DEX and lending."""
    assert is_resolvable_protocol("uniswap-v3") is True
    assert is_resolvable_protocol("uniswap v3") is True
    assert is_resolvable_protocol("aave-v3") is True
    assert is_resolvable_protocol("Aave V3") is True
    assert is_resolvable_protocol("balancer-v3") is True
    assert is_resolvable_protocol("unknown-dex") is False
