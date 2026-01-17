"""
Pydantic models for request/response validation.
"""
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


class ReportRequest(BaseModel):
    """Request model for generating a pool report."""
    
    pool_address: str = Field(
        ...,
        description="Ethereum address of the Balancer pool",
        pattern="^0x[a-fA-F0-9]{40}$",
        examples=["0x3de27efa2f1aa663ae5d458857e731c129069f29"]
    )
    recipient_email: EmailStr = Field(
        ...,
        description="Email address to send the report to",
        examples=["user@example.com"]
    )


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
    fees_15_days: float
    
    apr_current: float | None = None
    
    pool_name: str
    pool_address: str
