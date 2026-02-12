"""
FastAPI application for Balancer Pool Performance Reporter.
Generates and emails performance reports for Balancer pools.
"""
from fastapi import FastAPI, HTTPException, status, Request, Depends
from fastapi.responses import JSONResponse
from datetime import datetime, timezone
from contextlib import asynccontextmanager
import httpx
import asyncio
from sqlalchemy.orm import Session

from models import ReportRequest, ReportResponse, HealthResponse
from services.metrics_calculator import MetricsCalculator
from services.email_sender import EmailSender, EmailSenderError
from services.balancer_api import BalancerAPIError
from services.telegram_sender import TelegramSender
from services.anchor_token_info import AnchorTokenInfo
from services.data_exporter import DataExporter
from services.lp_return_calculator import LPReturnCalculator
from config import settings


# Lifespan context manager for startup/shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for the FastAPI app."""
    # Startup
    print("🚀 Starting Balancer Pool Reporter API...")
    
    # Cleanup old exports on startup
    exporter = DataExporter()
    exporter.cleanup_old_exports(max_age_hours=24)
    
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


# @app.post("/telegram/webhook", tags=["Telegram"])
# async def telegram_webhook(request: Request, db: Session = Depends(get_db)):
#     """
#     Webhook endpoint for Telegram bot updates.
#     New behavior:
#     - /start and /myid: help users discover their Telegram user_id and request whitelist access.
#     - Any other text (e.g. \"aave\"): if user is whitelisted, treat it as a client key and send a report back on Telegram.
#     """
#     try:
#         data = await request.json()
        
#         # Extract message and chat info
#         if "message" in data:
#             message = data["message"]
#             chat_id = message["chat"]["id"]
#             text = message.get("text", "")
            
#             # Extract user info
#             from_user = message.get("from", {})
#             user_id = from_user.get("id")
#             username = from_user.get("username")
#             first_name = from_user.get("first_name", "")
#             last_name = from_user.get("last_name")

#             telegram_sender = TelegramSender()

#             def _normalize_client_key(raw: str) -> str:
#                 return (raw or "").strip().lower()

#             async def _send_client_report(target_chat_id: str, client_key: str, pool_addresses: list[str]) -> None:
#                 """
#                 Background task: generate report metrics and send to Telegram.
#                 """
#                 try:
#                     calculator = MetricsCalculator()

#                     # Decide single vs multi
#                     if len(pool_addresses) == 1:
#                         pool_address = pool_addresses[0]
#                         metrics = await calculator.calculate_pool_metrics(pool_address)
#                         pool_data = await calculator.api.get_current_pool_data(pool_address)
#                         metrics_data = calculator.format_metrics_for_email(metrics, pool_data)

#                         # Add fields used by Telegram templates/caption
#                         pool_id = pool_data.get("id", pool_address)
#                         blockchain = pool_data.get("_blockchain", "ethereum")
#                         version = pool_data.get("_api_version", "v2")
#                         pool_url_link = f"https://balancer.fi/pools/{blockchain}/{version}/{pool_id}"
#                         current_time = datetime.utcnow().strftime("%B %d, %Y at %H:%M UTC")

#                         metrics_data["pool_id"] = pool_id
#                         metrics_data["pool_url"] = pool_url_link
#                         metrics_data["timestamp"] = current_time

#                         await telegram_sender.send_pool_report(
#                             pool_data=pool_data,
#                             metrics_data=metrics_data,
#                             chat_id=str(target_chat_id),
#                             metrics=metrics
#                         )
#                     else:
#                         ranking_by = ["volume", "tvl_growth", "swap_fee"]
#                         multi_metrics = await calculator.calculate_multi_pool_metrics(pool_addresses, ranking_by=ranking_by)
#                         metrics_data = calculator.format_multi_pool_metrics_for_email(multi_metrics)
#                         await telegram_sender.send_multi_pool_report(
#                             metrics_data=metrics_data, 
#                             chat_id=str(target_chat_id),
#                             metrics=multi_metrics
#                         )

