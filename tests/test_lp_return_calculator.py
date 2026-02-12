"""
Test suite for LP return calculator service.
Tests hold vs pool return calculations, impermanent loss, and comparisons.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from services.lp_return_calculator import LPReturnCalculator


# Mock price data for testing
MOCK_PRICES_STABLE = [
    {"timestamp": 1000000, "price": 1.00},
    {"timestamp": 1100000, "price": 1.00},
    {"timestamp": 1200000, "price": 1.00},
]

MOCK_PRICES_UP_10_PERCENT = [
    {"timestamp": 1000000, "price": 1.00},
    {"timestamp": 1100000, "price": 1.05},
    {"timestamp": 1200000, "price": 1.10},
]

MOCK_PRICES_DOWN_10_PERCENT = [
    {"timestamp": 1000000, "price": 1.00},
    {"timestamp": 1100000, "price": 0.95},
    {"timestamp": 1200000, "price": 0.90},
]

MOCK_PRICES_UP_50_PERCENT = [
    {"timestamp": 1000000, "price": 1.00},
    {"timestamp": 1100000, "price": 1.25},
    {"timestamp": 1200000, "price": 1.50},
]

# Mock pool data
MOCK_POOL_DATA_50_50 = {
    "id": "0x123",
    "address": "0x123",
    "name": "50WETH-50USDC",
    "type": "WEIGHTED",
    "allTokens": [
        {"address": "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2", "symbol": "WETH", "weight": "0.5"},
        {"address": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48", "symbol": "USDC", "weight": "0.5"},
    ],
    "dynamicData": {
        "aprItems": [
            {"type": "SWAP_FEE", "apr": 5.0},
            {"type": "STAKING", "apr": 3.0},
        ]
    }
}

MOCK_POOL_DATA_80_20 = {
    "id": "0x456",
    "address": "0x456",
    "name": "80WETH-20DAI",
    "type": "WEIGHTED",
    "allTokens": [
        {"address": "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2", "symbol": "WETH", "weight": "0.8"},
        {"address": "0x6b175474e89094c44da98b954eedeac495271d0f", "symbol": "DAI", "weight": "0.2"},
    ],
    "dynamicData": {
        "aprItems": []
    }
}

MOCK_SNAPSHOTS = [
    {"liquidity": "1000000", "swapFees": "10000", "timestamp": 1000000},
    {"liquidity": "1100000", "swapFees": "10500", "timestamp": 1100000},
    {"liquidity": "1200000", "swapFees": "11000", "timestamp": 1200000},
]


# Test 1: Hold return calculation with stable prices
@pytest.mark.asyncio
async def test_hold_return_stable_prices():
    """Test hold return calculation when prices don't change."""
    calc = LPReturnCalculator()
    
    # Mock price API
    calc.price_api.get_token_price_history = AsyncMock(return_value=MOCK_PRICES_STABLE)
    
    tokens = MOCK_POOL_DATA_50_50["allTokens"]
    result = await calc._calculate_hold_return(tokens, days=30, initial_investment_usd=10000)
    
    # With stable prices, return should be ~0%
    assert result["return_pct"] == pytest.approx(0.0, abs=0.1)
    assert result["final_value_usd"] == pytest.approx(10000, abs=1)


# Test 2: Hold return calculation with price increase
@pytest.mark.asyncio
async def test_hold_return_price_increase():
    """Test hold return calculation when prices increase."""
    calc = LPReturnCalculator()
    
    # Mock price API - both tokens increase 10%
    calc.price_api.get_token_price_history = AsyncMock(return_value=MOCK_PRICES_UP_10_PERCENT)
    
    tokens = MOCK_POOL_DATA_50_50["allTokens"]
    result = await calc._calculate_hold_return(tokens, days=30, initial_investment_usd=10000)
    
    # With 10% price increase, return should be ~10%
    assert result["return_pct"] == pytest.approx(10.0, abs=0.5)
    assert result["final_value_usd"] == pytest.approx(11000, abs=50)


# Test 3: Hold return calculation with price decrease
@pytest.mark.asyncio
async def test_hold_return_price_decrease():
    """Test hold return calculation when prices decrease."""
    calc = LPReturnCalculator()
    
    # Mock price API - both tokens decrease 10%
    calc.price_api.get_token_price_history = AsyncMock(return_value=MOCK_PRICES_DOWN_10_PERCENT)
    
    tokens = MOCK_POOL_DATA_50_50["allTokens"]
    result = await calc._calculate_hold_return(tokens, days=30, initial_investment_usd=10000)
    
    # With 10% price decrease, return should be ~-10%
    assert result["return_pct"] == pytest.approx(-10.0, abs=0.5)
    assert result["final_value_usd"] == pytest.approx(9000, abs=50)


