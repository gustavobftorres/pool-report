"""
Metrics calculator service for comparing pool performance.
Analyzes current metrics vs 15 days ago.
"""
from datetime import datetime, timedelta
from typing import Dict, Any
from services.balancer_api import BalancerAPI
from models import PoolMetrics


class MetricsCalculator:
    """Service for calculating and comparing pool metrics."""
    
    def __init__(self):
        self.api = BalancerAPI()
    
    async def calculate_pool_metrics(self, pool_address: str) -> PoolMetrics:
        """
        Calculate comprehensive pool metrics comparing current vs 15 days ago.
        
        Args:
            pool_address: Ethereum address of the pool
            
        Returns:
            PoolMetrics object with all calculated metrics
        """
        # Get current pool data
        current_pool = await self.api.get_current_pool_data(pool_address)
        
        # Get historical snapshots (30 days to ensure we have 15 days ago data)
        snapshots = await self.api.get_pool_snapshots(pool_address, days_back=30)
        
        # Calculate timestamp for 15 days ago
        fifteen_days_ago = datetime.utcnow() - timedelta(days=15)
        fifteen_days_ago_ts = int(fifteen_days_ago.timestamp())
        
        # Get snapshot from 15 days ago
        snapshot_15d_ago = await self.api.get_snapshot_at_timestamp(
            pool_address,
            fifteen_days_ago_ts
        )
        
        # Extract current metrics
        dynamic_data = current_pool.get("dynamicData", {})
        tvl_current = float(dynamic_data.get("totalLiquidity", 0))
        
        # Extract APR (get the first/main APR item)
        apr_items = dynamic_data.get("aprItems", [])
        apr_current = None
        if apr_items:
            # Try to get swap fee APR or total APR
            for item in apr_items:
                if item.get("type") in ["SWAP_FEE", "IB_YIELD"]:
                    apr_current = float(item.get("apr", 0))
                    break
            # If no specific type found, use the first one
            if apr_current is None and apr_items:
                apr_current = float(apr_items[0].get("apr", 0))
        
        # Get TVL from 15 days ago
        tvl_15d_ago = 0.0
        if snapshot_15d_ago:
            tvl_15d_ago = float(snapshot_15d_ago.get("liquidity", 0))
        elif snapshots:
            # Fallback: use the earliest available snapshot
            tvl_15d_ago = float(snapshots[0].get("liquidity", 0))
        
        # Calculate TVL change percentage
        tvl_change_percent = 0.0
        if tvl_15d_ago > 0:
            tvl_change_percent = ((tvl_current - tvl_15d_ago) / tvl_15d_ago) * 100
        
        # Calculate volume and fees for the last 15 days
        volume_15_days, fees_15_days = self._calculate_period_metrics(
            snapshots,
            fifteen_days_ago_ts
        )
        
        # Create and return metrics
        return PoolMetrics(
            tvl_current=tvl_current,
            tvl_15_days_ago=tvl_15d_ago,
            tvl_change_percent=tvl_change_percent,
            volume_15_days=volume_15_days,
            fees_15_days=fees_15_days,
            apr_current=apr_current,
            pool_name=current_pool.get("name", "Unknown Pool"),
            pool_address=pool_address
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
        # Method 1: If we have snapshots with cumulative data
        if period_snapshots:
            latest_snapshot = period_snapshots[-1]
            earliest_snapshot = period_snapshots[0]
            
            # If we have a snapshot before the period, use it as baseline
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
            
            # Calculate the difference (cumulative change)
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
        
        return {
            "pool_name": metrics.pool_name,
            "pool_address": metrics.pool_address,
            "pool_tokens": tokens,
            "tvl_current": f"${metrics.tvl_current:,.2f}",
            "tvl_15d_ago": f"${metrics.tvl_15_days_ago:,.2f}",
            "tvl_change_percent": f"{metrics.tvl_change_percent:+.2f}%",
            "tvl_change_positive": metrics.tvl_change_percent >= 0,
            "volume_15d": f"${metrics.volume_15_days:,.2f}",
            "fees_15d": f"${metrics.fees_15_days:,.2f}",
            "apr_current": f"{metrics.apr_current * 100:.2f}%" if metrics.apr_current else "N/A",
            "timestamp": datetime.utcnow().strftime("%B %d, %Y at %H:%M UTC")
        }