#                 except Exception as e:
#                     print(f"❌ Error generating Telegram client report for '{client_key}': {str(e)}")
#                     await telegram_sender.send_message(
#                         str(target_chat_id),
#                         f"❌ Failed to generate report for `{client_key}`. Please try again later.",
#                     )

#             # Commands
#             if text == "/start":
#                 response_text = (
#                     f"👋 Welcome {first_name}!\n\n"
#                     f"✅ *Your Telegram User ID:* `{user_id}`\n\n"
#                     "This bot is restricted.\n"
#                     "Ask the admin to whitelist your user ID.\n\n"
#                     "Once approved, send a client name like:\n"
#                     "`aave`"
#                 )
#                 await telegram_sender.send_message(str(chat_id), response_text)
#                 return {"ok": True}

#             if text == "/myid":
#                 response_text = f"✅ *Your Telegram User ID:* `{user_id}`"
#                 await telegram_sender.send_message(str(chat_id), response_text)
#                 return {"ok": True}

#             # Client-name request
#             client_key = _normalize_client_key(text)
#             if not client_key:
#                 return {"ok": True}

#             # Enforce whitelist
#             allowed = db.query(AllowedUser).filter(AllowedUser.user_id == user_id).first()
#             if not allowed:
#                 response_text = (
#                     "⛔ You are not authorized to use this bot.\n\n"
#                     f"Your user ID is: `{user_id}`\n"
#                     "Ask the admin to whitelist you."
#                 )
#                 await telegram_sender.send_message(str(chat_id), response_text)
#                 return {"ok": True}

#             # Update allowed user metadata
#             allowed.last_seen = datetime.utcnow()
#             allowed.username = username
#             allowed.first_name = first_name
#             allowed.last_name = last_name
#             db.commit()

#             # Lookup client pools
#             client = db.query(Client).filter(Client.client_key == client_key).first()
#             if not client:
#                 all_clients = [c.client_key for c in db.query(Client).order_by(Client.client_key.asc()).all()]
#                 listing = "\n".join([f"- `{ck}`" for ck in all_clients]) if all_clients else "_(no clients configured yet)_"
#                 response_text = (
#                     f"❓ Unknown client: `{client_key}`\n\n"
#                     "Available clients:\n"
#                     f"{listing}"
#                 )
#                 await telegram_sender.send_message(str(chat_id), response_text)
#                 return {"ok": True}

#             pool_addresses = [cp.pool_address for cp in client.pools]
#             if not pool_addresses:
#                 response_text = f"⚠️ Client `{client_key}` has no pools assigned."
#                 await telegram_sender.send_message(str(chat_id), response_text)
#                 return {"ok": True}

#             await telegram_sender.send_message(str(chat_id), f"🔄 Generating report for `{client_key}`...")
#             asyncio.create_task(_send_client_report(str(chat_id), client_key, pool_addresses))
        
#         return {"ok": True}
    
#     except Exception as e:
#         print(f"❌ Error in telegram webhook: {str(e)}")
#         return {"ok": False, "error": str(e)}


