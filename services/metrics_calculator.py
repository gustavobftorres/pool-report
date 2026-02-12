"""
Metrics calculator service for comparing pool performance.
Analyzes current metrics vs 15 days ago.
"""
from datetime import datetime, timedelta
from typing import Dict, Any
from services.balancer_api import BalancerAPI
from services.boosted_pool_analyzer import get_boosted_pool_type
from models import PoolMetrics, MultiPoolMetrics


class MetricsCalculator:
    """Service for calculating and comparing pool metrics."""
    
    def __init__(self):
        self.api = BalancerAPI()
    
    def _format_adaptive_percentage(self, value: float | None, max_decimals: int = 8) -> str:
        """
        Format a percentage value adaptively, rounding intelligently and removing trailing zeros.
        
        Examples:
            0.00999412 → "0.01%" (rounded to 2 decimals)
            0.01 → "0.01%"
            0.0001 → "0.0001%"
            0.000001 → "0.000001%"
            1.5 → "1.5%"
        
        Args:
            value: Percentage value as decimal (e.g., 0.01 for 1%)
            max_decimals: Maximum number of decimal places to show and round to
            
        Returns:
            Formatted string with % symbol, or "N/A" if value is None
        """
        if value is None:
            return "N/A"
        
        # Convert to percentage
        percentage = value * 100
        
        # Determine appropriate rounding based on magnitude
        if percentage >= 0.01:
            # For values >= 0.01%, round to 2 decimal places
            rounded = round(percentage, 2)
            decimals = 2
        elif percentage >= 0.0001:
            # For values >= 0.0001%, round to 4 decimal places
            rounded = round(percentage, 4)
            decimals = 4
        elif percentage >= 0.000001:
            # For values >= 0.000001%, round to 6 decimal places
            rounded = round(percentage, 6)
            decimals = 6
        else:
            # For very small values, use max_decimals
            rounded = round(percentage, max_decimals)
            decimals = max_decimals
        
        # Format with appropriate decimals, then remove trailing zeros
        formatted = f"{rounded:.{decimals}f}"
        
        # Remove trailing zeros and decimal point if not needed
        if '.' in formatted:
            formatted = formatted.rstrip('0').rstrip('.')
        
        return f"{formatted}%"
    
    def _detect_pool_type(self, pool_data: Dict[str, Any]) -> str:
        """
        Map API pool type to standardized type.
        
        Args:
            pool_data: Pool data from API
            
        Returns:
            Standardized pool type string
        """
        pool_type = pool_data.get("type") or pool_data.get("poolType", "")
        
        # Normalize types
        type_map = {
            "WEIGHTED": "Weighted",
            "COMPOSABLE_STABLE": "Stable",
            "COMPOSABLESTABLE": "Stable",
            "META_STABLE": "MetaStable",
            "METASTABLE": "MetaStable",
            "STABLE": "Stable",
            "BOOSTED": "Boosted",
            "GYRO": "Gyro",
            "GYROE": "Gyro",
            "FX": "FX",
            "LVR": "LVR",
        }
        return type_map.get(pool_type.upper(), pool_type)
    
    def _extract_static_metrics(self, pool_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract pool properties that don't change over time.
        
        Args:
            pool_data: Pool data from API
            
        Returns:
            Dictionary with static metrics
        """
        pool_type = self._detect_pool_type(pool_data)
        
        # Extract swap fee
        swap_fee = 0.0
        if "swapFee" in pool_data:
            swap_fee_raw = pool_data.get("swapFee", 0)
            swap_fee = float(swap_fee_raw) if swap_fee_raw else 0.0
        elif "dynamicData" in pool_data and "swapFee" in pool_data["dynamicData"]:
            swap_fee_raw = pool_data["dynamicData"].get("swapFee", 0)
            swap_fee = float(swap_fee_raw) if swap_fee_raw else 0.0
        
        # Extract weights for Weighted pools
        token_weights = None
        if pool_type == "Weighted":
            tokens = pool_data.get("allTokens") or pool_data.get("displayTokens") or pool_data.get("tokens", [])
            weights_dict = {}
            for token in tokens:
                symbol = token.get("symbol", "")
                weight = token.get("weight")
                if symbol and weight:
                    # Convert weight to percentage (weights are usually 0-1)
                    weight_float = float(weight)
                    if weight_float <= 1.0:
                        weight_float *= 100
                    weights_dict[symbol] = round(weight_float, 2)
            
            if weights_dict:
                token_weights = weights_dict
        
        is_core_pool = pool_data.get("isCore", False)
        
        return {
            "pool_type": pool_type,
            "swap_fee": swap_fee,
            "is_core_pool": is_core_pool,
            "token_weights": token_weights
        }
    
    def _extract_dynamic_metrics(
        self, 
        pool_data: Dict[str, Any],
        snapshot_15d: Dict[str, Any] | None
    ) -> Dict[str, Any]:
        """
        Extract time-dependent metrics with historical comparison.
        
        Args:
            pool_data: Current pool data from API
            snapshot_15d: Snapshot from 15 days ago (if available)
            
        Returns:
            Dictionary with dynamic metrics
        """
        pool_type = self._detect_pool_type(pool_data)
        metrics = {}
        
        # Boosted APR (from aprItems)
        if pool_type == "Boosted":
            apr_items = pool_data.get("dynamicData", {}).get("aprItems", [])
            boosted_items = [a for a in apr_items if a.get("type") == "IB_YIELD"]
            if boosted_items:
                metrics["boosted_apr"] = sum(float(a.get("apr", 0)) for a in boosted_items)
            else:
                metrics["boosted_apr"] = None
            
            metrics["boosted_apr_15d_ago"] = None
        
        # Surge Hook Fees (for Stable Surge pools)
        if "hook" in pool_data and pool_data["hook"]:
            metrics["surge_fees"] = None  # TODO: Implement hook contract queries
            metrics["surge_fees_15d_ago"] = None
        
        # Rebalance count (for Gyro/LVR pools)
        if pool_type in ["Gyro", "LVR"]:
            metrics["rebalance_count_15d"] = None  # TODO: Implement event log parsing
        
        return metrics
    
    def _generate_pool_url(self, pool_data: Dict[str, Any], pool_address: str) -> str:
        """
        Generate the Balancer.fi URL for a pool.
        Format: https://balancer.fi/pools/[blockchain]/[version]/[pool_address]
        
        Args:
            pool_data: Pool data from API (contains _api_version and _blockchain)
            pool_address: Pool address
            
        Returns:
            Full URL to view pool on Balancer.fi
        """
        blockchain = pool_data.get("_blockchain", "ethereum")
        version = pool_data.get("_api_version", "v2")
        
        return f"https://balancer.fi/pools/{blockchain}/{version}/{pool_address.lower()}"
    
    async def calculate_pool_metrics(self, pool_address: str, blockchain: str | None = None) -> PoolMetrics:
        """
        Calculate comprehensive pool metrics comparing current vs 15 days ago.
        
        Args:
            pool_address: Ethereum address of the pool
            blockchain: Optional blockchain name (e.g., "ethereum", "arbitrum", "plasma")
            
        Returns:
            PoolMetrics object with all calculated metrics
        """
        # Get current pool data (will try all chains if not found on specified chain)
        current_pool = await self.api.get_current_pool_data(pool_address, blockchain=blockchain)
        
        # Detect pool version and blockchain (use the blockchain where pool was actually found)
        pool_version = current_pool.get("_api_version", "v2")
        found_blockchain = current_pool.get("_blockchain", blockchain)  # Use blockchain where pool was found
        
        # Get historical snapshots (30 days to ensure we have 15 days ago data and for 30-day average)
        # Use the blockchain where the pool was actually found
        snapshots = await self.api.get_pool_snapshots(
            pool_address, 
            days_back=30,
            pool_version=pool_version,
            blockchain=found_blockchain
        )
        
        # Calculate timestamp for 30 days ago
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        thirty_days_ago_ts = int(thirty_days_ago.timestamp())
        
        # Calculate timestamp for 15 days ago (needed for period metrics calculation)
        fifteen_days_ago = datetime.utcnow() - timedelta(days=15)
        fifteen_days_ago_ts = int(fifteen_days_ago.timestamp())
        
        # Get snapshot by index: Always try index 14 (15th snapshot) first
        # If index 14 doesn't exist (snapshot missing), get the most recent snapshot before index 14
        # Logic: Try index 14, if it doesn't exist (IndexError or list too short), try 13, then 12, etc.
        # Snapshots are assumed to be ordered from oldest (index 0) to newest (index N-1)
        snapshot_15d_ago = None
        if snapshots and len(snapshots) > 0:
            # Try indices from 14 down to 0, stopping at the first available
            target_index = None
            for idx in range(14, -1, -1):  # Try 14, 13, 12, ..., 1, 0
                if idx < len(snapshots):
                    target_index = idx
                    break
            
            if target_index is not None:
                snapshot_15d_ago = snapshots[target_index]
                snapshot_timestamp = snapshot_15d_ago.get("timestamp", 0)
                snapshot_date = datetime.fromtimestamp(int(snapshot_timestamp)).strftime("%Y-%m-%d %H:%M") if snapshot_timestamp else "N/A"
                if target_index == 14:
                    print(f"   📅 Using 15th snapshot (index 14): {snapshot_date}")
                else:
                    print(f"   📅 Index 14 not available, using most recent before index 14 (index {target_index}): {snapshot_date}")
            else:
                print(f"   ⚠️  No snapshots available (list is empty)")
        else:
            print(f"   ⚠️  No snapshots available for comparison")
        
        # Extract current metrics
        dynamic_data = current_pool.get("dynamicData", {})
        tvl_current = float(dynamic_data.get("totalLiquidity", 0))
        
        # Check if we have historical data
        has_historical_data = len(snapshots) > 0
        
        # Get TVL from 15 days ago
        tvl_15d_ago = 0.0
        if snapshot_15d_ago:
            tvl_15d_ago = float(snapshot_15d_ago.get("liquidity", 0))
        elif snapshots:
            # Fallback: use the earliest available snapshot
            tvl_15d_ago = float(snapshots[0].get("liquidity", 0))
        elif pool_version == "v3":
            # V3 pools without historical data: use current as baseline
            print(f"⚠️  No historical snapshots available for V3 pool")
            print(f"   Using current values only - no historical comparison possible")
            tvl_15d_ago = tvl_current
        
        # Calculate TVL change percentage
        tvl_change_percent = 0.0
        if tvl_15d_ago > 0 and has_historical_data:
            tvl_change_percent = ((tvl_current - tvl_15d_ago) / tvl_15d_ago) * 100
        
        # Get volume and fees from 15 days ago for comparison
        volume_15d_ago = 0.0
        fees_15d_ago = 0.0
        if snapshot_15d_ago:
            volume_15d_ago = float(snapshot_15d_ago.get("swapVolume", 0))
            fees_15d_ago = float(snapshot_15d_ago.get("swapFees", 0))
        elif snapshots and has_historical_data:
            # Use earliest snapshot as baseline
            volume_15d_ago = float(snapshots[0].get("swapVolume", 0))
            fees_15d_ago = float(snapshots[0].get("swapFees", 0))
        
        # Calculate volume and fees for the last 15 days
        if has_historical_data:
            volume_15_days, fees_15_days = self._calculate_period_metrics(
                snapshots,
                fifteen_days_ago_ts
            )
        else:
            # No historical data: estimate from 24h data
            print(f"   Estimating 15-day metrics from 24h data")
            volume_24h = float(dynamic_data.get("volume24h", 0))
            fees_24h = float(dynamic_data.get("fees24h", 0))
            volume_15_days = volume_24h * 15
            fees_15_days = fees_24h * 15
        
        # Calculate change percentages
        volume_change_percent = 0.0
        fees_change_percent = 0.0
        
        if has_historical_data and volume_15d_ago > 0 and volume_15_days > 0:
            current_cumulative_volume = 0.0
            if snapshots:
                current_cumulative_volume = float(snapshots[-1].get("swapVolume", 0))
            
            if current_cumulative_volume > volume_15d_ago:
                volume_change_percent = ((current_cumulative_volume - volume_15d_ago) / volume_15d_ago) * 100
        
        if has_historical_data and fees_15d_ago > 0 and fees_15_days > 0:
            # Fees change: similar logic
            current_cumulative_fees = 0.0
            if snapshots:
                current_cumulative_fees = float(snapshots[-1].get("swapFees", 0))
            
            if current_cumulative_fees > fees_15d_ago:
                fees_change_percent = ((current_cumulative_fees - fees_15d_ago) / fees_15d_ago) * 100
        
        # Extract APR
        apr_current = None
        
        if "totalApr" in dynamic_data:
            apr_current = float(dynamic_data.get("totalApr", 0))
        
        if apr_current is None or apr_current == 0:
            apr_items = dynamic_data.get("aprItems", [])
            if apr_items:
                # Sum all APR items for total APR
                total_apr = sum(float(item.get("apr", 0)) for item in apr_items)
                if total_apr > 0:
                    apr_current = total_apr
                else:
                    # Fallback: use first item
                    apr_current = float(apr_items[0].get("apr", 0))
        
        if apr_current is None or apr_current == 0:
            if "apr" in dynamic_data:
                apr_current = float(dynamic_data.get("apr", 0))
        
        if apr_current is None or apr_current == 0:
            if "totalShares" in current_pool:
                if "apr" in current_pool:
                    apr_current = float(current_pool.get("apr", 0))
        
        if (apr_current is None or apr_current == 0) and tvl_current > 0 and fees_15_days > 0:
            # Get daily average from 15-day period
            fees_per_day = fees_15_days / 15
            # Calculate annualized fee APR
            annual_fees = fees_per_day * 365
            apr_current = annual_fees / tvl_current
        
        # Extract static metrics early (needed for swap fee fallback)
        static_metrics = self._extract_static_metrics(current_pool)
        static_swap_fee = static_metrics.get("swap_fee", 0.0)
        
        # Get swap fee rate for ranking: Always use swapFee from dynamicData (comes from get_current_pool_data)
        # This is the configured swap fee parameter, not a calculated value
        volume_fees_ratio_24h = None
        swap_fee_from_api = dynamic_data.get("swapFee")
        
        if swap_fee_from_api is not None:
            # Convert to float, handling both string and numeric types
            if isinstance(swap_fee_from_api, str):
                volume_fees_ratio_24h = float(swap_fee_from_api) if swap_fee_from_api else None
            else:
                volume_fees_ratio_24h = float(swap_fee_from_api) if swap_fee_from_api else None
            
            if volume_fees_ratio_24h is not None:
                print(f"   📈 Swap Fee Rate from get_current_pool_data (swapFee parameter): {volume_fees_ratio_24h:.6f} ({volume_fees_ratio_24h * 100:.4f}%)")
        
        # Note: For ranking, we ONLY use swapFee parameter from get_current_pool_data
        # We don't calculate fees24h/volume24h for ranking - that calculation is only for historical comparison
        # If swapFee is not available from API, use static swap fee as fallback
        if volume_fees_ratio_24h is None:
            if static_swap_fee > 0:
                volume_fees_ratio_24h = static_swap_fee
                print(f"   📈 Using static swap fee from pool config (fallback): {static_swap_fee:.6f} ({static_swap_fee * 100:.4f}%)")
            else:
                print(f"   ⚠️  No swap fee data available (swapFee not in API response and no static config)")
        
        # Calculate 30-day average swap fee rate from snapshots
        volume_fees_ratio_30d_avg = None
        volume_fees_ratio_30d_change = None
        volume_fees_ratio_30d_change_percent = None
        
        if snapshots and volume_fees_ratio_24h is not None:
            # Filter snapshots from last 30 days
            snapshots_30d = [
                s for s in snapshots
                if int(s.get("timestamp", 0)) >= thirty_days_ago_ts
            ]
            
            print(f"\n   🔍 ========== 30-DAY AVERAGE CALCULATION DEBUG ==========")
            print(f"   📅 Total snapshots in last 30 days: {len(snapshots_30d)}")
            print(f"   📊 Current swap fee rate: {volume_fees_ratio_24h:.8f} ({volume_fees_ratio_24h * 100:.6f}%)")
            
            if snapshots_30d:
                # Calculate swap fee rate for each snapshot and sum
                # IMPORTANT: Skip snapshots where volume24h or fees24h are zero
                total_ratio = 0.0
                valid_snapshots = 0
                skipped_snapshots = 0
                
                print(f"\n   📋 Processing each snapshot:")
                for idx, snapshot in enumerate(snapshots_30d, 1):
                    vol_24h = float(snapshot.get("volume24h", 0))
                    fee_24h = float(snapshot.get("fees24h", 0))
                    timestamp = snapshot.get("timestamp", 0)
                    date_str = datetime.fromtimestamp(int(timestamp)).strftime("%Y-%m-%d %H:%M") if timestamp else "N/A"
                    
                    print(f"      Snapshot #{idx} ({date_str}):")
                    print(f"         Volume24h: ${vol_24h:,.2f}")
                    print(f"         Fees24h: ${fee_24h:,.2f}")
                    
                    # Skip snapshots with zero volume or fees (they don't represent valid data)
                    if vol_24h > 0 and fee_24h >= 0:
                        ratio = fee_24h / vol_24h
                        total_ratio += ratio
                        valid_snapshots += 1
                        print(f"         ✅ VALID - Ratio: {ratio:.8f} ({ratio * 100:.6f}%)")
                        print(f"            Running total: {total_ratio:.8f} from {valid_snapshots} snapshots")
                    else:
                        skipped_snapshots += 1
                        reason = "zero volume" if vol_24h == 0 else "zero fees" if fee_24h == 0 else "both zero"
                        print(f"         ❌ SKIPPED - {reason}")
                
                print(f"\n   📊 Summary:")
                print(f"      Valid snapshots: {valid_snapshots}")
                print(f"      Skipped snapshots: {skipped_snapshots}")
                print(f"      Total ratio sum: {total_ratio:.8f}")
                
                # Calculate average only from valid snapshots
                if valid_snapshots > 0:
                    volume_fees_ratio_30d_avg = total_ratio / valid_snapshots
                    print(f"\n   🧮 Average calculation:")
                    print(f"      Average = Total sum / Valid count")
                    print(f"      Average = {total_ratio:.8f} / {valid_snapshots}")
                    print(f"      Average = {volume_fees_ratio_30d_avg:.8f} ({volume_fees_ratio_30d_avg * 100:.6f}%)")
                    
                    # Calculate change from average
                    volume_fees_ratio_30d_change = volume_fees_ratio_24h - volume_fees_ratio_30d_avg
                    
                    print(f"\n   📈 Change calculation:")
                    print(f"      Current rate: {volume_fees_ratio_24h:.8f} ({volume_fees_ratio_24h * 100:.6f}%)")
                    print(f"      30d average: {volume_fees_ratio_30d_avg:.8f} ({volume_fees_ratio_30d_avg * 100:.6f}%)")
                    print(f"      Absolute change: {volume_fees_ratio_30d_change:.8f}")
                    
                    if volume_fees_ratio_30d_avg > 0:
                        volume_fees_ratio_30d_change_percent = (volume_fees_ratio_30d_change / volume_fees_ratio_30d_avg) * 100
                        print(f"      Change % = (Change / Average) * 100")
                        print(f"      Change % = ({volume_fees_ratio_30d_change:.8f} / {volume_fees_ratio_30d_avg:.8f}) * 100")
                        print(f"      Change % = {volume_fees_ratio_30d_change_percent:+.6f}%")
                    else:
                        print(f"      ⚠️  Cannot calculate % change: average is zero")
                else:
                    print(f"   ⚠️  No valid snapshots found for 30-day average (all had zero volume/fees)")
            
            print(f"   ========================================================\n")
        
        # Calculate fees24h/volume24h ratio from snapshot (15th or first available) for comparison
        volume_fees_ratio_24h_15d_ago = None
        volume_fees_ratio_change_percent = None
        
        print(f"\n   🔍 ========== 15-DAY COMPARISON DEBUG ==========")
        print(f"   📊 Current swap fee rate (from get_current_pool_data): {volume_fees_ratio_24h:.8f} ({volume_fees_ratio_24h * 100:.6f}%)" if volume_fees_ratio_24h is not None else "   📊 Current swap fee rate: None")
        
        if snapshot_15d_ago:
            volume_24h_15d = float(snapshot_15d_ago.get("volume24h", 0))
            fees_24h_15d = float(snapshot_15d_ago.get("fees24h", 0))
            timestamp_15d = snapshot_15d_ago.get("timestamp", 0)
            date_str_15d = datetime.fromtimestamp(int(timestamp_15d)).strftime("%Y-%m-%d %H:%M") if timestamp_15d else "N/A"
            
            print(f"   📅 Snapshot date: {date_str_15d}")
            print(f"   💰 Snapshot - Volume24h: ${volume_24h_15d:,.2f}, Fees24h: ${fees_24h_15d:,.2f}")
            
            # Calculate swap fee rate as fees24h/volume24h from snapshot
            if volume_24h_15d > 0:
                volume_fees_ratio_24h_15d_ago = fees_24h_15d / volume_24h_15d
                print(f"   🧮 Snapshot swap fee rate calculation:")
                print(f"      Rate = Fees24h / Volume24h")
                print(f"      Rate = ${fees_24h_15d:,.2f} / ${volume_24h_15d:,.2f}")
                print(f"      Rate = {volume_fees_ratio_24h_15d_ago:.8f} ({volume_fees_ratio_24h_15d_ago * 100:.6f}%)")
            else:
                print(f"   ⚠️  Cannot calculate swap fee rate: volume24h is zero")
                # If we can't calculate from snapshot but have current swapFee, use it for comparison
                # This means no change (both are the same configured swap fee)
                if volume_fees_ratio_24h is not None:
                    volume_fees_ratio_24h_15d_ago = volume_fees_ratio_24h
                    print(f"   📊 Using current swap fee rate for 15d ago (no volume data): {volume_fees_ratio_24h:.8f} ({volume_fees_ratio_24h * 100:.6f}%)")
            
            # Calculate change percentage if we have both values
            if volume_fees_ratio_24h is not None and volume_fees_ratio_24h_15d_ago is not None and volume_fees_ratio_24h_15d_ago > 0:
                volume_fees_ratio_change_percent = ((volume_fees_ratio_24h - volume_fees_ratio_24h_15d_ago) / volume_fees_ratio_24h_15d_ago) * 100
                print(f"\n   📈 Change calculation:")
                print(f"      Current rate (from API): {volume_fees_ratio_24h:.8f} ({volume_fees_ratio_24h * 100:.6f}%)")
                print(f"      Snapshot rate (calculated): {volume_fees_ratio_24h_15d_ago:.8f} ({volume_fees_ratio_24h_15d_ago * 100:.6f}%)")
                print(f"      Absolute change: {volume_fees_ratio_24h - volume_fees_ratio_24h_15d_ago:.8f}")
                print(f"      Change % = ((Current - Snapshot) / Snapshot) * 100")
                print(f"      Change % = (({volume_fees_ratio_24h:.8f} - {volume_fees_ratio_24h_15d_ago:.8f}) / {volume_fees_ratio_24h_15d_ago:.8f}) * 100")
                print(f"      Change % = {volume_fees_ratio_change_percent:+.6f}%")
        else:
            print(f"   ⚠️  No snapshot available for comparison")
        
        print(f"   ========================================================\n")
        
        # Generate Balancer.fi URL
        pool_url = self._generate_pool_url(current_pool, pool_address)
        
        # Extract static metrics (pool properties)
        static_metrics = self._extract_static_metrics(current_pool)
        
        # Determine boosted pool type
        boosted_type = get_boosted_pool_type(current_pool)
        
        # Extract dynamic metrics (time-dependent)
        dynamic_metrics = self._extract_dynamic_metrics(current_pool, snapshot_15d_ago)
        
        # Create and return metrics
        return PoolMetrics(
            tvl_current=tvl_current,
            tvl_15_days_ago=tvl_15d_ago,
            tvl_change_percent=tvl_change_percent,
            volume_15_days=volume_15_days,
            volume_change_percent=volume_change_percent,
            fees_15_days=fees_15_days,
            fees_change_percent=fees_change_percent,
            volume_fees_ratio_24h=volume_fees_ratio_24h,
            volume_fees_ratio_24h_15d_ago=volume_fees_ratio_24h_15d_ago,
            volume_fees_ratio_change_percent=volume_fees_ratio_change_percent,
            volume_fees_ratio_30d_avg=volume_fees_ratio_30d_avg,
            volume_fees_ratio_30d_change=volume_fees_ratio_30d_change,
            volume_fees_ratio_30d_change_percent=volume_fees_ratio_30d_change_percent,
            apr_current=apr_current,
            pool_name=current_pool.get("name", "Unknown Pool"),
            pool_address=pool_address,
            pool_url=pool_url,
            # Static metrics
            pool_type=static_metrics["pool_type"],
            boosted_type=boosted_type,
            swap_fee=static_metrics["swap_fee"],
            is_core_pool=static_metrics["is_core_pool"],
            token_weights=static_metrics["token_weights"],
            # Dynamic metrics
            boosted_apr=dynamic_metrics.get("boosted_apr"),
            boosted_apr_15d_ago=dynamic_metrics.get("boosted_apr_15d_ago"),
            surge_fees=dynamic_metrics.get("surge_fees"),
            surge_fees_15d_ago=dynamic_metrics.get("surge_fees_15d_ago"),
            rebalance_count_15d=dynamic_metrics.get("rebalance_count_15d")
        )
    
    def _calculate_period_metrics(
        self,
        snapshots: list,
        start_timestamp: int
    ) -> tuple[float, float]:
        """
        Calculate cumulative volume and fees for a period.
        
        Args:
            snapshots: List of pool snapshots
            start_timestamp: Start of the period (Unix timestamp)
            
        Returns:
            Tuple of (total_volume, total_fees) for the period
        """
        if not snapshots:
            return 0.0, 0.0
        
        # Filter snapshots within the period
        period_snapshots = [
            s for s in snapshots
            if int(s.get("timestamp", 0)) >= start_timestamp
        ]
        
        if not period_snapshots:
            return 0.0, 0.0
        
        # Sort by timestamp to ensure correct ordering
        period_snapshots.sort(key=lambda x: int(x.get("timestamp", 0)))
        
        # Get the snapshot just before the period starts
        pre_period_snapshots = [
            s for s in snapshots
            if int(s.get("timestamp", 0)) < start_timestamp
        ]
        
        # Calculate cumulative metrics
        if period_snapshots:
            latest_snapshot = period_snapshots[-1]
            earliest_snapshot = period_snapshots[0]
            
            if pre_period_snapshots:
                baseline_snapshot = max(
                    pre_period_snapshots,
                    key=lambda x: int(x.get("timestamp", 0))
                )
                base_volume = float(baseline_snapshot.get("swapVolume", 0))
                base_fees = float(baseline_snapshot.get("swapFees", 0))
            else:
                base_volume = float(earliest_snapshot.get("swapVolume", 0))
                base_fees = float(earliest_snapshot.get("swapFees", 0))
            
            latest_volume = float(latest_snapshot.get("swapVolume", 0))
            latest_fees = float(latest_snapshot.get("swapFees", 0))
            
            total_volume = max(0, latest_volume - base_volume)
            total_fees = max(0, latest_fees - base_fees)
            
            return total_volume, total_fees
        
        return 0.0, 0.0
    
    def format_metrics_for_email(self, metrics: PoolMetrics, pool_data: Dict = None) -> Dict[str, Any]:
        """
        Format metrics into a dictionary suitable for email template rendering.
        
        Args:
            metrics: PoolMetrics object
            pool_data: Raw pool data from API (for token info)
            
        Returns:
            Dictionary with formatted metrics
        """
        # Extract token information if available
        tokens = []
        if pool_data and pool_data.get("allTokens"):
            for token in pool_data["allTokens"][:4]:  # Limit to 4 tokens to keep clean
                symbol = token.get("symbol", "")
                if symbol:  # Only add if symbol exists
                    tokens.append({
                        "symbol": symbol,
                        "address": token.get("address", "")
                    })
        
        # Check if this is a V3 pool without historical data
        is_v3_estimated = (metrics.tvl_change_percent == 0.0 and 
                          metrics.tvl_current == metrics.tvl_15_days_ago and 
                          metrics.tvl_current > 0 and
                          metrics.volume_change_percent == 0.0 and
                          metrics.fees_change_percent == 0.0)
        
        # Format the change percentages - use appropriate precision
        if not is_v3_estimated:
            # Use more decimal places for very small percentages
            if abs(metrics.volume_change_percent) < 0.01:
                volume_change_formatted = f"{metrics.volume_change_percent:+.4f}%"
            elif abs(metrics.volume_change_percent) < 1.0:
                volume_change_formatted = f"{metrics.volume_change_percent:+.3f}%"
            else:
                volume_change_formatted = f"{metrics.volume_change_percent:+.2f}%"
            
            if abs(metrics.fees_change_percent) < 0.01:
                fees_change_formatted = f"{metrics.fees_change_percent:+.4f}%"
            elif abs(metrics.fees_change_percent) < 1.0:
                fees_change_formatted = f"{metrics.fees_change_percent:+.3f}%"
            else:
                fees_change_formatted = f"{metrics.fees_change_percent:+.2f}%"
        else:
            volume_change_formatted = "N/A"
            fees_change_formatted = "N/A"
        
        result = {
            "pool_name": metrics.pool_name,
            "pool_address": metrics.pool_address,
            "pool_url": metrics.pool_url,
            "pool_tokens": tokens,
            "tvl_current": f"${metrics.tvl_current:,.2f}",
            "tvl_15d_ago": f"${metrics.tvl_15_days_ago:,.2f}",
            "tvl_change_percent": f"{metrics.tvl_change_percent:+.2f}%" if not is_v3_estimated else "N/A",
            "tvl_change_positive": metrics.tvl_change_percent >= 0,
            "volume_15d": f"${metrics.volume_15_days:,.2f}" + (" (est.)" if is_v3_estimated else ""),
            "volume_change_percent": volume_change_formatted,
            "volume_change_positive": metrics.volume_change_percent >= 0,
            "fees_15d": f"${metrics.fees_15_days:,.2f}" + (" (est.)" if is_v3_estimated else ""),
            "fees_change_percent": fees_change_formatted,
            "fees_change_positive": metrics.fees_change_percent >= 0,
            "volume_fees_ratio_24h": self._format_adaptive_percentage(metrics.volume_fees_ratio_24h),
            "volume_fees_ratio_24h_15d_ago": self._format_adaptive_percentage(metrics.volume_fees_ratio_24h_15d_ago),
            "volume_fees_ratio_change_percent": f"{metrics.volume_fees_ratio_change_percent:+.2f}%" if metrics.volume_fees_ratio_change_percent is not None else "N/A",
            # Only show alert if there's a significant change (>0.0005% change AND actual difference in values)
            # This prevents false positives from rounding differences (e.g., 0.01% → 0.01% showing as changed)
            # Using 0.00001 (0.001%) as minimum absolute difference to avoid rounding issues
            "volume_fees_ratio_has_changed": (
                metrics.volume_fees_ratio_change_percent is not None and 
                abs(metrics.volume_fees_ratio_change_percent) > 0.0005 and
                metrics.volume_fees_ratio_24h is not None and
                metrics.volume_fees_ratio_24h_15d_ago is not None and
                abs(metrics.volume_fees_ratio_24h - metrics.volume_fees_ratio_24h_15d_ago) > 0.00001  # Actual difference check (0.001%)
            ),
            "volume_fees_ratio_increased": (
                metrics.volume_fees_ratio_change_percent is not None and 
                metrics.volume_fees_ratio_change_percent > 0.0005 and
                metrics.volume_fees_ratio_24h is not None and
                metrics.volume_fees_ratio_24h_15d_ago is not None and
                (metrics.volume_fees_ratio_24h - metrics.volume_fees_ratio_24h_15d_ago) > 0.00001  # Actual difference check (0.001%)
            ),
            "volume_fees_ratio_decreased": (
                metrics.volume_fees_ratio_change_percent is not None and 
                metrics.volume_fees_ratio_change_percent < -0.0005 and
                metrics.volume_fees_ratio_24h is not None and
                metrics.volume_fees_ratio_24h_15d_ago is not None and
                (metrics.volume_fees_ratio_24h_15d_ago - metrics.volume_fees_ratio_24h) > 0.00001  # Actual difference check (0.001%)
            ),
            "volume_fees_ratio_30d_avg": self._format_adaptive_percentage(metrics.volume_fees_ratio_30d_avg),
            "volume_fees_ratio_30d_change": self._format_adaptive_percentage(metrics.volume_fees_ratio_30d_change),
            "volume_fees_ratio_30d_change_percent": f"{metrics.volume_fees_ratio_30d_change_percent:+.2f}%" if metrics.volume_fees_ratio_30d_change_percent is not None else "N/A",
            # Only show alert if change is significant (>1% change AND absolute difference > 0.0001%)
            "volume_fees_ratio_30d_has_changed": (
                metrics.volume_fees_ratio_30d_change_percent is not None and 
                abs(metrics.volume_fees_ratio_30d_change_percent) > 1.0 and
                metrics.volume_fees_ratio_24h is not None and
                metrics.volume_fees_ratio_30d_avg is not None and
                abs(metrics.volume_fees_ratio_24h - metrics.volume_fees_ratio_30d_avg) > 0.000001
            ),
            "volume_fees_ratio_30d_increased": (
                metrics.volume_fees_ratio_30d_change_percent is not None and 
                metrics.volume_fees_ratio_30d_change_percent > 1.0 and
                metrics.volume_fees_ratio_24h is not None and
                metrics.volume_fees_ratio_30d_avg is not None and
                (metrics.volume_fees_ratio_24h - metrics.volume_fees_ratio_30d_avg) > 0.000001
            ),
            "volume_fees_ratio_30d_decreased": (
                metrics.volume_fees_ratio_30d_change_percent is not None and 
                metrics.volume_fees_ratio_30d_change_percent < -1.0 and
                metrics.volume_fees_ratio_24h is not None and
                metrics.volume_fees_ratio_30d_avg is not None and
                (metrics.volume_fees_ratio_30d_avg - metrics.volume_fees_ratio_24h) > 0.000001
            ),
            "apr_current": f"{metrics.apr_current * 100:.2f}%" if metrics.apr_current else "N/A",
            # Static metrics
            "pool_type": metrics.pool_type,
            "swap_fee": self._format_adaptive_percentage(metrics.swap_fee) if metrics.swap_fee > 0 else "N/A",
            "is_core_pool": metrics.is_core_pool,
            "token_weights": metrics.token_weights,
            # Dynamic metrics
            "boosted_apr": f"{metrics.boosted_apr * 100:.2f}%" if metrics.boosted_apr else None,
            "boosted_apr_15d_ago": f"{metrics.boosted_apr_15d_ago * 100:.2f}%" if metrics.boosted_apr_15d_ago else None,
            "surge_fees": f"${metrics.surge_fees:,.2f}" if metrics.surge_fees else None,
            "surge_fees_15d_ago": f"${metrics.surge_fees_15d_ago:,.2f}" if metrics.surge_fees_15d_ago else None,
            "rebalance_count_15d": metrics.rebalance_count_15d,
            "is_v3_estimated": is_v3_estimated,
            "timestamp": datetime.utcnow().strftime("%B %d, %Y at %H:%M UTC")
        }
        
        return result
    
    async def calculate_multi_pool_metrics(
        self, 
        pool_addresses: list[str],
        ranking_by: list[str] | None = None
    ) -> MultiPoolMetrics:
        """
        Calculate metrics for multiple pools and rank them.
        
        Args:
            pool_addresses: List of pool addresses
            ranking_by: List of ranking metrics to include (e.g., ["swap_fee", "boosted_apr"])
            
        Returns:
            MultiPoolMetrics with rankings and totals
        """
        if ranking_by is None:
            ranking_by = []
        # Calculate metrics for each pool
        pools_metrics = []
        for address in pool_addresses:
            try:
                metrics = await self.calculate_pool_metrics(address)
                pools_metrics.append(metrics)
                swap_fee_info = f" (swap fee: {self._format_adaptive_percentage(metrics.volume_fees_ratio_24h)})" if metrics.volume_fees_ratio_24h else " (no swap fee data)"
                print(f"✅ Calculated metrics for {metrics.pool_name}{swap_fee_info}")
            except Exception as e:
                print(f"⚠️  Skipping pool {address}: {str(e)}")
                continue
        
        if not pools_metrics:
            raise ValueError("No valid pool metrics could be calculated")
        
        # Rank by TVL increase (absolute change from 15 days ago)
        sorted_by_tvl_increase = sorted(
            pools_metrics,
            key=lambda p: p.tvl_current - p.tvl_15_days_ago,
            reverse=True
        )[:3]
        top_3_tvl = [
            (
                p.pool_name, 
                p.tvl_current - p.tvl_15_days_ago,  # Absolute increase
                p.tvl_change_percent,  # Percentage change
                p.pool_url  # URL to view pool
            )
            for p in sorted_by_tvl_increase
        ]
        
        # Rank by volume (descending) - showing total volume and percentage of portfolio
        total_volume = sum(p.volume_15_days for p in pools_metrics)
        sorted_by_volume = sorted(
            pools_metrics, 
            key=lambda p: p.volume_15_days, 
            reverse=True
        )[:3]
        top_3_volume = [
            (
                p.pool_name, 
                p.volume_15_days,
                (p.volume_15_days / total_volume * 100) if total_volume > 0 else 0,  # Percentage of total
                p.pool_url  # URL to view pool
            )
            for p in sorted_by_volume
        ]
        
        # Rank by swap fee rate (fees24h/volume24h) - showing current rate and change
        pools_with_ratio = [p for p in pools_metrics if p.volume_fees_ratio_24h is not None]
        print(f"   📊 Pools with swap fee rate: {len(pools_with_ratio)}/{len(pools_metrics)}")
        
        if pools_with_ratio:
            sorted_by_swap_fee = sorted(
                pools_with_ratio,
                key=lambda p: p.volume_fees_ratio_24h or 0,
                reverse=True
            )[:3]
            
            print(f"\n   🔍 ========== TOP 3 SWAP FEE RATE DEBUG ==========")
            top_3_swap_fee = []
            for idx, p in enumerate(sorted_by_swap_fee, 1):
                print(f"\n   Pool #{idx}: {p.pool_name}")
                print(f"      Current swap fee rate: {p.volume_fees_ratio_24h:.8f} ({p.volume_fees_ratio_24h * 100:.6f}%)" if p.volume_fees_ratio_24h else "      Current swap fee rate: None")
                print(f"      15d change %: {p.volume_fees_ratio_change_percent:+.6f}%" if p.volume_fees_ratio_change_percent is not None else "      15d change %: None")
                print(f"      30d change %: {p.volume_fees_ratio_30d_change_percent:+.6f}%" if p.volume_fees_ratio_30d_change_percent is not None else "      30d change %: None")
                print(f"      Using for ranking: 15d change = {p.volume_fees_ratio_change_percent:+.6f}%" if p.volume_fees_ratio_change_percent is not None else "      Using for ranking: 15d change = None")
                
                # Check if swap fee changed significantly
                has_changed = (
                    p.volume_fees_ratio_change_percent is not None and 
                    abs(p.volume_fees_ratio_change_percent) > 0.0005 and
                    p.volume_fees_ratio_24h is not None and
                    p.volume_fees_ratio_24h_15d_ago is not None
                )
                
                top_3_swap_fee.append((
                    p.pool_name,
                    p.volume_fees_ratio_24h,
                    p.volume_fees_ratio_change_percent,  # Change percentage (15d)
                    p.pool_url,
                    has_changed,  # Whether swap fee changed significantly
                    p.volume_fees_ratio_24h_15d_ago  # 15d ago value for comparison
                ))
            print(f"   ========================================================\n")
        else:
            top_3_swap_fee = []
            print(f"   ⚠️  No pools with valid swap fee rate found")
        
        # Calculate totals
        total_fees = sum(p.fees_15_days for p in pools_metrics)
        
        # Calculate weighted average APR (by TVL)
        total_tvl = sum(p.tvl_current for p in pools_metrics)
        weighted_apr = 0.0
        if total_tvl > 0:
            for p in pools_metrics:
                if p.apr_current:
                    weight = p.tvl_current / total_tvl
                    weighted_apr += p.apr_current * weight
        
        # Generate custom rankings based on ranking_by parameter
        custom_rankings = {}
        
        if "swap_fee" in ranking_by:
            sorted_by_fee = sorted(pools_metrics, key=lambda p: p.swap_fee, reverse=True)[:3]
            custom_rankings["swap_fee"] = [
                (p.pool_name, p.swap_fee, p.pool_url) for p in sorted_by_fee
            ]
        
        if "rebalance_count" in ranking_by:
            # Filter pools that have rebalance data
            rebalanceable = [p for p in pools_metrics if p.rebalance_count_15d is not None]
            if rebalanceable:
                sorted_by_rebalance = sorted(
                    rebalanceable, 
                    key=lambda p: p.rebalance_count_15d, 
                    reverse=True
                )[:3]
                custom_rankings["rebalance_count"] = [
                    (p.pool_name, p.rebalance_count_15d, p.pool_url) for p in sorted_by_rebalance
                ]
        
        if "boosted_apr" in ranking_by:
            # Filter pools that have boosted APR
            boosted = [p for p in pools_metrics if p.boosted_apr is not None]
            if boosted:
                sorted_by_boosted = sorted(boosted, key=lambda p: p.boosted_apr, reverse=True)[:3]
                custom_rankings["boosted_apr"] = [
                    (p.pool_name, p.boosted_apr, p.pool_url) for p in sorted_by_boosted
                ]
        
        return MultiPoolMetrics(
            pools=pools_metrics,
            top_3_by_volume=top_3_volume,
            top_3_by_tvl=top_3_tvl,
            top_3_by_swap_fee=top_3_swap_fee,
            custom_rankings=custom_rankings,
            total_fees=total_fees,
            total_apr=weighted_apr
        )
    
    def format_multi_pool_metrics_for_email(self, metrics: MultiPoolMetrics) -> Dict[str, Any]:
        """
        Format multi-pool metrics for email template.
        Organized by pool (not by metric).
        
        Args:
            metrics: MultiPoolMetrics object
            
        Returns:
            Dictionary with formatted data organized by pool
        """
        # Format each pool with all its metrics
        pools_data = []
        for pool in metrics.pools:
            pool_data = {
                "name": pool.pool_name,
                "url": pool.pool_url,
                "tvl": f"${pool.tvl_current:,.2f}",
                "tvl_change": f"{pool.tvl_change_percent:+.1f}%",
                "volume": f"${pool.volume_15_days:,.2f}",
                "volume_change": f"{pool.volume_change_percent:+.1f}%",
                "apr": f"{pool.apr_current * 100:.2f}%" if pool.apr_current else "N/A",
                "swap_fee": self._format_adaptive_percentage(pool.volume_fees_ratio_24h) if pool.volume_fees_ratio_24h is not None else "N/A",
                "swap_fee_changed": (
                    pool.volume_fees_ratio_change_percent is not None and 
                    abs(pool.volume_fees_ratio_change_percent) > 0.0005 and
                    pool.volume_fees_ratio_24h is not None and
                    pool.volume_fees_ratio_24h_15d_ago is not None and
                    abs(pool.volume_fees_ratio_24h - pool.volume_fees_ratio_24h_15d_ago) > 0.00001
                ),
                "swap_fee_change": f"{pool.volume_fees_ratio_change_percent:+.2f}%" if pool.volume_fees_ratio_change_percent is not None else None,
                "swap_fee_15d_ago": self._format_adaptive_percentage(pool.volume_fees_ratio_24h_15d_ago) if pool.volume_fees_ratio_24h_15d_ago is not None else None,
            }
            pools_data.append(pool_data)
        
        return {
            "pool_count": len(metrics.pools),
            "pools": pools_data,  # List of pools with all metrics
            # Keep top_3_swap_fee for backward compatibility (used for alerts)
            "top_3_swap_fee": [
                {
                    "name": item[0],
                    "value": self._format_adaptive_percentage(item[1]),
                    "change": f"{item[2]:+.2f}%" if item[2] is not None else "N/A",
                    "rank": idx + 1,
                    "url": item[3],
                    "has_changed": item[4] if len(item) > 4 else False,
                    "value_15d_ago": self._format_adaptive_percentage(item[5]) if len(item) > 5 and item[5] is not None else "N/A"
                }
                for idx, item in enumerate(metrics.top_3_by_swap_fee)
            ] if metrics.top_3_by_swap_fee else [],
            "total_fees": f"${metrics.total_fees:,.2f}",
            "total_apr": f"{metrics.total_apr * 100:.2f}%" if metrics.total_apr > 0 else "N/A",
            "custom_rankings": metrics.custom_rankings,
            "timestamp": datetime.utcnow().strftime("%B %d, %Y at %H:%M UTC")
        }
