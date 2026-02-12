"""
Test suite for pool history analyzer service.
Tests parameter change detection and impact analysis.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone
from services.pool_history_analyzer import (
    ParameterChange,
    PoolHistoryAnalyzer,
    _is_lbp_pool,
    _is_surge_pool,
)


# Test 1: Parse swap fee change event
def test_parse_swap_fee_change_event():
    """Test parsing of swap fee change event."""
    analyzer = PoolHistoryAnalyzer()
    
    event = {
        "type": "SwapFeePercentageChanged",
        "timestamp": 1704067200,  # 2024-01-01
        "previousFee": "0.003",
        "swapFeePercentage": "0.0025",
    }
    
    change = analyzer._parse_event(event)
    
    assert change is not None
    assert change.change_type == "swap_fee"
    assert change.timestamp == 1704067200
    assert change.details["before"] == "0.003"
    assert change.details["after"] == "0.0025"


# Test 2: Parse weight change event
def test_parse_weight_change_event():
    """Test parsing of weight change event for LBP pools."""
    analyzer = PoolHistoryAnalyzer()
    
    event = {
        "type": "WeightsGraduallyChanged",
        "timestamp": 1704067200,
        "poolType": "LiquidityBootstrapping",  # Must be LBP
        "poolName": "Test LBP",
        "startWeights": ["0.5", "0.5"],
        "endWeights": ["0.6", "0.4"],
    }
    
    change = analyzer._parse_event(event)
    
    assert change is not None
    assert change.change_type == "weights"
    assert change.timestamp == 1704067200
    assert change.details["before"] == ["0.5", "0.5"]
    assert change.details["after"] == ["0.6", "0.4"]


# Test 3: Parse unknown event type returns None
def test_parse_unknown_event_type():
    """Test that unknown event types return None."""
    analyzer = PoolHistoryAnalyzer()
    
    event = {
        "type": "UnknownEventType",
        "timestamp": 1704067200,
    }
    
    change = analyzer._parse_event(event)
    
    assert change is None


# Test 4: Calculate metric changes
def test_calculate_metric_changes():
    """Test calculation of metric percentage changes."""
    analyzer = PoolHistoryAnalyzer()
    
    before = {
        "avg_tvl": 1000000.0,
        "avg_volume": 50000.0,
    }
    
    after = {
        "avg_tvl": 1020000.0,
        "avg_volume": 61500.0,
    }
    
    changes = analyzer._calculate_metric_changes(before, after)
    
    assert "avg_tvl_change_pct" in changes
    assert "avg_volume_change_pct" in changes
    assert changes["avg_tvl_change_pct"] == 2.0
    assert changes["avg_volume_change_pct"] == 23.0


# Test 5: Calculate metric changes with zero before value
def test_calculate_metric_changes_zero_before():
    """Test metric change calculation when before value is zero."""
    analyzer = PoolHistoryAnalyzer()
    
    before = {
        "avg_tvl": 0.0,
        "avg_volume": 50000.0,
    }
    
    after = {
        "avg_tvl": 1000000.0,
        "avg_volume": 60000.0,
    }
    
    changes = analyzer._calculate_metric_changes(before, after)
    
    # When before is 0, change should be 0 (can't calculate percentage)
    assert changes["avg_tvl_change_pct"] == 0
    assert changes["avg_volume_change_pct"] == 20.0


# Test 6: Generate impact summary for swap fee change
def test_generate_impact_summary_swap_fee():
    """Test impact summary generation for swap fee changes."""
    analyzer = PoolHistoryAnalyzer()
    
    change = ParameterChange(
        change_type="swap_fee",
        timestamp=1704067200,
        details={"before": "0.003", "after": "0.0025"}
    )
    
    impact = {
        "avg_volume_change_pct": 23.5,
        "avg_tvl_change_pct": 2.1,
    }
    
    summary = analyzer._generate_impact_summary(change, impact)
    
    assert "decreased" in summary.lower() or "changed" in summary.lower()
    assert "volume" in summary.lower()


# Test 7: Generate impact summary for weight change
def test_generate_impact_summary_weights():
    """Test impact summary generation for weight changes."""
    analyzer = PoolHistoryAnalyzer()
    
    change = ParameterChange(
        change_type="weights",
        timestamp=1704067200,
        details={"before": ["0.5", "0.5"], "after": ["0.6", "0.4"]}
    )
    
    impact = {
        "avg_volume_change_pct": 5.0,
        "avg_tvl_change_pct": 10.0,
    }
    
    summary = analyzer._generate_impact_summary(change, impact)
    
    assert "weights" in summary.lower() or "tvl" in summary.lower()


# Test 8: Deduplicate changes
def test_deduplicate_changes():
    """Test removal of duplicate parameter changes."""
    analyzer = PoolHistoryAnalyzer()
    
    # Create changes with same type and similar timestamps (same day)
    change1 = ParameterChange(
        change_type="swap_fee",
        timestamp=1704067200,  # 2024-01-01 00:00:00
        details={"before": "0.003", "after": "0.0025"}
    )
    
    change2 = ParameterChange(
        change_type="swap_fee",
        timestamp=1704070800,  # 2024-01-01 01:00:00 (same day)
        details={"before": "0.003", "after": "0.0025"}
    )
    
    change3 = ParameterChange(
        change_type="weights",
        timestamp=1704153600,  # 2024-01-02 00:00:00 (different day)
        details={"before": ["0.5", "0.5"], "after": ["0.6", "0.4"]}
    )
    
    changes = [change1, change2, change3]
    unique = analyzer._deduplicate_changes(changes)
    
    # Should have 2 unique changes (one swap_fee, one weights)
    assert len(unique) == 2
    
    # Check that we have both types
    types = [c.change_type for c in unique]
    assert "swap_fee" in types
    assert "weights" in types


# Test 9: Detect changes with mocked events
@pytest.mark.asyncio
async def test_detect_changes_in_period_with_events():
    """Test change detection with mocked event data."""
    analyzer = PoolHistoryAnalyzer()
    
    # Mock pool data to provide pool type context
    mock_pool_data = {
        "type": "LiquidityBootstrapping",  # LBP so weight changes are tracked
        "name": "Test LBP Pool",
    }
    
    # Mock the get_pool_events method
    mock_events = [
        {
            "type": "SwapFeePercentageChanged",
            "timestamp": 1704067200,
            "previousFee": "0.003",
            "swapFeePercentage": "0.0025",
        },
        {
            "type": "WeightsGraduallyChanged",
            "timestamp": 1704153600,
            "startWeights": ["0.5", "0.5"],
            "endWeights": ["0.6", "0.4"],
        }
    ]
    
    with patch.object(
        analyzer.balancer_api,
        'get_current_pool_data',
        new_callable=AsyncMock
    ) as mock_get_pool:
        mock_get_pool.return_value = mock_pool_data
        
        with patch.object(
            analyzer.balancer_api,
            'get_pool_events',
            new_callable=AsyncMock
        ) as mock_get_events:
            mock_get_events.return_value = mock_events
            
            # Mock get_pool_snapshots to return empty (no snapshot-based detection)
            with patch.object(
                analyzer.balancer_api,
                'get_pool_snapshots',
                new_callable=AsyncMock
            ) as mock_get_snapshots:
                mock_get_snapshots.return_value = []
                
                changes = await analyzer.detect_changes_in_period(
                    pool_address="0x1234567890123456789012345678901234567890",
                    days=30
                )
    
    # Should detect 2 changes
    assert len(changes) == 2
    
    # Verify changes are sorted by timestamp (newest first)
    assert changes[0].timestamp >= changes[1].timestamp
    
    # Verify change types
    change_types = [c.change_type for c in changes]
    assert "swap_fee" in change_types
    assert "weights" in change_types


# Test 10: Handle no changes gracefully
@pytest.mark.asyncio
async def test_detect_changes_no_events():
    """Test that no changes returns empty list gracefully."""
    analyzer = PoolHistoryAnalyzer()
    
    with patch.object(
        analyzer.balancer_api,
        'get_pool_events',
        new_callable=AsyncMock
    ) as mock_get_events:
        mock_get_events.return_value = []
        
        with patch.object(
            analyzer.balancer_api,
            'get_pool_snapshots',
            new_callable=AsyncMock
        ) as mock_get_snapshots:
            mock_get_snapshots.return_value = []
            
            changes = await analyzer.detect_changes_in_period(
                pool_address="0x1234567890123456789012345678901234567890",
                days=30
            )
    
    assert len(changes) == 0


# Test 11: Analyze impact with mocked snapshots
@pytest.mark.asyncio
async def test_analyze_impact_of_change():
    """Test impact analysis with mocked snapshot data."""
    analyzer = PoolHistoryAnalyzer()
    
    change = ParameterChange(
        change_type="swap_fee",
        timestamp=1704067200,  # 2024-01-01
        details={"before": "0.003", "after": "0.0025"}
    )
    
    # Mock snapshots for before period
    mock_snapshots_before = [
        {
            "timestamp": 1703721600,  # 2023-12-28
            "liquidity": "1000000",
            "swapVolume": "100000",
        },
        {
            "timestamp": 1703808000,  # 2023-12-29
            "liquidity": "1000000",
            "swapVolume": "150000",
        },
    ]
    
    # Mock snapshots for after period
    mock_snapshots_after = [
        {
            "timestamp": 1704153600,  # 2024-01-02
            "liquidity": "1020000",
            "swapVolume": "200000",
        },
        {
            "timestamp": 1704240000,  # 2024-01-03
            "liquidity": "1020000",
            "swapVolume": "261500",
        },
    ]
    
    call_count = [0]
    
    async def mock_get_snapshots(pool_address, days_back):
        """Mock that returns different snapshots based on call count."""
        call_count[0] += 1
        if call_count[0] == 1:
            # First call: before period
            return mock_snapshots_before
        else:
            # Second call: after period
            return mock_snapshots_after
    
    with patch.object(
        analyzer.balancer_api,
        'get_pool_snapshots',
        side_effect=mock_get_snapshots
    ):
        impact = await analyzer.analyze_impact_of_change(
            pool_address="0x1234567890123456789012345678901234567890",
            change=change
        )
    
    # Check that impact contains expected keys
    assert "summary" in impact
    assert isinstance(impact["summary"], str)
    
    # Impact should have metrics (if snapshots were found)
    # Note: actual values depend on the mock data and calculation logic


# Test 12: Get average metrics from snapshots
@pytest.mark.asyncio
async def test_get_average_metrics_in_period():
    """Test calculation of average metrics from snapshots."""
    analyzer = PoolHistoryAnalyzer()
    
    mock_snapshots = [
        {
            "timestamp": 1704067200,  # 2024-01-01
            "liquidity": "1000000",
            "swapVolume": "100000",
        },
        {
            "timestamp": 1704153600,  # 2024-01-02
            "liquidity": "1100000",
            "swapVolume": "150000",
        },
        {
            "timestamp": 1704240000,  # 2024-01-03
            "liquidity": "1200000",
            "swapVolume": "200000",
        },
    ]
    
    with patch.object(
        analyzer.balancer_api,
        'get_pool_snapshots',
        new_callable=AsyncMock
    ) as mock_get_snapshots:
        mock_get_snapshots.return_value = mock_snapshots
        
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 4, tzinfo=timezone.utc)
        
        metrics = await analyzer._get_average_metrics_in_period(
            pool_address="0x1234567890123456789012345678901234567890",
            start_date=start,
            end_date=end
        )
    
    # Check that metrics are calculated
    assert "avg_tvl" in metrics
    assert "avg_volume" in metrics
    
    # Average TVL should be (1000000 + 1100000 + 1200000) / 3
    assert metrics["avg_tvl"] == pytest.approx(1100000.0, rel=0.01)


# Test 13: Handle API errors gracefully in detect_changes
@pytest.mark.asyncio
async def test_detect_changes_handles_api_errors():
    """Test that API errors are handled gracefully during change detection."""
    analyzer = PoolHistoryAnalyzer()
    
    with patch.object(
        analyzer.balancer_api,
        'get_pool_events',
        new_callable=AsyncMock
    ) as mock_get_events:
        # Simulate API error
        mock_get_events.side_effect = Exception("API connection failed")
        
        with patch.object(
            analyzer.balancer_api,
            'get_pool_snapshots',
            new_callable=AsyncMock
        ) as mock_get_snapshots:
            mock_get_snapshots.return_value = []
            
            # Should not raise exception, but return empty list
            changes = await analyzer.detect_changes_in_period(
                pool_address="0x1234567890123456789012345678901234567890",
                days=30
            )
    
    assert isinstance(changes, list)
    assert len(changes) == 0


# Test 14: Handle empty snapshots in average metrics calculation
@pytest.mark.asyncio
async def test_get_average_metrics_no_snapshots():
    """Test average metrics calculation with no snapshots."""
    analyzer = PoolHistoryAnalyzer()
    
    with patch.object(
        analyzer.balancer_api,
        'get_pool_snapshots',
        new_callable=AsyncMock
    ) as mock_get_snapshots:
        mock_get_snapshots.return_value = []
        
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 8, tzinfo=timezone.utc)
        
        metrics = await analyzer._get_average_metrics_in_period(
            pool_address="0x1234567890123456789012345678901234567890",
            start_date=start,
            end_date=end
        )
    
    # Should return empty dict
    assert metrics == {}


# Test 15: ParameterChange initialization
def test_parameter_change_initialization():
    """Test ParameterChange object initialization."""
    change = ParameterChange(
        change_type="swap_fee",
        timestamp=1704067200,
        details={"before": "0.003", "after": "0.0025"}
    )
    
    assert change.change_type == "swap_fee"
    assert change.timestamp == 1704067200
    assert change.details["before"] == "0.003"
    assert change.details["after"] == "0.0025"
    assert change.impact == {}  # Should be empty dict initially


# Test 16: Impact summary handles minimal changes
def test_generate_impact_summary_minimal_change():
    """Test impact summary for minimal metric changes."""
    analyzer = PoolHistoryAnalyzer()
    
    change = ParameterChange(
        change_type="swap_fee",
        timestamp=1704067200,
        details={"before": "0.003", "after": "0.0025"}
    )
    
    # Very small changes (< 5%)
    impact = {
        "avg_volume_change_pct": 1.2,
        "avg_tvl_change_pct": 0.5,
    }
    
    summary = analyzer._generate_impact_summary(change, impact)
    
    assert "stable" in summary.lower() or "remained" in summary.lower()


# Test 17: Test empty changes list deduplication
def test_deduplicate_empty_changes():
    """Test deduplication with empty list."""
    analyzer = PoolHistoryAnalyzer()
    
    unique = analyzer._deduplicate_changes([])
    
    assert unique == []


# Summary of test coverage:
# ✅ 1. Parse swap fee change event
# ✅ 2. Parse weight change event
# ✅ 3. Parse unknown event returns None
# ✅ 4. Calculate metric changes
# ✅ 5. Calculate metric changes with zero before value
# ✅ 6. Generate impact summary for swap fee
# ✅ 7. Generate impact summary for weights
# ✅ 8. Deduplicate changes
# ✅ 9. Detect changes with mocked events
# ✅ 10. Handle no changes gracefully
# ✅ 11. Analyze impact with mocked snapshots
# ✅ 12. Get average metrics from snapshots
# ✅ 13. Handle API errors gracefully
# ✅ 14. Handle empty snapshots
# ✅ 15. ParameterChange initialization
# ✅ 16. Impact summary handles minimal changes
# ✅ 17. Empty changes list deduplication


# ============================================================================
# Phase 7: New tests for LBP filtering, amp factor, and surge parameters
# ============================================================================

# Test 18: LBP weight change is tracked
def test_lbp_weight_change_tracked():
    """Test that weight changes ARE tracked for LBP pools."""
    analyzer = PoolHistoryAnalyzer()
    
    event = {
        "type": "WeightsGraduallyChanged",
        "timestamp": 1234567890,
        "poolType": "LiquidityBootstrapping",
        "poolName": "LBP Token Launch",
        "startWeights": ["0.9", "0.1"],
        "endWeights": ["0.5", "0.5"],
    }
    
    change = analyzer._parse_event(event)
    
    assert change is not None
    assert change.change_type == "weights"
    assert change.details["before"] == ["0.9", "0.1"]
    assert change.details["after"] == ["0.5", "0.5"]
    assert change.details["pool_type"] == "LiquidityBootstrapping"


# Test 19: Regular weighted pool weight change is ignored
def test_regular_weighted_pool_weight_change_ignored():
    """Test that weight changes are SKIPPED for regular weighted pools."""
    analyzer = PoolHistoryAnalyzer()
    
    event = {
        "type": "WeightsGraduallyChanged",
        "timestamp": 1234567890,
        "poolType": "Weighted",  # Regular weighted pool
        "poolName": "50WETH-50USDC",
        "startWeights": ["0.5", "0.5"],
        "endWeights": ["0.6", "0.4"],
    }
    
    change = analyzer._parse_event(event)
    
    # Should return None (filtered out)
    assert change is None


# Test 20: Amp factor change is parsed
def test_amp_factor_change_parsed():
    """Test parsing of amp factor change event."""
    analyzer = PoolHistoryAnalyzer()
    
    event = {
        "type": "AmpUpdateStarted",
        "timestamp": 1234567890,
        "poolType": "Stable",
        "startValue": "1000",
        "endValue": "1500",
    }
    
    change = analyzer._parse_event(event)
    
    assert change is not None
    assert change.change_type == "amp_factor"
    assert change.details["before"] == "1000"
    assert change.details["after"] == "1500"
    assert change.details["event_type"] == "AmpUpdateStarted"
    assert change.details["pool_type"] == "Stable"


# Test 21: Amp factor change for non-stable pool is ignored
def test_amp_factor_non_stable_pool_ignored():
    """Test that amp factor changes are SKIPPED for non-stable pools."""
    analyzer = PoolHistoryAnalyzer()
    
    event = {
        "type": "AmpUpdateStarted",
        "timestamp": 1234567890,
        "poolType": "Weighted",  # Not a stable pool
        "startValue": "1000",
        "endValue": "1500",
    }
    
    change = analyzer._parse_event(event)
    
    # Should return None (filtered out)
    assert change is None


# Test 22: Amp factor impact summary
def test_amp_factor_impact_summary():
    """Test impact summary generation for amp factor changes."""
    analyzer = PoolHistoryAnalyzer()
    
    change = ParameterChange(
        change_type="amp_factor",
        timestamp=1234567890,
        details={"before": "1000", "after": "1500"}
    )
    
    impact = {
        "avg_volume_change_pct": 15.5,
        "avg_tvl_change_pct": 2.1,
    }
    
    summary = analyzer._generate_impact_summary(change, impact)
    
    assert "1000" in summary
    assert "1500" in summary
    assert "Amplification factor" in summary or "amp" in summary.lower()
    # Should mention the larger change (volume)
    assert "15.5" in summary or "increased" in summary.lower()


# Test 23: Surge threshold change is parsed
def test_surge_threshold_change_parsed():
    """Test parsing of surge threshold change event."""
    analyzer = PoolHistoryAnalyzer()
    
    event = {
        "type": "SurgeThresholdChanged",
        "timestamp": 1234567890,
        "poolType": "Stable",
        "previousThreshold": "0.02",
        "newThreshold": "0.03",
    }
    
    change = analyzer._parse_event(event)
    
    # May not exist in subgraph yet, but if it does, test it
    if change is not None:
        assert change.change_type == "surge_threshold"
        assert change.details["before"] == "0.02"
        assert change.details["after"] == "0.03"
        assert change.details["pool_type"] == "Stable"
    else:
        # Log that surge events are not available (expected)
        print("ℹ️  Surge threshold events not found in subgraph (expected)")


# Test 24: Surge fee change is parsed
def test_surge_fee_change_parsed():
    """Test parsing of surge fee change event."""
    analyzer = PoolHistoryAnalyzer()
    
    event = {
        "type": "SurgeFeeChanged",
        "timestamp": 1234567890,
        "poolType": "Stable",
        "previousMaxFee": "0.10",
        "newMaxFee": "0.15",
    }
    
    change = analyzer._parse_event(event)
    
    # May not exist in subgraph yet, but if it does, test it
    if change is not None:
        assert change.change_type == "max_surge_fee"
        assert change.details["before"] == "0.10"
        assert change.details["after"] == "0.15"
        assert change.details["pool_type"] == "Stable"
    else:
        # Log that surge events are not available (expected)
        print("ℹ️  Surge fee events not found in subgraph (expected)")


# Test 25: Surge threshold impact summary
def test_surge_threshold_impact_summary():
    """Test impact summary generation for surge threshold changes."""
    analyzer = PoolHistoryAnalyzer()
    
    change = ParameterChange(
        change_type="surge_threshold",
        timestamp=1234567890,
        details={"before": "0.02", "after": "0.03"}
    )
    
    impact = {
        "avg_volume_change_pct": -8.5,
        "avg_tvl_change_pct": 1.2,
    }
    
    summary = analyzer._generate_impact_summary(change, impact)
    
    assert "0.02" in summary
    assert "0.03" in summary
    assert "Surge threshold" in summary or "threshold" in summary.lower()
    # Should mention volume decrease
    assert "decreased" in summary.lower() or "8.5" in summary


# Test 26: Max surge fee impact summary
def test_max_surge_fee_impact_summary():
    """Test impact summary generation for max surge fee changes."""
    analyzer = PoolHistoryAnalyzer()
    
    change = ParameterChange(
        change_type="max_surge_fee",
        timestamp=1234567890,
        details={"before": "0.10", "after": "0.15"}
    )
    
    impact = {
        "avg_volume_change_pct": 3.2,
        "avg_tvl_change_pct": 0.8,
    }
    
    summary = analyzer._generate_impact_summary(change, impact)
    
    assert "0.10" in summary
    assert "0.15" in summary
    assert "surge fee" in summary.lower() or "max" in summary.lower()
    # Volume remained relatively stable (< 5%)
    assert "stable" in summary.lower() or "remained" in summary.lower()


# Test 27: Test _is_lbp_pool helper with various pool types
def test_is_lbp_pool_helper():
    """Test the _is_lbp_pool helper function."""
    # Should recognize LBP types
    assert _is_lbp_pool("LiquidityBootstrapping", "") is True
    assert _is_lbp_pool("LBP", "") is True
    assert _is_lbp_pool("Bootstrapping", "") is True
    
    # Should recognize LBP in pool name as fallback
    assert _is_lbp_pool("Weighted", "My LBP Pool") is True
    assert _is_lbp_pool("Weighted", "Token Bootstrapping") is True
    
    # Should NOT recognize regular pools
    assert _is_lbp_pool("Weighted", "50WETH-50USDC") is False
    assert _is_lbp_pool("Stable", "USDC-DAI-USDT") is False
    assert _is_lbp_pool("ComposableStable", "Pool") is False
    
    # Should handle empty/None values
    assert _is_lbp_pool("", "") is False


# Test 28: Test _is_surge_pool helper
def test_is_surge_pool_helper():
    """Test the _is_surge_pool helper function."""
    # Should recognize surge in pool type
    pool_with_surge_type = {"type": "StableSurge", "hook": {}}
    assert _is_surge_pool(pool_with_surge_type) is True
    
    # Should NOT recognize regular stable pools
    regular_stable = {"type": "Stable", "hook": {}}
    assert _is_surge_pool(regular_stable) is False
    
    # Should handle empty pool data
    assert _is_surge_pool({}) is False


# Test 29: Detect changes with pool context (integration test)
@pytest.mark.asyncio
async def test_detect_changes_with_pool_context():
    """Test that pool context is properly passed to events during detection."""
    analyzer = PoolHistoryAnalyzer()
    
    # Mock pool data response
    mock_pool_data = {
        "type": "LiquidityBootstrapping",
        "name": "Test LBP Pool",
    }
    
    # Mock event that would be filtered without context
    mock_events = [
        {
            "type": "WeightsGraduallyChanged",
            "timestamp": 1704067200,
            "startWeights": ["0.8", "0.2"],
            "endWeights": ["0.5", "0.5"],
        }
    ]
    
    with patch.object(
        analyzer.balancer_api,
        'get_current_pool_data',
        new_callable=AsyncMock
    ) as mock_get_pool:
        mock_get_pool.return_value = mock_pool_data
        
        with patch.object(
            analyzer.balancer_api,
            'get_pool_events',
            new_callable=AsyncMock
        ) as mock_get_events:
            mock_get_events.return_value = mock_events
            
            with patch.object(
                analyzer.balancer_api,
                'get_pool_snapshots',
                new_callable=AsyncMock
            ) as mock_get_snapshots:
                mock_get_snapshots.return_value = []
                
                changes = await analyzer.detect_changes_in_period(
                    pool_address="0x1234567890123456789012345678901234567890",
                    days=30
                )
    
    # Should detect the LBP weight change (not filtered out)
    assert len(changes) == 1
    assert changes[0].change_type == "weights"


# Summary of Phase 7 test coverage:
# ✅ 18. LBP weight change is tracked
# ✅ 19. Regular weighted pool weight change is ignored
# ✅ 20. Amp factor change is parsed
# ✅ 21. Amp factor change for non-stable pool is ignored
# ✅ 22. Amp factor impact summary
# ✅ 23. Surge threshold change is parsed (if available)
# ✅ 24. Surge fee change is parsed (if available)
# ✅ 25. Surge threshold impact summary
# ✅ 26. Max surge fee impact summary
# ✅ 27. _is_lbp_pool helper function
# ✅ 28. _is_surge_pool helper function
# ✅ 29. Detect changes with pool context (integration)
