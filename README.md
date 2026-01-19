# Balancer Pool Performance Reporter

A FastAPI-based web service that generates and emails performance reports for Balancer v2/v3 liquidity pools. The service queries Balancer's GraphQL APIs to fetch pool metrics, compares current performance with data from 15 days ago, and sends beautifully styled reports via email and Telegram with visual change indicators and adaptive precision formatting.

## Features

- 📊 **Works with Both V2 and V3 Pools** - Automatically detects pool version
- 🔀 **Multi-Pool Comparison** - Compare multiple pools with rankings and totals
- 🎯 **Pool-Type Specific Metrics** - Weighted pools show token weights, Boosted pools show yield APR
- 📈 **Performance Tracking** - Compares current metrics with 15-day historical data
- 📉 **Change Indicators** - Volume and fees show % change with visual indicators (📈/📉)
- 🎨 **Adaptive Precision** - Automatically adjusts decimal places for tiny percentage changes
- 💡 **Smart APR Calculation** - 5-level fallback including fee-based calculation for pools without APR data
- 📧 Sends beautifully styled HTML email reports with responsive design, gradient headers, and dark theme matching balancer.fi design
- 🏆 Rankings: Top 3 pools by Volume, TVL Growth, Swap Fee, and more
- 💰 Aggregated metrics: Total fees and weighted average APR
- ⚙️ **Configurable Rankings** - Choose which metrics to rank pools by
- 🔗 **Clickable Pool Links** - Direct links to balancer.fi
- 🚀 FastAPI with automatic API documentation and lifecycle management
- ⚡ Async/await for efficient API calls
- 🔒 Type-safe with Pydantic models
- 🔄 Smart fallback: Tries V3 API first, then V2 Subgraph
- 📨 **Telegram Integration** - Sends rich image cards with key pool metrics to a Telegram chat for single-pool reports
- 👥 **User Management System** - PostgreSQL database with Streamlit admin UI for managing users and their pool assignments
- 🎨 **Admin Dashboard** - Beautiful Streamlit interface to assign pools to users, view activity, and manage the system

## Metrics Tracked

### Core Metrics (All Pools)
- **Pool Type**: Weighted, Stable, Boosted, etc.
- **Swap Fee**: Trading fee percentage (up to 4 decimal precision for low-fee pools)
- **TVL (Total Value Locked)**: Current vs 15 days ago with % change
- **Volume**: Total swap volume over the last 15 days with % change from previous period
- **Fees**: Total fees collected over the last 15 days with % change from previous period
- **APR**: Current Annual Percentage Rate (calculated from fees if not available from API)

### Pool-Type Specific Metrics
- **Token Weights** (Weighted pools): Allocation percentages for each token
- **Boosted APR** (Boosted pools): Yield from underlying yield-bearing tokens
- **Rebalance Count** (Gyro/LVR pools): Number of rebalances in 15 days (when available)
- **Surge Fees** (Stable Surge pools): Dynamic fee adjustments (when available)

### Adaptive Precision
Volume and fees change percentages automatically adjust decimal precision based on magnitude:
- **< 0.01%**: 4 decimal places (e.g., `+0.0003%`) - for low-activity pools
- **< 1.0%**: 3 decimal places (e.g., `+0.120%`) - for moderate changes
- **≥ 1.0%**: 2 decimal places (e.g., `+7.90%`) - for significant changes

### APR Calculation
The system uses a comprehensive fallback approach for APR:
1. Direct `totalApr` field from API (V3 pools)
2. Sum of `aprItems` array (V2 and some V3 pools)
3. Direct `apr` field in pool data
4. APR from root pool object
5. **Fee-based calculation**: `APR = (daily_fees × 365) / TVL` (fallback for pools without APR data)

### ⚠️ V3 Pool Limitations
V3 pools may have limited historical data availability:
- **Historical snapshots** are queried from the V3 API but may not always be available
- When V3 snapshots are unavailable:
  - **Volume/Fees** are estimated by extrapolating 24h data to 15 days (marked as "est.")
  - **TVL comparison** shows current value only ("N/A" for change percentage)
  - A note will appear in the email report indicating estimated data
- All other current metrics (APR, swap fee, pool type) work normally
- The system automatically attempts V3 snapshots first, then falls back to estimates

