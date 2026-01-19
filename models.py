"""
Pydantic models for request/response validation.
"""
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, EmailStr, Field


class RankingMetric(str, Enum):
    """Metrics available for ranking pools in multi-pool reports."""
    
    VOLUME = "volume"
    TVL_GROWTH = "tvl_growth"
    SWAP_FEE = "swap_fee"
    REBALANCE_COUNT = "rebalance_count"
    BOOSTED_APR = "boosted_apr"


class ReportRequest(BaseModel):
    """Request model for generating a pool report (single or multiple pools)."""
    
    pool_addresses: list[str] = Field(
        ...,
        description="List of Ethereum addresses of Balancer pools (1 or more)",
        examples=[["0x3de27efa2f1aa663ae5d458857e731c129069f29"]],
        min_length=1
    )
    recipient_email: EmailStr = Field(
        ...,
        description="Email address to send the report to",
        examples=["user@example.com"]
    )
    ranking_by: list[RankingMetric] | None = Field(
        default=[RankingMetric.VOLUME, RankingMetric.TVL_GROWTH],
        description="Metrics to rank pools by (for multi-pool reports)"
    )
    
    # For backwards compatibility, also accept single pool_address
    @classmethod
    def model_validate(cls, obj):
        # If old format with pool_address, convert to pool_addresses
        if isinstance(obj, dict) and "pool_address" in obj and "pool_addresses" not in obj:
            obj["pool_addresses"] = [obj.pop("pool_address")]
        return super().model_validate(obj)


class ReportResponse(BaseModel):
    """Response model after report generation."""
    
    status: str = Field(
        ...,
        description="Status of the report generation",
        examples=["sent"]
    )
    timestamp: datetime = Field(
        ...,
        description="Timestamp when the report was generated"
    )
    pool_name: str = Field(
        ...,
        description="Name of the pool from Balancer"
    )
    pool_address: str = Field(
        ...,
        description="Address of the pool that was analyzed"
    )


class HealthResponse(BaseModel):
    """Response model for health check endpoint."""
    
    status: str = Field(
        default="healthy",
        description="Health status of the service"
    )
    timestamp: datetime = Field(
        ...,
        description="Current server timestamp"
    )


class PoolMetrics(BaseModel):
    """Model for pool performance metrics."""
    
    tvl_current: float
    tvl_15_days_ago: float
    tvl_change_percent: float
    
    volume_15_days: float
    volume_change_percent: float
    fees_15_days: float
    fees_change_percent: float
    
    apr_current: float | None = None
    
    pool_name: str
    pool_address: str
    pool_url: str | None = None  
    
    # Static metrics
    pool_type: str  
    swap_fee: float 
    is_core_pool: bool = False
    
    # Pool-type specific (Optional)
    token_weights: dict[str, float] | None = None  
    boosted_apr: float | None = None  # Boosted only
    boosted_apr_15d_ago: float | None = None
    surge_fees: float | None = None  # Surge only
    surge_fees_15d_ago: float | None = None
    rebalance_count_15d: int | None = None  # Gyro/LVR only


class MultiPoolMetrics(BaseModel):
    """Model for multiple pools comparison metrics."""
    
    pools: list[PoolMetrics]
    
    # Rankings
    top_3_by_volume: list[tuple[str, float, float, str | None]]  # (pool_name, volume, percentage_of_total, pool_url)
    top_3_by_tvl: list[tuple[str, float, float, str | None]]     # (pool_name, tvl_increase, percentage_change, pool_url)
    
    # Custom configurable rankings
    custom_rankings: dict[str, list[tuple[str, float, str | None]]] = {}  # {metric_name: [(pool_name, value, pool_url)]}
    
    # Totals
    total_fees: float
    total_apr: float