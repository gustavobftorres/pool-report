"""
FastAPI application for Balancer Pool Performance Reporter.
Generates and emails performance reports for Balancer pools.
"""
from fastapi import FastAPI, HTTPException, status, Request, Depends
from fastapi.responses import JSONResponse
from datetime import datetime
from contextlib import asynccontextmanager
import httpx
import asyncio
from sqlalchemy.orm import Session

from models import ReportRequest, ReportResponse, HealthResponse
from services.metrics_calculator import MetricsCalculator
from services.email_sender import EmailSender, EmailSenderError
from services.balancer_api import BalancerAPIError
from services.telegram_sender import TelegramSender
from config import settings
from database import get_db, AllowedUser, Client, ClientPool


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


@app.get("/test-smtp", tags=["Health"])
async def test_smtp():
    """Test SMTP connection and configuration."""
    import smtplib
    from config import settings
    
    try:
        # Test SMTP connection
        server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10)
        server.set_debuglevel(0)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(settings.smtp_username, settings.smtp_password)
        server.quit()
        
        return {
            "status": "success",
            "message": "SMTP connection successful",
            "smtp_host": settings.smtp_host,
            "smtp_port": settings.smtp_port,
            "smtp_username": settings.smtp_username
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"SMTP connection failed: {str(e)}",
            "smtp_host": settings.smtp_host if settings.smtp_host else "NOT SET",
            "smtp_port": settings.smtp_port if settings.smtp_port else "NOT SET"
        }