V2 pools have full historical comparison with accurate 15-day metrics from the V2 Subgraph.

## Requirements

- Python 3.11 or higher
- pip (Python package manager)
- PostgreSQL 12 or higher (for user management)

## Installation

### 1. Install PostgreSQL

**On macOS:**
```bash
# Using Homebrew
brew install postgresql@15
brew services start postgresql@15

# Create database
createdb pool_report
```

**On Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql

# Create database
sudo -u postgres createdb pool_report
```

**On Windows:**
- Download and install from https://www.postgresql.org/download/windows/
- Use pgAdmin to create a database named `pool_report`

### 2. Clone and Setup Python Environment

Create a virtual environment with Python 3.11:

```bash
python3.11 -m venv venv
source venv/bin/activate
```

### 3. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the project root:

```bash
touch .env
```

Edit `.env` with your configuration (see Configuration section below).

### 5. Initialize Database

```bash
python init_db.py
```

This will create the required database tables (`users` and `user_pools`).

## Configuration

Edit the `.env` file with your settings:

```env
# SMTP Configuration (use Gmail, Outlook, or custom SMTP)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password
FROM_EMAIL=your_email@gmail.com

# Balancer APIs
BALANCER_V3_API=https://api-v3.balancer.fi/
BALANCER_V2_SUBGRAPH=https://api.studio.thegraph.com/query/24617/balancer-v2
BALANCER_GQL_ENDPOINT=https://gateway-arbitrum.network.thegraph.com/api/YOUR_API_KEY/subgraphs/id/YOUR_SUBGRAPH_ID
DEFAULT_CHAIN=MAINNET          # For API queries (MAINNET, ARBITRUM, POLYGON, etc.)
BLOCKCHAIN_NAME=ethereum       # For balancer.fi URLs (ethereum, arbitrum, polygon, etc.)

# Telegram Integration (Optional)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_default_chat_id    # Optional: Default chat ID for reports

# Database Configuration
DATABASE_URL=postgresql://user:password@localhost:5432/pool_report
```

**Database URL Format:**
```
postgresql://username:password@host:port/database_name
```

**Multi-Chain Support:**
- `DEFAULT_CHAIN`: Used for GraphQL API queries (e.g., `MAINNET`, `ARBITRUM`, `POLYGON`)
- `BLOCKCHAIN_NAME`: Used for generating balancer.fi URLs (e.g., `ethereum`, `arbitrum`, `polygon`)
- Both should represent the same network, just in different formats

### Gmail SMTP Setup

If using Gmail, you'll need to:
1. Enable 2-factor authentication
2. Generate an "App Password" at https://myaccount.google.com/apppasswords
3. Use the app password in the `.env` file

### Telegram Bot Setup (Optional)

The application includes a scalable Telegram integration that allows users to receive reports without editing environment variables.

#### 1. Create Your Bot

1. Open Telegram and message [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the prompts
3. Copy the bot token provided by BotFather
4. Add the token to your `.env` file as `TELEGRAM_BOT_TOKEN`

#### 2. Configure Webhook

Once your FastAPI server is running and accessible (either locally with ngrok or deployed):

**Option A: Using the API endpoint**
```bash
curl -X POST "http://localhost:8000/telegram/setup-webhook?webhook_url=https://your-domain.com/telegram/webhook"
```

**Option B: Direct Telegram API**
```bash
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://your-domain.com/telegram/webhook"}'
```

**For local development with ngrok:**
```bash
# Start ngrok
ngrok http 8000

# Use the ngrok URL for webhook
curl -X POST "http://localhost:8000/telegram/setup-webhook?webhook_url=https://your-ngrok-url.ngrok.io/telegram/webhook"
```

#### 3. Get Your Chat ID

Each user who wants to receive reports should:

1. Open Telegram and search for your bot
2. Send `/start` to the bot
3. The bot will reply with their Telegram Chat ID
4. Users include this chat ID in their API requests

**Example Bot Response:**
```
✅ Your Telegram Chat ID: 123456789

📋 Use this ID in your API requests to receive pool reports.

