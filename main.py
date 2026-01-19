"""
FastAPI application for Balancer Pool Performance Reporter.
Generates and emails performance reports for Balancer pools.
"""
from fastapi import FastAPI, HTTPException, status, Request, Depends
from fastapi.responses import JSONResponse
from datetime import datetime
from contextlib import asynccontextmanager
import httpx
from sqlalchemy.orm import Session

from models import ReportRequest, ReportResponse, HealthResponse
from services.metrics_calculator import MetricsCalculator
from services.email_sender import EmailSender
from services.balancer_api import BalancerAPIError
from services.telegram_sender import TelegramSender
from config import settings
from database import get_db, User, UserPool


# Lifespan context manager for startup/shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for the FastAPI app."""
    # Startup
    print("🚀 Starting Balancer Pool Reporter API...")
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
            "telegram_webhook": "/telegram/webhook (POST)",
            "telegram_setup": "/telegram/setup-webhook (POST)",
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


@app.post("/telegram/webhook", tags=["Telegram"])
async def telegram_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Webhook endpoint for Telegram bot updates.
    Handles commands like /start and /myid to help users discover their chat ID.
    Also saves user information to the database for admin management.
    """
    try:
        data = await request.json()
        
        # Extract message and chat info
        if "message" in data:
            message = data["message"]
            chat_id = message["chat"]["id"]
            text = message.get("text", "")
            
            # Extract user info
            from_user = message.get("from", {})
            user_id = from_user.get("id")
            username = from_user.get("username")
            first_name = from_user.get("first_name", "")
            last_name = from_user.get("last_name")
            
            # Save or update user in database
            user = db.query(User).filter(User.user_id == user_id).first()
            if user:
                # Update existing user
                user.last_seen = datetime.utcnow()
                user.username = username
                user.first_name = first_name
                user.last_name = last_name
            else:
                # Create new user
                user = User(
                    user_id=user_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name
                )
                db.add(user)
            db.commit()
            print(f"✅ User {user_id} ({first_name}) saved/updated in database")
            
            # Handle /start command
            if text == "/start":
                telegram_sender = TelegramSender()
                response_text = (
                    f"👋 Welcome {first_name}!\n\n"
                    f"✅ *Your Telegram User ID:* `{user_id}`\n\n"
                    f"Your account is registered. An admin will assign pools to you.\n"
                    f"Once pools are assigned, you can request reports!\n\n"
                    f"*Example request:*\n"
                    f"```json\n"
                    f'{{\n'
                    f'  "user_id": {user_id},\n'
                    f'  "recipient_email": "you@example.com"\n'
                    f'}}\n'
                    f"```"
                )
                
                # Send response via Telegram API
                await telegram_sender.send_message(str(chat_id), response_text)
                print(f"✅ Sent welcome message to user {user_id}")
            
            # Handle /myid command
            elif text == "/myid":
                telegram_sender = TelegramSender()
                pool_count = len(user.pools) if user else 0
                response_text = (
                    f"✅ *Your Telegram User ID:* `{user_id}`\n\n"
                    f"📊 *Assigned Pools:* {pool_count}\n\n"
                    f"Use this ID in your API requests to receive pool reports."
                )
                
                await telegram_sender.send_message(str(chat_id), response_text)
                print(f"✅ Sent user ID to {user_id}")
        
        return {"ok": True}
    
    except Exception as e:
        print(f"❌ Error in telegram webhook: {str(e)}")
        return {"ok": False, "error": str(e)}


@app.post("/telegram/setup-webhook", tags=["Telegram"])
async def setup_telegram_webhook(webhook_url: str):
    """
    Configure Telegram bot webhook URL.
    Call this once to register your webhook endpoint with Telegram.
    
    Example: POST /telegram/setup-webhook?webhook_url=https://your-domain.com/telegram/webhook
    """
    try:
        telegram_api = f"https://api.telegram.org/bot{settings.telegram_bot_token}/setWebhook"
        async with httpx.AsyncClient() as client:
            response = await client.post(telegram_api, json={"url": webhook_url})
            result = response.json()
            
            if result.get("ok"):
                print(f"✅ Webhook configured: {webhook_url}")
                return {"status": "success", "webhook_url": webhook_url, "response": result}
            else:
                print(f"❌ Failed to configure webhook: {result}")
                return {"status": "failed", "response": result}
    
    except Exception as e:
        print(f"❌ Error setting up webhook: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error setting up webhook: {str(e)}"
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
    
    Supports two modes:
    1. Direct pool addresses: Provide pool_addresses array
    2. User lookup: Provide user_id to automatically use assigned pools
    """
)
async def generate_report(request: ReportRequest, db: Session = Depends(get_db)):
    """
    Generate and send a pool performance report via Email.
    - Single pool: Email report (and Telegram card as an extra channel)
    - Multi-pool: Email summary report
    
    Args:
        request: ReportRequest containing either pool_addresses or user_id
        db: Database session (injected)
        
    Returns:
        ReportResponse with status, timestamp, and pool information
        
    Raises:
        HTTPException: If report generation or sending fails
    """
    try:
        # Determine pool addresses (either from request or user lookup)
        if request.user_id:
            # Look up user's pools from database
            print(f"🔍 Looking up pools for user {request.user_id}...")
            user_pools = db.query(UserPool).filter(
                UserPool.user_id == request.user_id
            ).all()
            
            if not user_pools:
                raise HTTPException(
                    status_code=404,
                    detail=f"No pools assigned to user {request.user_id}. Please contact admin to assign pools."
                )
            
            pool_addresses = [up.pool_address for up in user_pools]
            print(f"✅ Found {len(pool_addresses)} pool(s) for user {request.user_id}")
            
            # Use user's Telegram ID as chat_id if not provided
            if not request.telegram_chat_id:
                request.telegram_chat_id = str(request.user_id)
        else:
            # Use provided pool_addresses (backward compatibility)
            pool_addresses = request.pool_addresses
            print(f"📊 Using {len(pool_addresses)} pool(s) from request")
        
        # Initialize services
        calculator = MetricsCalculator()
        email_sender = EmailSender()
        telegram_sender = TelegramSender()  # Used as an additional channel for single-pool
        
        # Determine if single or multiple pools
        is_multi_pool = len(pool_addresses) > 1
        
        if is_multi_pool:
            # ---------------------------------------------------------
            # MULTI-POOL: Email summary report
            # ---------------------------------------------------------
            print(f"📊 Generating comparison report for {len(pool_addresses)} pools...")
            
            # Calculate metrics for all pools
            print("🔍 Fetching data for all pools...")
            # Convert RankingMetric enums to strings for the calculator
            ranking_by = [metric.value for metric in request.ranking_by] if request.ranking_by else []
            multi_metrics = await calculator.calculate_multi_pool_metrics(
                pool_addresses,
                ranking_by=ranking_by
            )
            
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
            # Use request-level telegram_chat_id if provided, otherwise use env variable
            telegram_chat_id = request.telegram_chat_id or settings.telegram_chat_id
            if telegram_chat_id:
                print(f"✈️ Sending Telegram multi-pool Card to Chat ID: {telegram_chat_id}...")
                await telegram_sender.send_multi_pool_report(
                    metrics_data=metrics_data,
                    chat_id=telegram_chat_id
                )
                print("✅ Telegram multi-pool report sent successfully!")
            
            return ReportResponse(
                status="sent",
                timestamp=datetime.utcnow(),
                pool_name=f"Comparison of {len(multi_metrics.pools)} Pools",
                pool_address=", ".join(pool_addresses[:3]) + ("..." if len(pool_addresses) > 3 else "")
            )
        
        else:
            # ---------------------------------------------------------
            # SINGLE POOL: Email report + Telegram card
            # ---------------------------------------------------------
            pool_address = pool_addresses[0]

            metrics = await calculator.calculate_pool_metrics(pool_address)
            
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
            
            # Send email
            await email_sender.send_pool_report(
                recipient_email=request.recipient_email,
                pool_name=metrics.pool_name,
                metrics_data=metrics_data,
                multi_pool=False
            )
            print(f"✅ Email report sent successfully!")

            # Optionally, also send Telegram card (secondary channel)
            # Use request-level telegram_chat_id if provided, otherwise use env variable
            telegram_chat_id = request.telegram_chat_id or settings.telegram_chat_id
            if telegram_chat_id:
                print(f"✈️ Sending Telegram Card to Chat ID: {telegram_chat_id}...")
                await telegram_sender.send_pool_report(
                    pool_data=pool_data,
                    metrics_data=metrics_data,
                    chat_id=telegram_chat_id
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
