"""
FastAPI application for Balancer Pool Performance Reporter.
Generates and emails performance reports for Balancer pools.
"""
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from datetime import datetime
from contextlib import asynccontextmanager

from models import ReportRequest, ReportResponse, HealthResponse
from services.metrics_calculator import MetricsCalculator
from services.email_sender import EmailSender
from services.balancer_api import BalancerAPIError
from services.telegram_sender import TelegramSender
from config import settings


# Lifespan context manager for startup/shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for the FastAPI app."""
    # Startup
    print("🚀 Starting Balancer Pool Reporter API...")
    print(f"📊 Balancer V3 API: {settings.balancer_v3_api}")
    print(f"📈 Balancer V2 Subgraph: {settings.balancer_v2_subgraph}")
    print(f"📧 Email from: {settings.from_email}")
    yield
    # Shutdown
    print("👋 Shutting down Balancer Pool Reporter API...")


# Initialize FastAPI app
app = FastAPI(
    title="Balancer Pool Reporter",
    description="Generate and email performance reports for Balancer v2/v3 liquidity pools",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Balancer Pool Reporter",
        "version": "1.0.0",
        "description": "Generate and email performance reports for Balancer pools",
        "endpoints": {
            "health": "/health",
            "report": "/report (POST)",
            "docs": "/docs",
            "redoc": "/redoc"
        }
    }


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    Health check endpoint.
    Returns the current status and timestamp of the service.
    """
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow()
    )


@app.post(
    "/report",
    response_model=ReportResponse,
    status_code=status.HTTP_200_OK,
    tags=["Reports"],
    summary="Generate and send pool performance report",
    description="""
    Generate a comprehensive performance report for a Balancer pool and send it via email.
    
    The report includes:
    - Total Value Locked (TVL) comparison with 15 days ago
    - Volume and fees over the last 15 days
    - Current APR
    
    The report is sent as a beautifully styled HTML email matching balancer.fi design.
    """
)
async def generate_report(request: ReportRequest):
    """
    Generate and send a pool performance report via Email.
    - Single pool: Email report (and Telegram card as an extra channel)
    - Multi-pool: Email summary report
    
    Args:
        request: ReportRequest containing pool_addresses (list) and recipient_email
        
    Returns:
        ReportResponse with status, timestamp, and pool information
        
    Raises:
        HTTPException: If report generation or sending fails
    """
    try:
        # Initialize services
        calculator = MetricsCalculator()
        email_sender = EmailSender()
        telegram_sender = TelegramSender()  # Used as an additional channel for single-pool
        
        # Determine if single or multiple pools
        is_multi_pool = len(request.pool_addresses) > 1
        
        if is_multi_pool:
            # ---------------------------------------------------------
            # MULTI-POOL: Email summary report
            # ---------------------------------------------------------
            print(f"📊 Generating comparison report for {len(request.pool_addresses)} pools...")
            
            # Calculate metrics for all pools
            print("🔍 Fetching data for all pools...")
            multi_metrics = await calculator.calculate_multi_pool_metrics(request.pool_addresses)
            
            print(f"✅ Metrics calculated for {len(multi_metrics.pools)} pools")
            print(f"   Total Fees: ${multi_metrics.total_fees:,.2f}")
            print(f"   Weighted APR: {multi_metrics.total_apr * 100:.2f}%")
            
            # Format metrics for email
            metrics_data = calculator.format_multi_pool_metrics_for_email(multi_metrics)
            
            # Send email
            print(f"📧 Sending comparison report to {request.recipient_email}...")
            await email_sender.send_pool_report(
                recipient_email=request.recipient_email,
                pool_name=f"{len(multi_metrics.pools)} Pools",
                metrics_data=metrics_data,
                multi_pool=True
            )
            
            print(f"✅ Comparison report sent successfully!")

            # Also send Telegram card (secondary channel)
            print("✈️ Sending Telegram multi-pool Card to Chat ID...")
            await telegram_sender.send_multi_pool_report(metrics_data=metrics_data)
            print("✅ Telegram multi-pool report sent successfully!")
            
            return ReportResponse(
                status="sent",
                timestamp=datetime.utcnow(),
                pool_name=f"Comparison of {len(multi_metrics.pools)} Pools",
                pool_address=", ".join(request.pool_addresses[:3]) + ("..." if len(request.pool_addresses) > 3 else "")
            )
        
        else:
            # ---------------------------------------------------------
            # SINGLE POOL: Email report + Telegram card
            # ---------------------------------------------------------
            pool_address = request.pool_addresses[0]
            print(f"📊 Generating report for pool: {pool_address}")
            
            # Calculate metrics
            print("🔍 Fetching pool data and calculating metrics...")
            metrics = await calculator.calculate_pool_metrics(pool_address)
            
            print(f"✅ Metrics calculated for {metrics.pool_name}")
            print(f"   TVL: ${metrics.tvl_current:,.2f} ({metrics.tvl_change_percent:+.2f}%)")
            print(f"   Volume (15d): ${metrics.volume_15_days:,.2f}")
            print(f"   Fees (15d): ${metrics.fees_15_days:,.2f}")
            
            # Get pool data for token info
            pool_data = await calculator.api.get_current_pool_data(pool_address)
            
            # Format metrics dictionary
            metrics_data = calculator.format_metrics_for_email(metrics, pool_data)

            # Extract Metadata
            pool_id = pool_data.get("id", pool_address)
            blockchain = pool_data.get("_blockchain", "ethereum")
            version = pool_data.get("_api_version", "v2")
            
            # Construct URL and Timestamp
            pool_url_link = f"https://balancer.fi/pools/{blockchain}/{version}/{pool_id}"
            current_time = datetime.utcnow().strftime("%B %d, %Y at %H:%M UTC")
            
            # Inject data for the Telegram Card & Markdown
            metrics_data["pool_id"] = pool_id
            metrics_data["pool_url"] = pool_url_link
            metrics_data["timestamp"] = current_time
            
            # Send EMAIL report (primary channel)
            print(f"📧 Sending email report to {request.recipient_email}...")
            await email_sender.send_pool_report(
                recipient_email=request.recipient_email,
                pool_name=metrics.pool_name,
                metrics_data=metrics_data,
                multi_pool=False
            )
            print(f"✅ Email report sent successfully!")

            # Optionally, also send Telegram card (secondary channel)
            print(f"✈️ Sending Telegram Card to Chat ID...")
            await telegram_sender.send_pool_report(
                pool_data=pool_data,
                metrics_data=metrics_data
            )
            print(f"✅ Telegram report sent successfully!")
            
            return ReportResponse(
                status="sent",
                timestamp=datetime.utcnow(),
                pool_name=metrics.pool_name,
                pool_address=pool_address
            )
        
    except BalancerAPIError as e:
        print(f"❌ Balancer API error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error fetching data from Balancer API: {str(e)}"
        )
    
    except Exception as e:
        print(f"❌ Error generating report: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating report: {str(e)}"
        )


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler for unhandled exceptions."""
    print(f"❌ Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An unexpected error occurred. Please try again later.",
            "error": str(exc)
        }
    )


if __name__ == "__main__":
    import uvicorn
    
    print("🚀 Starting Balancer Pool Reporter...")
    print("📚 API documentation available at: http://localhost:8000/docs")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