Example:
{
  "pool_addresses": ["0x..."],
  "recipient_email": "you@example.com",
  "telegram_chat_id": "123456789"
}
```

#### 4. Using Telegram Chat IDs in API Requests

Users can pass their chat ID directly in the POST request:

```json
{
  "pool_addresses": ["0x3de27efa2f1aa663ae5d458857e731c129069f29"],
  "recipient_email": "user@example.com",
  "telegram_chat_id": "123456789"
}
```

**Fallback Behavior:**
- If `telegram_chat_id` is provided in the request, reports go to that chat
- If not provided, reports go to the `TELEGRAM_CHAT_ID` from `.env` (if configured)
- If neither is configured, Telegram sending is skipped (email still works)

**Benefits of This Approach:**
- ✅ No manual chat ID discovery via getUpdates
- ✅ No need to edit `.env` for different users
- ✅ Scalable for multiple users
- ✅ Each user controls their own chat ID
- ✅ Maintains security (only users with API access can send to their own chat)

## Usage

### Start the Services

You'll need to run two services:

**1. FastAPI Server (main application):**
```bash
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`

**2. Admin UI (user management dashboard):**
```bash
# In a separate terminal
streamlit run admin_ui.py
```

The admin UI will be available at `http://localhost:8501`

### API Documentation

FastAPI provides automatic interactive documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Admin Dashboard**: http://localhost:8501

### Generate a Single Pool Report

Send a POST request to `/report` with one pool.

For single-pool requests, the service:
- Sends an HTML email report to the configured `recipient_email`
- Sends a Telegram image card + markdown summary to the specified chat ID (if provided) or default chat ID

```bash
curl -X POST "http://localhost:8000/report" \
  -H "Content-Type: application/json" \
  -d '{
    "pool_addresses": ["0x3de27efa2f1aa663ae5d458857e731c129069f29"],
    "recipient_email": "your.email@example.com",
    "telegram_chat_id": "123456789"
  }'
```

**Note:** `telegram_chat_id` is optional. If omitted, the default `TELEGRAM_CHAT_ID` from `.env` is used (if configured).

### Send Reports to Users (Admin-Controlled)

**Recommended workflow:** Admins send reports to users via the Streamlit UI.

**How it works:**
1. User sends `/start` to your Telegram bot → Gets registered in database
2. Admin assigns pools to user via Streamlit UI
3. Admin navigates to "📧 Send Reports" tab in Streamlit
4. Admin enters user's email and clicks "📧 Send"
5. System generates report for user's assigned pools
6. Report sent to email and Telegram automatically

**Benefits:**
- ✅ Admin controls when reports are sent
- ✅ Users don't need to know pool addresses or make API requests
- ✅ Simple workflow - just click a button
- ✅ Centralized management
- ✅ Search and filter users

**Alternative - Direct API Access (Advanced):**

You can also trigger reports programmatically via API:

```bash
curl -X POST "http://localhost:8000/report" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 123456789,
    "recipient_email": "user@example.com"
  }'
```

### Generate a Multi-Pool Comparison Report

Send a POST request with multiple pools.

For multi-pool requests, the service:
- Sends an HTML summary email report to the configured `recipient_email`
- Sends a Telegram image card + markdown summary to the specified chat ID (if provided) or default chat ID

```bash
curl -X POST "http://localhost:8000/report" \
  -H "Content-Type: application/json" \
  -d '{
    "pool_addresses": [
      "0x3de27efa2f1aa663ae5d458857e731c129069f29",
      "0x5c6ee304399dbdb9c8ef030ab642b10820db8f56",
      "0x96646936b91d6b9d7d0c47c496afbf3d6ec7b6f8"
    ],
    "recipient_email": "your.email@example.com",
    "telegram_chat_id": "123456789"
  }'
```

**Multi-Pool Report Includes:**
- 🏆 Top 3 pools by Trading Volume (with % of total portfolio volume)
- 💎 Top 3 pools by TVL Growth (absolute increase + % change from 15 days ago)
- 💰 Total Fees collected (all pools combined)
- 🚀 Weighted Average APR (by TVL)

### Multi-Pool with Custom Rankings

Add custom rankings to your multi-pool reports:

```bash
curl -X POST "http://localhost:8000/report" \
  -H "Content-Type: application/json" \
  -d '{
    "pool_addresses": [
      "0x3de27efa2f1aa663ae5d458857e731c129069f29",
      "0x5c6ee304399dbdb9c8ef030ab642b10820db8f56"
    ],
    "recipient_email": "your.email@example.com",
    "ranking_by": ["swap_fee", "boosted_apr"]
  }'
```

