"""
Tests for Balancer V3 API integration.

Regression test: The V3 API schema changed - 'allTokens' was removed and replaced
with 'poolTokens'. Using 'allTokens' in the GraphQL query causes HTTP 400 Bad Request.
This test ensures the fix remains in place.
"""
import pytest
from unittest.mock import AsyncMock, patch

from services.balancer_api import BalancerAPI, BalancerAPIError


def test_v3_query_does_not_use_alltokens():
    """
    Regression test: Verify the V3 GraphQL query uses poolTokens, not allTokens.
    The Balancer V3 API returns 400 when querying the deprecated 'allTokens' field.
    """
    api = BalancerAPI()
    # The query is defined inline in get_current_pool_data - we verify via integration
    # that the API returns 200. For unit test, we check the _normalize method exists
    # and produces allTokens from poolTokens.
    pool_with_pool_tokens = {
        "id": "0x123",
        "name": "Test Pool",
        "poolTokens": [
            {"address": "0xaaa", "symbol": "WETH", "name": "Wrapped Ether", "weight": "0.5"},
            {"address": "0xbbb", "symbol": "USDC", "name": "USD Coin", "weight": "0.5"},
        ],
    }
    normalized = api._normalize_v3_pool_tokens(pool_with_pool_tokens)
    assert "allTokens" in normalized
    assert len(normalized["allTokens"]) == 2
    assert normalized["allTokens"][0]["address"] == "0xaaa"
    assert normalized["allTokens"][0]["symbol"] == "WETH"
    assert normalized["allTokens"][0]["name"] == "Wrapped Ether"
    assert normalized["allTokens"][0]["weight"] == "0.5"


def test_normalize_v3_pool_tokens_uses_symbol_when_name_missing():
    """poolTokens may not have 'name' - fallback to symbol."""
    api = BalancerAPI()
    pool = {
        "poolTokens": [
            {"address": "0xaaa", "symbol": "WETH", "weight": "0.5"},
        ],
    }
    normalized = api._normalize_v3_pool_tokens(pool)
    assert normalized["allTokens"][0]["name"] == "WETH"


def test_normalize_v3_pool_tokens_skips_when_alltokens_present():
    """If allTokens already exists, don't overwrite."""
    api = BalancerAPI()
    pool = {
        "allTokens": [{"address": "0xexisting", "symbol": "X"}],
        "poolTokens": [{"address": "0xnew", "symbol": "Y", "name": "Y", "weight": None}],
    }
    normalized = api._normalize_v3_pool_tokens(pool)
    assert normalized["allTokens"][0]["address"] == "0xexisting"


@pytest.mark.asyncio
async def test_v3_api_returns_200_for_known_pool():
    """
    Integration test: Fetch a known V3 pool and verify we get 200 (not 400).
    Pool addresses from the 'rocket pool' client that were failing before the fix.
    """
    api = BalancerAPI()
    # Known V3 pools that were returning 400 before the allTokens->poolTokens fix
    v3_pool_addresses = [
        "0x1ea5870f7c037930ce1d5d8d9317c670e89e13e3",  # Balancer rETH - Aave WETH
        "0x72192f098b4835f434693d6786e248905d3adceb",  # Rocket pool
    ]
    for pool_address in v3_pool_addresses:
        try:
            pool = await api.get_current_pool_data(pool_address)
            assert pool is not None, f"Pool {pool_address} returned None"
            assert pool.get("name"), f"Pool {pool_address} has no name"
            # Verify allTokens is present (from normalization) for downstream compatibility
            assert "allTokens" in pool or "poolTokens" in pool, (
                f"Pool {pool_address} must have allTokens or poolTokens for downstream code"
            )
        except BalancerAPIError as e:
            pytest.fail(f"V3 API returned error for {pool_address}: {e}")


@pytest.mark.asyncio
async def test_v3_query_does_not_cause_400():
    """
    Regression test: The exact query we send must not cause HTTP 400.
    We patch _execute_query to capture the request and verify the query body.
    """
    captured_queries = []

    async def capture_execute(url, query, variables=None):
        captured_queries.append({"url": url, "query": query, "variables": variables})
        # V2 subgraph returns empty, V3 returns pool - only capture when hitting V3 URL
        if "api-v3" in url or "balancer.fi" in url:
            return {
                "poolGetPool": {
                    "id": "0x1ea5870f7c037930ce1d5d8d9317c670e89e13e3",
                    "name": "Test Pool",
                    "address": "0x1ea5870f7c037930ce1d5d8d9317c670e89e13e3",
                    "poolTokens": [
                        {"address": "0xa", "symbol": "A", "name": "Token A", "weight": None},
                    ],
                }
            }
        return {"pools": []}  # V2 subgraph returns no pools

    api = BalancerAPI()
    with patch.object(api, "_execute_query", side_effect=capture_execute):
        await api.get_current_pool_data("0x1ea5870f7c037930ce1d5d8d9317c670e89e13e3")

    v3_queries = [c for c in captured_queries if "poolGetPool" in c.get("query", "")]
    assert v3_queries, "Should have captured at least one V3 query"
    for cap in v3_queries:
        query = cap.get("query", "")
        assert "poolTokens" in query, "Query must use poolTokens (V3 API schema)"
        assert "allTokens" not in query, (
            "Query must NOT use allTokens - it was removed from V3 API and causes HTTP 400"
        )
