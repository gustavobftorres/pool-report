"""
Metrics calculator service for comparing pool performance.
Analyzes current metrics vs 15 days ago.
"""
from datetime import datetime, timedelta
from typing import Dict, Any
from services.balancer_api import BalancerAPI
from models import PoolMetrics, MultiPoolMetrics


class MetricsCalculator:
    """Service for calculating and comparing pool metrics."""
    
    def __init__(self):
        self.api = BalancerAPI()
    
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
        # Get current pool data
        current_pool = await self.api.get_current_pool_data(pool_address, blockchain=blockchain)
        
        # Detect pool version
        pool_version = current_pool.get("_api_version", "v2")
        
        # Get historical snapshots (30 days to ensure we have 15 days ago data)
        snapshots = await self.api.get_pool_snapshots(
            pool_address, 
            days_back=30,
            pool_version=pool_version,
            blockchain=blockchain
        )
        
        # Calculate timestamp for 15 days ago
        fifteen_days_ago = datetime.utcnow() - timedelta(days=15)
        fifteen_days_ago_ts = int(fifteen_days_ago.timestamp())
        
        # Get snapshot from 15 days ago
        snapshot_15d_ago = await self.api.get_snapshot_at_timestamp(
            pool_address,
            fifteen_days_ago_ts,
            pool_version=pool_version,
            blockchain=blockchain
        )
        
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
        
        # Generate Balancer.fi URL
        pool_url = self._generate_pool_url(current_pool, pool_address)
        
        # Extract static metrics (pool properties)
        static_metrics = self._extract_static_metrics(current_pool)
        
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
            apr_current=apr_current,
            pool_name=current_pool.get("name", "Unknown Pool"),
            pool_address=pool_address,
            pool_url=pool_url,
            # Static metrics
            pool_type=static_metrics["pool_type"],
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
            "apr_current": f"{metrics.apr_current * 100:.2f}%" if metrics.apr_current else "N/A",
            # Static metrics
            "pool_type": metrics.pool_type,
            "swap_fee": f"{metrics.swap_fee * 100:.4f}%" if metrics.swap_fee > 0 else "N/A",
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
                print(f"✅ Calculated metrics for {metrics.pool_name}")
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
            custom_rankings=custom_rankings,
            total_fees=total_fees,
            total_apr=weighted_apr
        )
    
    def format_multi_pool_metrics_for_email(self, metrics: MultiPoolMetrics) -> Dict[str, Any]:
        """
        Format multi-pool metrics for email template.
        
        Args:
            metrics: MultiPoolMetrics object
            
        Returns:
            Dictionary with formatted data
        """
        return {
            "pool_count": len(metrics.pools),
            "top_3_volume": [
                {
                    "name": name,
                    "value": f"${volume:,.2f}",
                    "percentage": f"{percentage:.1f}%",
                    "rank": idx + 1,
                    "url": url
                }
                for idx, (name, volume, percentage, url) in enumerate(metrics.top_3_by_volume)
            ],
            "top_3_tvl": [
                {
                    "name": name,
                    "value": f"${tvl_increase:,.2f}",
                    "percentage": f"{percentage:+.1f}%",
                    "rank": idx + 1,
                    "url": url
                }
                for idx, (name, tvl_increase, percentage, url) in enumerate(metrics.top_3_by_tvl)
            ],
            "total_fees": f"${metrics.total_fees:,.2f}",
            "total_apr": f"{metrics.total_apr * 100:.2f}%" if metrics.total_apr > 0 else "N/A",
            "custom_rankings": metrics.custom_rankings,
            "timestamp": datetime.utcnow().strftime("%B %d, %Y at %H:%M UTC")
        }