# @app.post("/telegram/setup-webhook", tags=["Telegram"])
# async def setup_telegram_webhook(webhook_url: str):
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
    summary="Generate and send comprehensive pool performance report",
    description="""
    Generate a comprehensive performance report for Balancer pool(s) with advanced features.
    
    **Core Metrics:**
    - Total Value Locked (TVL) comparison with 15 days ago
    - Volume and fees over the last 15 days
    - Current APR and fee percentages
    - Anchor token lending market analysis
    
    **New Features (Phases 1-4):**
    - 🚀 **Boosted Pool Detection**: Automatically detects and analyzes boosted pools
    - 📁 **Data Export**: Export to Excel/CSV with `export_format` parameter
    - 💰 **Hold vs Pool Analysis**: Compares LP returns vs holding tokens (automatic)
    - 📅 **Parameter Changes**: Detects fee/weight changes in last 30 days (automatic)
    
    **Request Modes:**
    1. Direct pool addresses: Provide `pool_addresses` array
    2. Optional data export: Set `export_format` to "excel", "csv", or "both"
    
    **Example Request:**
    ```json
    {
      "pool_addresses": ["0x3de27efa2f1aa663ae5d458857e731c129069f29"],
      "anchor_token_address": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
      "export_format": "both",
      "recipient_email": "user@example.com",
      "telegram_chat_id": "123456789"
    }
    ```
    
    **Response Includes:**
    - Report delivery status
    - Export file paths (if `export_format` specified)
    - Pool performance summary
    - Anchor token best lending market
    """
)
async def generate_report(request: ReportRequest):
    """
    Generate and send a comprehensive pool performance report.
    
    **Features:**
    - Single pool: Detailed report with all metrics
    - Multi-pool: Aggregated summary with rankings
    - Boosted pool support: Automatic detection and underlying token extraction
    - Data export: Excel/CSV export for single pool reports (Phase 6)
    - Hold vs Pool: Profitability analysis (automatic for supported pools)
    - Parameter changes: Historical configuration changes (automatic)
    
    **Args:**
        request: ReportRequest with pool addresses and optional export format
        
    **Returns:**
        ReportResponse with status, timestamp, and export file paths (if export requested)
        
    **Raises:**
        HTTPException: If report generation or sending fails
        
    **Export Feature (Phase 6):**
    Single pool reports can be exported to Excel/CSV by setting `export_format`:
    - "excel": Multi-sheet Excel workbook with metrics and analysis
    - "csv": Flat CSV file for easy data import
    - "both": Both Excel and CSV files
    
    Export files include:
    - Basic pool metrics (TVL, volume, fees, APR)
    - Hold vs Pool analysis (Phase 3)
    - Parameter changes (Phase 4)
    - Anchor token data (if provided)
    
    Note: Multi-pool export is not yet implemented (future Phase 7)
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

        # Get anchor token information
        anchor_service = AnchorTokenInfo()
        anchor_data = None
        anchor_df = None  # Store full DataFrame for export
        anchor_csv_path = None  # Store CSV path
        try:
            anchor_address = request.anchor_token_address.lower()
            # Default to ethereum for anchor token lookup if not detectable from first pool
            blockchain = "ethereum"
            try:
                first_pool_data = await calculator.api.get_current_pool_data(pool_addresses[0])
                blockchain = first_pool_data.get("_blockchain", "ethereum")
            except:
                pass

            print(f"⚓ Retrieving info for anchor token: {anchor_address}")
            # get_token_data handles CSV saving internally if debug=True
            anchor_df = await anchor_service.get_token_data(anchor_address, blockchain, debug=True)
            
            # Get summary stats to include in report
            if not anchor_df.empty:
                anchor_data = {
                    "token_address": anchor_address,
                    "token_symbol": anchor_service._resolve_token_symbol(anchor_address),
                    "stats": anchor_service.get_summary_stats(anchor_df),
                    "top_market": anchor_df.iloc[0].to_dict() if len(anchor_df) > 0 else None
                }
            
        except Exception as e:
            print(f"⚠️ Could not retrieve anchor token info: {str(e)}")

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
            
            # Add anchor token info if available
            if anchor_data:
                metrics_data["anchor_token"] = anchor_data
            
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
            
            # Export data if requested (Phase 6: Export Integration)
            export_files = {}
            if request.export_format:
                try:
                    print(f"📁 Generating multi-pool {request.export_format} export...")
                    data_exporter = DataExporter()
                    
                    export_files = data_exporter.export_multi_pool_metrics(
                        multi_metrics=multi_metrics,
                        anchor_data=anchor_data,
                        anchor_df=anchor_df,
                        format=request.export_format,
                    )
                    
                    print(f"✅ Multi-pool export successful!")
                    for fmt, path in export_files.items():
                        print(f"   {fmt.upper()}: {path}")
                        
                except Exception as e:
                    print(f"⚠️  Export failed: {e}")
                    import traceback
                    traceback.print_exc()
            
            return ReportResponse(
                status="sent",
                timestamp=datetime.utcnow(),
                pool_name=f"Comparison of {len(multi_metrics.pools)} Pools",
                pool_address=", ".join(pool_addresses[:3]) + ("..." if len(pool_addresses) > 3 else ""),
                export_files=export_files if export_files else None
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
            
            # Add anchor token info if available
            if anchor_data:
                metrics_data["anchor_token"] = anchor_data
            
            # Calculate hold vs pool analysis
            hold_vs_pool_data = None
            try:
                lp_calc = LPReturnCalculator()
                hold_vs_pool_data = await lp_calc.calculate_hold_vs_pool(
                    pool_address=pool_address,
                    days=30,  # Configurable via request if needed
                    initial_investment_usd=10000  # Configurable via request if needed
                )
                print(f"✅ Hold vs Pool: {hold_vs_pool_data['comparison']['recommendation']}")
                metrics_data["hold_vs_pool"] = hold_vs_pool_data
            except Exception as e:
                print(f"⚠️  Hold vs Pool calculation failed: {e}")
                # Don't fail the whole request
            
            # Detect parameter changes (Phase 4)
            parameter_changes = []
            try:
                from services.pool_history_analyzer import PoolHistoryAnalyzer
                history_analyzer = PoolHistoryAnalyzer()
                changes = await history_analyzer.detect_changes_in_period(pool_address, days=30)
                
                # Analyze impact for each change
                for change in changes:
                    try:
                        impact = await history_analyzer.analyze_impact_of_change(pool_address, change)
                        change.impact = impact
                        
                        # Format for template
                        parameter_changes.append({
                            "type_display": change.change_type.replace("_", " ").title(),
                            "days_ago": (datetime.now(timezone.utc) - datetime.fromtimestamp(change.timestamp, tz=timezone.utc)).days,
                            "before": str(change.details.get("before", "N/A")),
                            "after": str(change.details.get("after", "N/A")),
                            "impact": impact,
                        })
                    except Exception as e:
                        print(f"⚠️  Failed to analyze impact for change: {e}")
                        # Add the change without impact analysis
                        parameter_changes.append({
                            "type_display": change.change_type.replace("_", " ").title(),
                            "days_ago": (datetime.now(timezone.utc) - datetime.fromtimestamp(change.timestamp, tz=timezone.utc)).days,
                            "before": str(change.details.get("before", "N/A")),
                            "after": str(change.details.get("after", "N/A")),
                            "impact": None,
                        })
                
                print(f"✅ Detected {len(parameter_changes)} parameter changes")
                metrics_data["parameter_changes"] = parameter_changes if parameter_changes else None
            except Exception as e:
                print(f"⚠️  Parameter change detection failed: {e}")
                # Don't fail the whole request
                metrics_data["parameter_changes"] = None
            
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
            
            # Export data if requested (Phase 6: Export Integration)
            export_files = {}
            if request.export_format:
                try:
                    print(f"📁 Generating {request.export_format} export...")
                    data_exporter = DataExporter()
                    
                    # Use adapter method to export simple metrics
                    # Note: This exports MetricsCalculator data (basic metrics only).
                    # For full competitor data from all 8 Dune metric groups,
                    # future enhancement would use MetricsPipeline instead.
                    export_files = data_exporter.export_simple_pool_metrics(
                        pool_data=pool_data,
                        metrics_data=metrics_data,
                        anchor_data=anchor_data,
                        anchor_df=anchor_df,  # Pass full DataFrame for Excel export
                        format=request.export_format,
                        filename=None  # Auto-generate filename
                    )
                    
                    print(f"✅ Export successful!")
                    for fmt, path in export_files.items():
                        print(f"   {fmt.upper()}: {path}")
                        
                except Exception as e:
                    print(f"⚠️  Export failed: {e}")
                    # Don't fail the whole request if export fails
                    import traceback
                    traceback.print_exc()
            
            return ReportResponse(
                status="sent",
                timestamp=datetime.utcnow(),
                pool_name=metrics.pool_name,
                pool_address=pool_address,
                export_files=export_files if export_files else None
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

# ---- End of /report endpoint ---- #

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
