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

## Installation

1. Clone the repository

2. Create a virtual environment with Python 3.11:

```bash
python3.11 -m venv venv
source venv/bin/activate
```

Or use the provided setup script:

```bash
./setup_python311.sh
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Copy `.env.example` to `.env` and configure your settings:

```bash
cp .env.example .env
```

5. Edit `.env` with your SMTP credentials and preferences

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

# Telegram Integration
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
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

## Usage

### Start the Server

```bash
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`

### API Documentation

FastAPI provides automatic interactive documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Generate a Single Pool Report

Send a POST request to `/report` with one pool.

For single-pool requests, the service:
- Sends an HTML email report to the configured `recipient_email`
- Sends a Telegram image card + markdown summary to the configured chat ID (if Telegram is configured)

```bash
curl -X POST "http://localhost:8000/report" \
  -H "Content-Type: application/json" \
  -d '{
    "pool_addresses": ["0x3de27efa2f1aa663ae5d458857e731c129069f29"],
    "recipient_email": "your.email@example.com"
  }'
```

### Generate a Multi-Pool Comparison Report

Send a POST request with multiple pools.

For multi-pool requests, the service:
- Sends an HTML summary email report to the configured `recipient_email`
- Sends a Telegram image card + markdown summary to the configured chat ID (if Telegram is configured)

```bash
curl -X POST "http://localhost:8000/report" \
  -H "Content-Type: application/json" \
  -d '{
    "pool_addresses": [
      "0x3de27efa2f1aa663ae5d458857e731c129069f29",
      "0x5c6ee304399dbdb9c8ef030ab642b10820db8f56",
      "0x96646936b91d6b9d7d0c47c496afbf3d6ec7b6f8"
    ],
    "recipient_email": "your.email@example.com"
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
  "recipient_email": "user@example.com"
}
```

**Request Body (Multiple Pools):**
```json
{
  "pool_addresses": [
    "0x3de27efa2f1aa663ae5d458857e731c129069f29",
    "0x5c6ee304399dbdb9c8ef030ab642b10820db8f56"
  ],
  "recipient_email": "user@example.com"
}
```

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

## Project Structure

```
pool-report/
├── main.py                   # FastAPI application entry point
├── config.py                 # Pydantic settings configuration
├── models.py                 # Pydantic request/response models
├── services/
│   ├── balancer_api.py       # GraphQL queries to Balancer APIs
│   ├── metrics_calculator.py # Metrics comparison logic
│   ├── email_sender.py       # SMTP email sending
│   └── telegram_sender.py    # Telegram card generation and sending
├── templates/
│   ├── email_report.html     # Single pool email template (responsive, gradient design)
│   └── email_report_multi.html  # Multi-pool comparison email template
├── requirements.txt          # Python dependencies
├── .env.example              # Example environment variables
└── README.md                 # This file
```

## Development

### Running in Development Mode

```bash
uvicorn main:app --reload --port 8000
```

### Testing the Email Template

You can test email generation without sending by examining the logs or temporarily modifying the email sender to save HTML to a file.

## Future Enhancements

- [x] Support for multiple pools in a single report ✅
- [x] Telegram integration for notifications ✅
- [ ] Add charts and visualizations
- [ ] Store historical reports in a database
- [ ] Scheduled reports (daily/weekly cron jobs)
- [ ] Support for multiple email recipients
- [ ] Webhook notifications
- [ ] WebSocket support for real-time updates
- [ ] Full V3 pool historical data (pending V3 API availability)

## License

MIT

## Support

For issues or questions, please open an issue on the repository.
