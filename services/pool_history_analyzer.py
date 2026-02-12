"""
Pool History Analyzer: Detect and analyze parameter changes.

This service tracks pool configuration changes (fees, weights, gauges, incentives)
and analyzes their impact on pool performance metrics.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from services.balancer_api import BalancerAPI


class ParameterChange:
    """Represents a single parameter change event."""
    
    def __init__(
        self,
        change_type: str,
        timestamp: int,
        details: dict[str, Any],
    ):
        """
        Initialize a parameter change event.
        
        Args:
            change_type: Type of change ("swap_fee", "weights", "gauge", etc.)
            timestamp: Unix timestamp when change occurred
            details: Dictionary with "before" and "after" values and other details
        """
        self.change_type = change_type
        self.timestamp = timestamp
        self.details = details
        self.impact: dict[str, Any] = {}  # Populated by analyze_impact()


class PoolHistoryAnalyzer:
    """Analyze pool parameter changes and their impact on performance."""
    
    def __init__(self):
        """Initialize the pool history analyzer."""
        self.balancer_api = BalancerAPI()
    
    async def detect_changes_in_period(
        self,
        pool_address: str,
        days: int = 30,
    ) -> list[ParameterChange]:
        """
        Detect all parameter changes in the last {days} days.
        
        Args:
            pool_address: Ethereum address of the pool
            days: Number of days to look back (default: 30)
        
        Returns:
            List of ParameterChange objects, sorted by timestamp (newest first)
        """
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=days)
        
        print(f"🔍 Detecting parameter changes for {pool_address} (last {days} days)")
        
        # Fetch pool data to get pool type for filtering
        try:
            pool_data = await self.balancer_api.get_current_pool_data(pool_address)
            pool_type = pool_data.get("type", "Unknown")
            pool_name = pool_data.get("name", "")
            print(f"   Pool Type: {pool_type}")
        except Exception as e:
            print(f"⚠️  Could not fetch pool data: {e}")
            pool_type = "Unknown"
            pool_name = ""
        
        # Get events from Balancer API
        try:
            events = await self.balancer_api.get_pool_events(
                pool_address=pool_address,
                event_types=[
                    "SwapFeePercentageChanged",
                    "WeightsGraduallyChanged",
                    "AmpUpdateStarted",
                    "AmpUpdateStopped",
                    "SurgeThresholdChanged",  # May not exist in subgraph
                    "SurgeFeeChanged",        # May not exist in subgraph
                ],
                start_timestamp=int(start_time.timestamp()),
                end_timestamp=int(end_time.timestamp()),
            )
        except Exception as e:
            print(f"⚠️  Error fetching pool events: {str(e)}")
            events = []
        
        # Parse events into ParameterChange objects
        changes = []
        for event in events:
            # Add pool context to event for LBP filtering
            event["poolType"] = pool_type
            event["poolName"] = pool_name
            
            change = self._parse_event(event)
            if change:
                changes.append(change)
        
        # Additionally detect changes by comparing snapshots
        # This is more reliable for V2 pools where events may not be tracked
        snapshot_changes = await self._detect_changes_from_snapshots(
            pool_address, start_time, end_time
        )
        changes.extend(snapshot_changes)
        
        # Remove duplicates (same type and similar timestamp)
        unique_changes = self._deduplicate_changes(changes)
        
        # Sort by timestamp (newest first)
        unique_changes.sort(key=lambda c: c.timestamp, reverse=True)
        
        print(f"✅ Detected {len(unique_changes)} parameter changes")
        
        return unique_changes
    
    async def analyze_impact_of_change(
        self,
        pool_address: str,
        change: ParameterChange,
    ) -> dict[str, Any]:
        """
        Analyze impact of a parameter change on pool metrics.
        
        Compares metrics before and after the change (7 days on each side).
        
        Args:
            pool_address: Ethereum address of the pool
            change: ParameterChange object to analyze
        
        Returns:
            Dictionary with impact metrics:
            {
                "volume_change_pct": +23.5,
                "tvl_change_pct": +2.1,
                "summary": "Volume increased significantly after fee reduction"
            }
        """
        print(f"📊 Analyzing impact of {change.change_type} change")
        
        # Get the change date
        change_date = datetime.fromtimestamp(change.timestamp, tz=timezone.utc)
        
        # Fetch metrics 7 days before
        before_end = change_date - timedelta(hours=1)
        before_start = before_end - timedelta(days=7)
        
        try:
            metrics_before = await self._get_average_metrics_in_period(
                pool_address, before_start, before_end
            )
        except Exception as e:
            print(f"⚠️  Error fetching metrics before change: {str(e)}")
            metrics_before = {}
        
        # Fetch metrics 7 days after
        after_start = change_date + timedelta(hours=1)
        after_end = after_start + timedelta(days=7)
        
        try:
            metrics_after = await self._get_average_metrics_in_period(
                pool_address, after_start, after_end
            )
        except Exception as e:
            print(f"⚠️  Error fetching metrics after change: {str(e)}")
            metrics_after = {}
        
        # Calculate percentage changes
        impact = self._calculate_metric_changes(metrics_before, metrics_after)
        
        # Generate human-readable summary
        impact["summary"] = self._generate_impact_summary(change, impact)
        
        return impact
    
    async def _get_average_metrics_in_period(
        self,
        pool_address: str,
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, float]:
        """
        Get average metrics over a time period.
        
        Uses pool snapshots to calculate average volume, TVL, etc.
        
        Args:
            pool_address: Ethereum address of the pool
            start_date: Start of period
            end_date: End of period
        
        Returns:
            Dictionary with average metrics:
            {
                "avg_tvl": 1500000.0,
                "avg_volume": 50000.0,
                "avg_fees": 150.0
            }
        """
        # Get snapshots covering the period (with buffer)
        days = (end_date - start_date).days + 30  # Extra buffer
        
        try:
            snapshots = await self.balancer_api.get_pool_snapshots(
                pool_address, days_back=days
            )
        except Exception as e:
            print(f"⚠️  Error fetching snapshots: {str(e)}")
            return {}
        
        if not snapshots:
            return {}
        
        # Filter to date range
        start_ts = int(start_date.timestamp())
        end_ts = int(end_date.timestamp())
        
        period_snapshots = [
            s for s in snapshots
            if start_ts <= int(s.get("timestamp", 0)) <= end_ts
        ]
        
        if not period_snapshots:
            print(f"⚠️  No snapshots found in period {start_date} to {end_date}")
            return {}
        
        print(f"   Found {len(period_snapshots)} snapshots in period")
        
        # Calculate averages
        total_tvl = sum(float(s.get("liquidity", 0)) for s in period_snapshots)
        avg_tvl = total_tvl / len(period_snapshots)
        
        # Calculate daily volume from cumulative swapVolume
        # We need to look at the difference between first and last snapshot
        if len(period_snapshots) >= 2:
            first_vol = float(period_snapshots[0].get("swapVolume", 0))
            last_vol = float(period_snapshots[-1].get("swapVolume", 0))
            total_volume = last_vol - first_vol
            days_in_period = (end_date - start_date).days or 1
            avg_daily_volume = total_volume / days_in_period
        else:
            avg_daily_volume = 0
        
        return {
            "avg_tvl": avg_tvl,
            "avg_volume": avg_daily_volume,
        }
    
    def _calculate_metric_changes(
        self,
        before: dict[str, float],
        after: dict[str, float],
    ) -> dict[str, float]:
        """
        Calculate percentage changes between before and after metrics.
        
        Args:
            before: Metrics before change
            after: Metrics after change
        
        Returns:
            Dictionary with percentage changes for each metric
        """
        changes = {}
        
        for metric, before_value in before.items():
            after_value = after.get(metric, 0)
            
            if before_value > 0:
                pct_change = ((after_value - before_value) / before_value) * 100
                changes[f"{metric}_change_pct"] = round(pct_change, 1)
            else:
                # If before value is 0, can't calculate percentage
                changes[f"{metric}_change_pct"] = 0
        
        return changes
    
    def _generate_impact_summary(
        self,
        change: ParameterChange,
        impact: dict[str, float],
    ) -> str:
        """
        Generate human-readable impact summary.
        
        Args:
            change: The parameter change
            impact: Impact metrics dictionary
        
        Returns:
            Human-readable summary string
        """
        # Extract impact metrics
        volume_change = impact.get("avg_volume_change_pct", 0)
        tvl_change = impact.get("avg_tvl_change_pct", 0)
        
        # Build summary based on change type and metrics
        if change.change_type == "swap_fee":
            before_fee = change.details.get("before", "?")
            after_fee = change.details.get("after", "?")
            
            # Determine if fee increased or decreased
            try:
                before_val = float(before_fee) if before_fee != "?" else 0
                after_val = float(after_fee) if after_fee != "?" else 0
                fee_direction = "increased" if after_val > before_val else "decreased"
            except (ValueError, TypeError):
                fee_direction = "changed"
            
            # Analyze volume impact
            if abs(volume_change) < 5:
                volume_impact = "Volume remained stable"
            elif volume_change > 0:
                volume_impact = f"Volume increased by {abs(volume_change):.1f}%"
            else:
                volume_impact = f"Volume decreased by {abs(volume_change):.1f}%"
            
            return f"Swap fee {fee_direction}. {volume_impact}."
        
        elif change.change_type == "weights":
            # Analyze weight change impact
            if abs(tvl_change) < 5:
                tvl_impact = "TVL remained stable"
            elif tvl_change > 0:
                tvl_impact = f"TVL increased by {abs(tvl_change):.1f}%"
            else:
                tvl_impact = f"TVL decreased by {abs(tvl_change):.1f}%"
            
            return f"Pool weights adjusted. {tvl_impact}."
        
        elif change.change_type == "amp_factor":
            before_amp = change.details.get("before", "?")
            after_amp = change.details.get("after", "?")
            
            # Analyze volume/TVL impact
            if abs(volume_change) < 5 and abs(tvl_change) < 5:
                impact_str = "Minimal impact on metrics"
            elif abs(volume_change) >= abs(tvl_change):
                if volume_change > 0:
                    impact_str = f"Volume increased by {abs(volume_change):.1f}%"
                else:
                    impact_str = f"Volume decreased by {abs(volume_change):.1f}%"
            else:
                if tvl_change > 0:
                    impact_str = f"TVL increased by {abs(tvl_change):.1f}%"
                else:
                    impact_str = f"TVL decreased by {abs(tvl_change):.1f}%"
            
            return f"Amplification factor changed from {before_amp} to {after_amp}. {impact_str}."
        
        elif change.change_type == "surge_threshold":
            before_val = change.details.get("before", "?")
            after_val = change.details.get("after", "?")
            
            if abs(volume_change) < 5:
                volume_impact = "Volume remained stable"
            elif volume_change > 0:
                volume_impact = f"Volume increased by {abs(volume_change):.1f}%"
            else:
                volume_impact = f"Volume decreased by {abs(volume_change):.1f}%"
            
            return f"Surge threshold adjusted from {before_val} to {after_val}. {volume_impact}."
        
        elif change.change_type == "max_surge_fee":
            before_fee = change.details.get("before", "?")
            after_fee = change.details.get("after", "?")
            
            if abs(volume_change) < 5:
                volume_impact = "Volume remained stable"
            elif volume_change > 0:
                volume_impact = f"Volume increased by {abs(volume_change):.1f}%"
            else:
                volume_impact = f"Volume decreased by {abs(volume_change):.1f}%"
            
            return f"Max surge fee changed from {before_fee} to {after_fee}. {volume_impact}."
        
        else:
            # Generic summary
            if abs(volume_change) >= abs(tvl_change):
                primary_metric = "volume"
                primary_change = volume_change
            else:
                primary_metric = "TVL"
                primary_change = tvl_change
            
            if abs(primary_change) < 5:
                return "Minimal impact on pool metrics."
            elif primary_change > 0:
                return f"Positive impact: {primary_metric} increased by {abs(primary_change):.1f}%."
            else:
                return f"Negative impact: {primary_metric} decreased by {abs(primary_change):.1f}%."
    
    def _parse_event(self, event: dict[str, Any]) -> ParameterChange | None:
        """
        Parse raw event into ParameterChange object.
        
        Args:
            event: Raw event dictionary from Balancer API
        
        Returns:
            ParameterChange object or None if event cannot be parsed
        """
        event_type = event.get("type")
        
        if event_type == "SwapFeePercentageChanged":
            return ParameterChange(
                change_type="swap_fee",
                timestamp=int(event.get("timestamp", 0)),
                details={
                    "before": event.get("previousFee", "unknown"),
                    "after": event.get("swapFeePercentage", "unknown"),
                }
            )
        
        elif event_type == "WeightsGraduallyChanged":
            # Get pool type from event context
            pool_type = event.get("poolType", "")
            pool_name = event.get("poolName", "")
            
            # Only track weight changes for LBP pools
            # Regular weighted pools have immutable weights
            if not _is_lbp_pool(pool_type, pool_name):
                print(f"   ℹ️  Skipping weight change (not an LBP pool: {pool_type})")
                return None
            
            print(f"   ✅ Detected LBP weight change")
            return ParameterChange(
                change_type="weights",
                timestamp=int(event.get("timestamp", 0)),
                details={
                    "before": event.get("startWeights", []),
                    "after": event.get("endWeights", []),
                    "pool_type": pool_type,  # Include for reference
                }
            )
        
        elif event_type == "AmpUpdateStarted" or event_type == "AmpUpdateStopped":
            # Amp factor changes in stable pools
            # These events indicate gradual amp parameter updates
            
            # Only relevant for stable pools
            pool_type = event.get("poolType", "")
            if "stable" not in pool_type.lower():
                print(f"   ℹ️  Skipping amp change (not a stable pool: {pool_type})")
                return None
            
            return ParameterChange(
                change_type="amp_factor",
                timestamp=int(event.get("timestamp", 0)),
                details={
                    "before": event.get("startValue", event.get("oldAmpFactor", "unknown")),
                    "after": event.get("endValue", event.get("newAmpFactor", "unknown")),
                    "event_type": event_type,  # Started or Stopped
                    "pool_type": pool_type,
                }
            )
        
        elif event_type == "SurgeThresholdChanged":
            return ParameterChange(
                change_type="surge_threshold",
                timestamp=int(event.get("timestamp", 0)),
                details={
                    "before": event.get("previousThreshold", "unknown"),
                    "after": event.get("newThreshold", "unknown"),
                    "pool_type": event.get("poolType", ""),
                }
            )
        
        elif event_type == "SurgeFeeChanged":
            return ParameterChange(
                change_type="max_surge_fee",
                timestamp=int(event.get("timestamp", 0)),
                details={
                    "before": event.get("previousMaxFee", "unknown"),
                    "after": event.get("newMaxFee", "unknown"),
                    "pool_type": event.get("poolType", ""),
                }
            )
        
        # Add more event types as needed
        
        return None
    
    async def _detect_changes_from_snapshots(
        self,
        pool_address: str,
        start_date: datetime,
        end_date: datetime,
    ) -> list[ParameterChange]:
        """
        Detect parameter changes by comparing consecutive snapshots.
        
        This is a fallback method when event logs are not available.
        
        Args:
            pool_address: Ethereum address of the pool
            start_date: Start of detection period
            end_date: End of detection period
        
        Returns:
            List of detected ParameterChange objects
        """
        changes = []
        
        try:
            # Get snapshots for the period
            days = (end_date - start_date).days + 10  # Extra buffer
            snapshots = await self.balancer_api.get_pool_snapshots(
                pool_address, days_back=days
            )
            
            if len(snapshots) < 2:
                return changes
            
            # Note: V2 subgraph snapshots don't include swapFee or weights
            # This would require querying the pool state at each block
            # For now, we'll document this as a limitation
            
            print(f"ℹ️  Snapshot-based change detection has limited data in V2 subgraph")
            print(f"   Consider using event logs or pool state queries for more accurate detection")
            
        except Exception as e:
            print(f"⚠️  Error detecting changes from snapshots: {str(e)}")
        
        return changes
    
    def _deduplicate_changes(
        self,
        changes: list[ParameterChange],
    ) -> list[ParameterChange]:
        """
        Remove duplicate changes (same type and similar timestamp).
        
        Args:
            changes: List of ParameterChange objects
        
        Returns:
            Deduplicated list of ParameterChange objects
        """
        if not changes:
            return []
        
        unique = []
        seen = set()
        
        for change in changes:
            # Create a key based on type and timestamp (rounded to day)
            day_timestamp = change.timestamp // 86400  # Round to day
            key = (change.change_type, day_timestamp)
            
            if key not in seen:
                seen.add(key)
                unique.append(change)
        
        return unique


def _is_lbp_pool(pool_type: str, pool_name: str = "") -> bool:
    """
    Check if pool is a Liquidity Bootstrapping Pool.
    
    LBPs are the ONLY pool type where weight changes are expected.
    Regular weighted pools have immutable weights.
    
    Args:
        pool_type: Pool type from API (e.g., "Weighted", "LiquidityBootstrapping")
        pool_name: Pool name for additional context
        
    Returns:
        True if pool is an LBP, False otherwise
    """
    if not pool_type:
        return False
    
    # LBP indicators in pool type
    lbp_indicators = ["LBP", "LiquidityBootstrapping", "Bootstrapping"]
    
    pool_type_upper = pool_type.upper()
    pool_name_upper = pool_name.upper()
    
    # Check type field
    for indicator in lbp_indicators:
        if indicator.upper() in pool_type_upper:
            return True
    
    # Check name as fallback
    if "LBP" in pool_name_upper or "BOOTSTRAPPING" in pool_name_upper:
        return True
    
    return False


def _is_surge_pool(pool_data: dict) -> bool:
    """
    Check if pool is a Stable Surge pool.
    
    Surge pools use a specific hook contract for dynamic fees.
    
    Args:
        pool_data: Pool data from API
        
    Returns:
        True if pool uses surge hook
    """
    # Check pool type
    pool_type = pool_data.get("type", "")
    if "surge" in pool_type.lower():
        return True
    
    # Check hook address (if available in API response)
    hook = pool_data.get("hook", {})
    hook_address = hook.get("address", "") if isinstance(hook, dict) else ""
    
    # Known surge hook contracts (Ethereum mainnet)
    # TODO: Add known surge hook addresses when available
    SURGE_HOOK_ADDRESSES = [
        # "0x...",  # Add known surge hook addresses
    ]
    
    if hook_address and hook_address.lower() in [h.lower() for h in SURGE_HOOK_ADDRESSES]:
        return True
    
    return False