**Available Ranking Metrics:**
- `volume` - Top pools by trading volume (default)
- `tvl_growth` - Top pools by TVL increase (default)
- `swap_fee` - Top pools by swap fee percentage
- `boosted_apr` - Top pools by boosted APR (Boosted pools only)
- `rebalance_count` - Top pools by rebalance activity (when available)

Or use the interactive Swagger UI at `/docs` to test the endpoint.

**Note:** For backwards compatibility, you can still use `pool_address` (singular) for single pool reports.

## User Management System

### Admin Dashboard

Access the Streamlit admin UI at `http://localhost:8501` to manage users and their pool assignments.

**Features:**
- 👥 **Users Tab**: View all registered users, their Telegram info, and activity
- 🏊 **Manage Pools Tab**: Assign/remove pools for each user
- 📧 **Send Reports Tab**: Send reports to users with one click
- 📊 **Overview Tab**: System statistics, recent activity, and pool distribution charts

### Workflow: From Registration to Report

1. **User Registration:**
   - User opens Telegram and messages your bot
   - User sends `/start` command
   - Bot automatically saves user info (user_id, username, name) to database
   - Bot replies confirming registration

2. **Admin Pool Assignment:**
   - Admin opens Streamlit UI at `http://localhost:8501`
   - Goes to "🏊 Manage Pools" tab
   - Selects user from dropdown
   - Adds one or more pool addresses
   - Pools are now assigned to that user

3. **Admin Sends Report:**
   - Admin goes to "📧 Send Reports" tab
   - Searches for user (optional)
   - Enters user's email address
   - Clicks "📧 Send" button
   - System generates and sends report to email + Telegram

**Note:** Users don't need to do anything after registration. The admin controls when reports are sent.

### Bot Commands

- `/start` - Register and get your user ID
- `/myid` - Get your user ID and see how many pools are assigned

### Health Check

```bash
curl http://localhost:8000/health
```

### API Information

```bash
curl http://localhost:8000/
```

Returns API information including available endpoints.

## API Endpoints

### GET /

Root endpoint with API information.

**Response:**
```json
{
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
```

### POST /report

Generate and send a pool performance report.

- **Single pool:** HTML email report + Telegram card (if Telegram is configured)
- **Multiple pools:** HTML email summary report + Telegram card (multi-pool comparison)

**Request Body (Single Pool):**
```json
{
  "pool_addresses": ["0x3de27efa2f1aa663ae5d458857e731c129069f29"],
  "recipient_email": "user@example.com",
  "telegram_chat_id": "123456789"
}
```

**Request Body (Multiple Pools):**
```json
{
  "pool_addresses": [
    "0x3de27efa2f1aa663ae5d458857e731c129069f29",
    "0x5c6ee304399dbdb9c8ef030ab642b10820db8f56"
  ],
  "recipient_email": "user@example.com",
  "telegram_chat_id": "123456789",
  "ranking_by": ["volume", "tvl_growth"]
}
```

**Optional Fields:**
- `telegram_chat_id` (string): Telegram chat ID to send report to (overrides env variable)
- `ranking_by` (array): Metrics to rank by in multi-pool reports (default: `["volume", "tvl_growth"]`)

**Response:**
```json
{
  "status": "sent",
  "timestamp": "2026-01-17T12:00:00Z",
  "pool_name": "Pool Name",
  "pool_address": "0x3de27efa2f1aa663ae5d458857e731c129069f29"
}
```

### GET /health

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-01-17T12:00:00Z"
}
```

### POST /telegram/webhook

Webhook endpoint for Telegram bot updates. Handles bot commands like `/start` and `/myid` to help users discover their chat ID.

**This endpoint is called automatically by Telegram when users interact with your bot. You don't need to call it manually.**

**Supported Commands:**
- `/start` - Welcome message with user's chat ID
- `/myid` - Returns user's chat ID

**Response:**
```json
{
  "ok": true
}
```

### POST /telegram/setup-webhook

Configure the Telegram bot webhook URL. Call this once after deploying to register your webhook endpoint with Telegram.

**Query Parameters:**
- `webhook_url` (string, required): Your public webhook URL (e.g., `https://your-domain.com/telegram/webhook`)