# Test 4: Impermanent loss calculation for 50/50 pool with no price change
@pytest.mark.asyncio
async def test_impermanent_loss_no_change():
    """Test IL calculation when prices don't change."""
    calc = LPReturnCalculator()
    
    # Mock price API - stable prices
    calc.price_api.get_token_price_history = AsyncMock(return_value=MOCK_PRICES_STABLE)
    
    tokens = MOCK_POOL_DATA_50_50["allTokens"]
    il = await calc._calculate_impermanent_loss(tokens, days=30)
    
    # No price change = no IL
    assert il == pytest.approx(0.0, abs=0.001)


# Test 5: Impermanent loss calculation for 50/50 pool with divergent prices
@pytest.mark.asyncio
async def test_impermanent_loss_divergent_prices():
    """Test IL calculation when token prices diverge."""
    calc = LPReturnCalculator()
    
    # Mock price API - token 1 stays stable, token 2 increases 50%
    async def mock_get_price_history(token_address, days):
        if "weth" in token_address.lower() or "c02aaa" in token_address.lower():
            return MOCK_PRICES_UP_50_PERCENT
        else:
            return MOCK_PRICES_STABLE
    
    calc.price_api.get_token_price_history = mock_get_price_history
    
    tokens = MOCK_POOL_DATA_50_50["allTokens"]
    il = await calc._calculate_impermanent_loss(tokens, days=30)
    
    # With 1.5x price ratio in 50/50 pool, IL should be negative (loss)
    # The actual IL is around -11% (using the correct weighted formula)
    assert il < 0  # Should be negative (loss)
    assert il == pytest.approx(-0.11, abs=0.02)  # About -11% IL


# Test 6: Impermanent loss calculation for 80/20 pool
@pytest.mark.asyncio
async def test_impermanent_loss_weighted_pool():
    """Test IL calculation for weighted pool (80/20)."""
    calc = LPReturnCalculator()
    
    # Mock price API - token 1 increases 50%, token 2 stable
    async def mock_get_price_history(token_address, days):
        if "weth" in token_address.lower() or "c02aaa" in token_address.lower():
            return MOCK_PRICES_UP_50_PERCENT
        else:
            return MOCK_PRICES_STABLE
    
    calc.price_api.get_token_price_history = mock_get_price_history
    
    tokens = MOCK_POOL_DATA_80_20["allTokens"]
    il = await calc._calculate_impermanent_loss(tokens, days=30)
    
    # Weighted pools have less IL than 50/50 (50/50 had -11%, this should be less)
    assert il < 0  # Should be negative (loss)
    assert abs(il) < abs(-0.11)  # Should be less than 50/50 pool IL
    assert il == pytest.approx(-0.067, abs=0.01)  # About -6.7% IL for 80/20


# Test 7: Fees earned calculation from snapshots
@pytest.mark.asyncio
async def test_fees_earned_from_snapshots():
    """Test fee calculation using snapshot data."""
    calc = LPReturnCalculator()
    
    # Mock Balancer API
    calc.balancer_api.get_pool_snapshots = AsyncMock(return_value=MOCK_SNAPSHOTS)
    
    fees = await calc._calculate_fees_earned(
        pool_address="0x123",
        days=30,
        initial_investment_usd=10000
    )
    
    # Total fees in snapshots: 11000 - 10000 = 1000
    # Our share with 10000 investment in 1M TVL: 1000 * (10000/1000000) = 10
    assert fees == pytest.approx(10.0, abs=0.1)


# Test 8: Fees earned calculation from APR (fallback)
@pytest.mark.asyncio
async def test_fees_earned_from_apr():
    """Test fee calculation using APR when snapshots unavailable."""
    calc = LPReturnCalculator()
    
    # Mock empty snapshots
    calc.balancer_api.get_pool_snapshots = AsyncMock(return_value=[])
    calc.balancer_api.get_current_pool_data = AsyncMock(return_value=MOCK_POOL_DATA_50_50)
    
    fees = await calc._calculate_fees_earned(
        pool_address="0x123",
        days=30,
        initial_investment_usd=10000
    )
    
    # APR is 5%, so daily rate = 5/365 = 0.0137%
    # Over 30 days: 10000 * 0.05 / 365 * 30 ≈ 41.10
    assert fees == pytest.approx(41.10, abs=5)