@app.post("/telegram/webhook", tags=["Telegram"])
async def telegram_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Webhook endpoint for Telegram bot updates.
    New behavior:
    - /start and /myid: help users discover their Telegram user_id and request whitelist access.
    - Any other text (e.g. \"aave\"): if user is whitelisted, treat it as a client key and send a report back on Telegram.
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

            telegram_sender = TelegramSender()

            def _normalize_client_key(raw: str) -> str:
                return (raw or "").strip().lower()

            async def _send_client_report(target_chat_id: str, client_key: str, pool_addresses: list[str]) -> None:
                """
                Background task: generate report metrics and send to Telegram.
                """
                try:
                    calculator = MetricsCalculator()

                    # Decide single vs multi
                    if len(pool_addresses) == 1:
                        pool_address = pool_addresses[0]
                        metrics = await calculator.calculate_pool_metrics(pool_address)
                        pool_data = await calculator.api.get_current_pool_data(pool_address)
                        metrics_data = calculator.format_metrics_for_email(metrics, pool_data)

                        # Add fields used by Telegram templates/caption
                        pool_id = pool_data.get("id", pool_address)
                        blockchain = pool_data.get("_blockchain", "ethereum")
                        version = pool_data.get("_api_version", "v2")
                        pool_url_link = f"https://balancer.fi/pools/{blockchain}/{version}/{pool_id}"
                        current_time = datetime.utcnow().strftime("%B %d, %Y at %H:%M UTC")

                        metrics_data["pool_id"] = pool_id
                        metrics_data["pool_url"] = pool_url_link
                        metrics_data["timestamp"] = current_time

                        await telegram_sender.send_pool_report(
                            pool_data=pool_data,
                            metrics_data=metrics_data,
                            chat_id=str(target_chat_id),
                            metrics=metrics
                        )
                    else:
                        ranking_by = ["volume", "tvl_growth", "swap_fee"]
                        multi_metrics = await calculator.calculate_multi_pool_metrics(pool_addresses, ranking_by=ranking_by)
                        metrics_data = calculator.format_multi_pool_metrics_for_email(multi_metrics)
                        await telegram_sender.send_multi_pool_report(
                            metrics_data=metrics_data, 
                            chat_id=str(target_chat_id),
                            metrics=multi_metrics
                        )

                except Exception as e:
                    print(f"❌ Error generating Telegram client report for '{client_key}': {str(e)}")
                    await telegram_sender.send_message(
                        str(target_chat_id),
                        f"❌ Failed to generate report for `{client_key}`. Please try again later.",
                    )

            # Commands
            if text == "/start":
                response_text = (
                    f"👋 Welcome {first_name}!\n\n"
                    f"✅ *Your Telegram User ID:* `{user_id}`\n\n"
                    "This bot is restricted.\n"
                    "Ask the admin to whitelist your user ID.\n\n"
                    "Once approved, send a client name like:\n"
                    "`aave`"
                )
                await telegram_sender.send_message(str(chat_id), response_text)
                return {"ok": True}

            if text == "/myid":
                response_text = f"✅ *Your Telegram User ID:* `{user_id}`"
                await telegram_sender.send_message(str(chat_id), response_text)
                return {"ok": True}

            # Client-name request
            client_key = _normalize_client_key(text)
            if not client_key:
                return {"ok": True}

            # Enforce whitelist
            allowed = db.query(AllowedUser).filter(AllowedUser.user_id == user_id).first()
            if not allowed:
                response_text = (
                    "⛔ You are not authorized to use this bot.\n\n"
                    f"Your user ID is: `{user_id}`\n"
                    "Ask the admin to whitelist you."
                )
                await telegram_sender.send_message(str(chat_id), response_text)
                return {"ok": True}

            # Update allowed user metadata
            allowed.last_seen = datetime.utcnow()
            allowed.username = username
            allowed.first_name = first_name
            allowed.last_name = last_name
            db.commit()

            # Lookup client pools
            client = db.query(Client).filter(Client.client_key == client_key).first()
            if not client:
                all_clients = [c.client_key for c in db.query(Client).order_by(Client.client_key.asc()).all()]
                listing = "\n".join([f"- `{ck}`" for ck in all_clients]) if all_clients else "_(no clients configured yet)_"
                response_text = (
                    f"❓ Unknown client: `{client_key}`\n\n"
                    "Available clients:\n"
                    f"{listing}"
                )
                await telegram_sender.send_message(str(chat_id), response_text)
                return {"ok": True}

            pool_addresses = [cp.pool_address for cp in client.pools]
            if not pool_addresses:
                response_text = f"⚠️ Client `{client_key}` has no pools assigned."
                await telegram_sender.send_message(str(chat_id), response_text)
                return {"ok": True}

            await telegram_sender.send_message(str(chat_id), f"🔄 Generating report for `{client_key}`...")
            asyncio.create_task(_send_client_report(str(chat_id), client_key, pool_addresses))
        
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
            raise HTTPException(
                status_code=400,
                detail="user_id lookup is no longer supported. Provide pool_addresses directly, or use the Telegram bot client-name flow."
            )

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
            
            # Fetch per-pool data for insights (pool types, tokens, etc.)
            # This is used only by the insights pipeline, not by the email templates.
            pools_data: list[dict] = []
            for addr in pool_addresses:
                try:
                    pool_info = await calculator.api.get_current_pool_data(addr)
                except Exception as e:
                    print(f"⚠️  Failed to fetch pool data for {addr}: {e}")
                    pool_info = {"address": addr}
                pools_data.append(pool_info)
            
            # Send email
            print(f"📧 Sending comparison report to {request.recipient_email}...")
            if request.recipient_email and email_sender.enabled:
                try:
                    await email_sender.send_pool_report(
                        recipient_email=request.recipient_email,
                        pool_name=f"{len(multi_metrics.pools)} Pools",
                        metrics_data=metrics_data,
                        multi_pool=True
                    )
                    print("✅ Comparison email report sent successfully!")
                except EmailSenderError as e:
                    # Fail-open: continue to Telegram / response even if email fails.
                    print(f"⚠️  Email sending failed (continuing without email): {str(e)}")
            else:
                print("ℹ️  Email disabled or recipient_email missing; skipping email.")

            # Also send Telegram card (secondary channel)
            # Use request-level telegram_chat_id if provided, otherwise use env variable
            telegram_chat_id = request.telegram_chat_id or settings.telegram_chat_id
            if telegram_chat_id:
                print(f"✈️ Sending Telegram multi-pool Card to Chat ID: {telegram_chat_id}...")
                await telegram_sender.send_multi_pool_report(
                    metrics_data=metrics_data,
                    chat_id=telegram_chat_id,
                    metrics=multi_metrics,
                    pools_data=pools_data,
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
            if request.recipient_email and email_sender.enabled:
                try:
                    await email_sender.send_pool_report(
                        recipient_email=request.recipient_email,
                        pool_name=metrics.pool_name,
                        metrics_data=metrics_data,
                        multi_pool=False
                    )
                    print("✅ Email report sent successfully!")
                except EmailSenderError as e:
                    # Fail-open: continue to Telegram / response even if email fails.
                    print(f"⚠️  Email sending failed (continuing without email): {str(e)}")
            else:
                print("ℹ️  Email disabled or recipient_email missing; skipping email.")

            # Optionally, also send Telegram card (secondary channel)
            # Use request-level telegram_chat_id if provided, otherwise use env variable
            telegram_chat_id = request.telegram_chat_id or settings.telegram_chat_id
            if telegram_chat_id:
                print(f"✈️ Sending Telegram Card to Chat ID: {telegram_chat_id}...")
                await telegram_sender.send_pool_report(
                    pool_data=pool_data,
                    metrics_data=metrics_data,
                    chat_id=telegram_chat_id,
                    metrics=metrics
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