**Example:**
```bash
curl -X POST "http://localhost:8000/telegram/setup-webhook?webhook_url=https://your-domain.com/telegram/webhook"
```

**Response (Success):**
```json
{
  "status": "success",
  "webhook_url": "https://your-domain.com/telegram/webhook",
  "response": {
    "ok": true,
    "result": true,
    "description": "Webhook was set"
  }
}
```

## Project Structure

```
pool-report/
├── main.py                        # FastAPI application entry point
├── config.py                      # Pydantic settings configuration
├── models.py                      # Pydantic request/response models
├── database.py                    # SQLAlchemy database models and session
├── init_db.py                     # Database initialization script
├── admin_ui.py                    # Streamlit admin dashboard
├── services/
│   ├── balancer_api.py            # GraphQL queries to Balancer APIs
│   ├── metrics_calculator.py      # Metrics comparison logic
│   ├── email_sender.py            # SMTP email sending
│   └── telegram_sender.py         # Telegram card generation and sending
├── templates/
│   ├── email_report.html          # Single pool email template
│   ├── email_report_multi.html    # Multi-pool comparison email template
│   ├── telegram_card.html         # Single pool Telegram card template
│   └── telegram_card_multi.html   # Multi-pool Telegram card template
├── requirements.txt               # Python dependencies
├── .env                           # Environment variables (create this)
└── README.md                      # This file
```

## Development

### Running in Development Mode

```bash
uvicorn main:app --reload --port 8000
```

### Testing the Email Template

You can test email generation without sending by examining the logs or temporarily modifying the email sender to save HTML to a file.

## Database Schema

The user management system uses two main tables:

**users**
- `user_id` (Primary Key): Telegram user ID
- `username`: Telegram username
- `first_name`: User's first name
- `last_name`: User's last name (optional)
- `created_at`: Registration timestamp
- `last_seen`: Last interaction timestamp

**user_pools**
- `id` (Primary Key): Auto-increment ID
- `user_id` (Foreign Key): References users.user_id
- `pool_address`: Ethereum pool address (0x...)
- `added_at`: Timestamp when pool was assigned

## Deployment

See **[DEPLOYMENT.md](DEPLOYMENT.md)** for comprehensive deployment instructions.

**Quick Start:**
- **Easiest**: Railway (FastAPI + PostgreSQL) + Streamlit Cloud (Admin UI)
- **Free Tier**: Railway $5/month credit + Streamlit Cloud free
- **Total Setup Time**: ~15 minutes

**What you get:**
- ✅ Public HTTPS URLs for both services
- ✅ Automatic database backups
- ✅ Auto-deploy on git push
- ✅ Environment variable management
- ✅ Logs and monitoring

## Troubleshooting

### PostgreSQL Connection Issues

If you get database connection errors:

1. **Check PostgreSQL is running:**
   ```bash
   # macOS
   brew services list | grep postgresql
   
   # Linux
   sudo systemctl status postgresql
   ```

2. **Verify database exists:**
   ```bash
   psql -l | grep pool_report
   ```

3. **Test connection:**
   ```bash
   psql postgresql://localhost:5432/pool_report
   ```

4. **Check DATABASE_URL in .env:**
   - Format: `postgresql://username:password@host:port/database_name`
   - Default PostgreSQL user is usually `postgres` or your system username
   - Default port is `5432`

### Webhook Not Receiving Messages

1. Make sure webhook URL is publicly accessible (use ngrok for local testing)
2. Verify webhook is registered: Check bot settings with BotFather
3. Check FastAPI logs for incoming requests

## Future Enhancements

- [x] Support for multiple pools in a single report ✅
- [x] Telegram integration for notifications ✅
- [x] User management system with database ✅
- [x] Admin dashboard for pool assignment ✅
- [ ] Add charts and visualizations to reports
- [ ] Scheduled reports (daily/weekly cron jobs)
- [ ] User authentication for admin dashboard
- [ ] Bot commands for users to request reports directly
- [ ] Historical report storage and retrieval
- [ ] WebSocket support for real-time updates
- [ ] Full V3 pool historical data (pending V3 API availability)

## License

MIT

## Support

For issues or questions, please open an issue on the repository.