# Test 9: Incentives calculation
def test_incentives_earned():
    """Test incentive calculation from APR data."""
    calc = LPReturnCalculator()
    
    incentives = calc._calculate_incentives_earned(
        pool_data=MOCK_POOL_DATA_50_50,
        days=30,
        initial_investment_usd=10000
    )
    
    # STAKING APR is 3%, so daily rate = 3/365 = 0.00822%
    # Over 30 days: 10000 * 0.03 / 365 * 30 ≈ 24.66
    assert incentives == pytest.approx(24.66, abs=5)


# Test 10: Comparison logic - pool wins
def test_comparison_pool_wins():
    """Test comparison when pool strategy outperforms hold."""
    calc = LPReturnCalculator()
    
    hold_result = {"return_pct": 10.0, "return_usd": 1000}
    pool_result = {"return_pct": 15.0, "return_usd": 1500}
    
    comparison = calc._compare_strategies(hold_result, pool_result)
    
    assert comparison["winner"] == "pool"
    assert comparison["difference_pct"] == pytest.approx(5.0, abs=0.1)
    assert "more profitable" in comparison["recommendation"]


# Test 11: Comparison logic - hold wins
def test_comparison_hold_wins():
    """Test comparison when hold strategy outperforms pool."""
    calc = LPReturnCalculator()
    
    hold_result = {"return_pct": 15.0, "return_usd": 1500}
    pool_result = {"return_pct": 10.0, "return_usd": 1000}
    
    comparison = calc._compare_strategies(hold_result, pool_result)
    
    assert comparison["winner"] == "hold"
    assert comparison["difference_pct"] == pytest.approx(-5.0, abs=0.1)
    assert "Holding tokens" in comparison["recommendation"]


# Test 12: Comparison logic - tie
def test_comparison_tie():
    """Test comparison when strategies perform similarly."""
    calc = LPReturnCalculator()
    
    hold_result = {"return_pct": 10.0, "return_usd": 1000}
    pool_result = {"return_pct": 10.5, "return_usd": 1050}
    
    comparison = calc._compare_strategies(hold_result, pool_result)
    
    assert "similarly" in comparison["recommendation"]


# Test 13: Full integration test with mocked data
@pytest.mark.asyncio
async def test_calculate_hold_vs_pool_full():
    """Test full hold vs pool calculation with mocked services."""
    calc = LPReturnCalculator()
    
    # Mock all required APIs
    calc.balancer_api.get_current_pool_data = AsyncMock(return_value=MOCK_POOL_DATA_50_50)
    calc.balancer_api.get_pool_snapshots = AsyncMock(return_value=MOCK_SNAPSHOTS)
    calc.price_api.get_token_price_history = AsyncMock(return_value=MOCK_PRICES_UP_10_PERCENT)
    
    result = await calc.calculate_hold_vs_pool(
        pool_address="0x123",
        days=30,
        initial_investment_usd=10000
    )
    
    # Check structure
    assert "period_days" in result
    assert "initial_investment_usd" in result
    assert "hold_strategy" in result
    assert "pool_strategy" in result
    assert "comparison" in result
    
    # Check hold strategy
    assert result["hold_strategy"]["return_pct"] > 0
    assert result["hold_strategy"]["final_value_usd"] > 10000
    
    # Check pool strategy
    assert "breakdown" in result["pool_strategy"]
    assert "fees_earned_usd" in result["pool_strategy"]["breakdown"]
    assert "incentives_earned_usd" in result["pool_strategy"]["breakdown"]
    assert "impermanent_loss_usd" in result["pool_strategy"]["breakdown"]
    assert "token_appreciation_usd" in result["pool_strategy"]["breakdown"]
    
    # Check comparison
    assert result["comparison"]["winner"] in ["pool", "hold"]


# Test 14: Error handling - insufficient price data
@pytest.mark.asyncio
async def test_hold_return_insufficient_data():
    """Test hold return calculation with insufficient price data."""
    calc = LPReturnCalculator()
    
    # Mock empty price data
    calc.price_api.get_token_price_history = AsyncMock(return_value=[])
    
    tokens = MOCK_POOL_DATA_50_50["allTokens"]
    result = await calc._calculate_hold_return(tokens, days=30, initial_investment_usd=10000)
    
    # Should return initial investment (no change assumed)
    assert result["return_pct"] == pytest.approx(0.0, abs=0.1)
    assert result["final_value_usd"] == pytest.approx(10000, abs=1)


# Test 15: Error handling - empty pool data
@pytest.mark.asyncio
async def test_calculate_hold_vs_pool_empty_tokens():
    """Test full calculation with empty token list."""
    calc = LPReturnCalculator()
    
    # Mock pool data with no tokens
    empty_pool_data = {
        "id": "0x123",
        "address": "0x123",
        "name": "Empty Pool",
        "allTokens": []
    }
    calc.balancer_api.get_current_pool_data = AsyncMock(return_value=empty_pool_data)
    
    result = await calc.calculate_hold_vs_pool(
        pool_address="0x123",
        days=30,
        initial_investment_usd=10000
    )
    
    # Should return empty result
    assert result["comparison"]["winner"] == "unknown"


# Test 16: Pool return calculation includes all components
@pytest.mark.asyncio
async def test_pool_return_all_components():
    """Test that pool return includes fees, incentives, IL, and appreciation."""
    calc = LPReturnCalculator()
    
    # Mock all APIs
    calc.balancer_api.get_pool_snapshots = AsyncMock(return_value=MOCK_SNAPSHOTS)
    calc.price_api.get_token_price_history = AsyncMock(return_value=MOCK_PRICES_UP_10_PERCENT)
    
    result = await calc._calculate_pool_return(
        pool_address="0x123",
        pool_data=MOCK_POOL_DATA_50_50,
        tokens=MOCK_POOL_DATA_50_50["allTokens"],
        days=30,
        initial_investment_usd=10000
    )
    
    # Check that all breakdown components exist
    breakdown = result["breakdown"]
    assert "fees_earned_usd" in breakdown
    assert "incentives_earned_usd" in breakdown
    assert "impermanent_loss_usd" in breakdown
    assert "token_appreciation_usd" in breakdown
    
    # Fees should be positive
    assert breakdown["fees_earned_usd"] >= 0
    
    # IL should be negative or zero
    assert breakdown["impermanent_loss_usd"] <= 0


# Test 17: Three-token pool IL calculation
@pytest.mark.asyncio
async def test_impermanent_loss_three_token_pool():
    """Test IL calculation for pool with more than 2 tokens (not supported)."""
    calc = LPReturnCalculator()
    
    three_token_pool = [
        {"address": "0x1", "symbol": "TOKEN1", "weight": "0.33"},
        {"address": "0x2", "symbol": "TOKEN2", "weight": "0.33"},
        {"address": "0x3", "symbol": "TOKEN3", "weight": "0.34"},
    ]
    
    calc.price_api.get_token_price_history = AsyncMock(return_value=MOCK_PRICES_UP_10_PERCENT)
    
    il = await calc._calculate_impermanent_loss(three_token_pool, days=30)
    
    # Should return 0 for unsupported pool types
    assert il == 0.0


# Test 18: Real pool simulation - conservative case
@pytest.mark.asyncio
async def test_real_pool_simulation_conservative():
    """Simulate a real-world scenario where hold slightly outperforms pool."""
    calc = LPReturnCalculator()
    
    # Scenario: Tokens increase 20%, but IL eats into profits
    # Fees and incentives partially compensate
    
    calc.balancer_api.get_current_pool_data = AsyncMock(return_value=MOCK_POOL_DATA_50_50)
    calc.balancer_api.get_pool_snapshots = AsyncMock(return_value=MOCK_SNAPSHOTS)
    
    async def mock_divergent_prices(token_address, days):
        if "weth" in token_address.lower() or "c02aaa" in token_address.lower():
            # WETH increases 50%
            return MOCK_PRICES_UP_50_PERCENT
        else:
            # USDC stays stable
            return MOCK_PRICES_STABLE
    
    calc.price_api.get_token_price_history = mock_divergent_prices
    
    result = await calc.calculate_hold_vs_pool(
        pool_address="0x123",
        days=30,
        initial_investment_usd=10000
    )
    
    # In this scenario:
    # Hold: 50% of investment in WETH (+50%) + 50% in USDC (0%) = +25% total
    # Pool: Similar appreciation but with IL reducing gains, plus fees/incentives
    
    # Pool should underperform hold due to significant IL
    assert result["pool_strategy"]["breakdown"]["impermanent_loss_usd"] < 0
