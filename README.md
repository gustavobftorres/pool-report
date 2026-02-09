# Balancer Pool Performance Reporter

A FastAPI-based web service that generates performance reports for Balancer v2/v3 liquidity pools and anchor token lending markets. The service queries Balancer's GraphQL APIs to fetch pool metrics, compares current performance with data from 15 days ago, and sends beautifully styled reports via Telegram with visual change indicators and adaptive precision formatting.

## Key Features

- 📊 **Pool Performance Tracking**: Compare pool metrics (TVL, volume, fees, APR) with 15-day historical data
- ⚓ **Anchor Token Analysis**: Track lending market APYs and trading volumes for anchor tokens (USDC, WETH, etc.)
- 📈 **Multi-Pool Comparisons**: Analyze multiple pools with customizable ranking metrics
- 🤖 **Telegram Integration**: Receive formatted reports with visual cards directly in Telegram
- 💾 **CSV Export**: Generate CSV reports for anchor token lending markets (992+ markets tracked)
- 🔍 **Dune Analytics Integration**: Historical volume data from on-chain DEX aggregators

## Metrics Tracked

### Pool Performance Metrics
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

### Anchor Token Metrics (NEW)
- **Lending Markets**: APYs from 990+ lending protocols (Aave, Morpho, Compound, etc.)
- **Trading Volume**: 30-day Balancer swap volume by chain/version/pair (via Dune Analytics)
- **Best Market Identification**: Automatically identifies highest-yield lending opportunity
- **CSV Export**: Generates `anchor_token_info.csv` with complete market data
- **Supported Tokens**: USDC, WETH, wstETH, DAI, USDT, WBTC, rETH, cbETH (extensible)

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
# Balancer APIs
BALANCER_V3_API=https://api-v3.balancer.fi/
BALANCER_V2_SUBGRAPH=https://api.studio.thegraph.com/query/24617/balancer-v2
BALANCER_GQL_ENDPOINT=https://gateway-arbitrum.network.thegraph.com/api/YOUR_API_KEY/subgraphs/id/YOUR_SUBGRAPH_ID
DEFAULT_CHAIN=MAINNET          # For API queries (MAINNET, ARBITRUM, POLYGON, etc.)
BLOCKCHAIN_NAME=ethereum       # For balancer.fi URLs (ethereum, arbitrum, polygon, etc.)

# Telegram Integration (Required)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_default_chat_id    # Optional: Default chat ID for reports

# Dune Analytics (for anchor token volume data)
DUNE_API_KEY=your_dune_api_key
DUNE_ANCHOR_VOLUME_QUERY_ID=6664013
DUNE_QUERY_PERFORMANCE=medium              # Options: low, medium, high
DUNE_QUERY_TIMEOUT=60.0

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

### Dune Analytics Setup (for Anchor Token Volume)

To enable historical volume tracking for anchor tokens:

1. Create a free account at [dune.com](https://dune.com)
2. Get your API key from [dune.com/settings/api](https://dune.com/settings/api)
3. Create a new query using the SQL template in `ANCHOR_TOKEN_SETUP.md`
4. Copy the Query ID from the URL (e.g., `https://dune.com/queries/123456` → ID is `123456`)
5. Add both to your `.env` file

**Note:** Volume tracking will be skipped if Dune credentials are not configured. Lending market data (DefiLlama) works independently.

### Telegram Bot Setup 

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

### Generate a Single Pool Report with Anchor Token Analysis

Send a POST request to `/report` with one pool and an anchor token address.

For single-pool requests, the service:
- Fetches pool performance metrics (15-day comparison)
- Retrieves anchor token lending markets and trading volume
- Generates CSV export with complete anchor token data
- Sends a Telegram image card + markdown summary with anchor token info

```bash
curl -X POST "http://localhost:8000/report" \
  -H "Content-Type: application/json" \
  -d '{
    "pool_addresses": ["0x3de27efa2f1aa663ae5d458857e731c129069f29"],
    "anchor_token_address": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
    "recipient_email": "your.email@example.com",
    "telegram_chat_id": "123456789"
  }'
```

**Common Anchor Token Addresses (Ethereum Mainnet):**
- USDC: `0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48`
- WETH: `0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2`
- wstETH: `0x7f39c581f595b53c5cb19bd0b3f8da6c935e2ca0`

**Output:** Creates `anchor_token_info.csv` in project root with 990+ lending markets

**Note:** `telegram_chat_id` is optional. If omitted, the default `TELEGRAM_CHAT_ID` from `.env` is used (if configured).

### Send Reports to Users (Admin-Controlled)

**Recommended workflow:** Admins send reports to users via the Streamlit UI.

### Generate a Multi-Pool Comparison Report

Send a POST request with multiple pools and an anchor token.

For multi-pool requests, the service:
- Aggregates metrics across all pools
- Compares pools using customizable ranking criteria
- Includes anchor token lending market analysis
- Generates CSV export with anchor token data
- Sends a Telegram image card + markdown summary with rankings and anchor info

```bash
curl -X POST "http://localhost:8000/report" \
  -H "Content-Type: application/json" \
  -d '{
    "pool_addresses": [
      "0x3de27efa2f1aa663ae5d458857e731c129069f29",
      "0x5c6ee304399dbdb9c8ef030ab642b10820db8f56",
      "0x96646936b91d6b9d7d0c47c496afbf3d6ec7b6f8"
    ],
    "anchor_token_address": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
    "recipient_email": "your.email@example.com",
    "telegram_chat_id": "123456789"
  }'
```

**Multi-Pool Report Includes:**
- 🏆 Top 3 pools by Trading Volume (with % of total portfolio volume)
- 💎 Top 3 pools by TVL Growth (absolute increase + % change from 15 days ago)
- 💰 Total Fees collected (all pools combined)
- 🚀 Weighted Average APR (by TVL)
- ⚓ Anchor Token best lending market (protocol + APY)
- 📊 Number of lending markets tracked

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

### Generate Anchor Token CSV Only

To generate just the CSV file with anchor token data (no Telegram report):

```bash
cd /home/kaique/Documents/Projetos/pool-report
echo -e "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48\nethereum" | \
  PYTHONPATH=. ./venv/bin/python tests/interactive_anchor_test.py
```

**Output:** `anchor_token_info.csv` with columns:
- `protocol` - Lending protocol name (e.g., Aave V3, Morpho, Compound)
- `chain` - Blockchain network
- `symbol` - Market token symbol
- `apy` - Annual Percentage Yield (%)
- `tvl_usd` - Total Value Locked in USD
- `reward_tokens` - Additional reward tokens (if any)
- `pool_id` - Protocol-specific pool identifier

## User Management System

### Admin Dashboard

Access the Streamlit admin UI at `http://localhost:8501` to manage users and their pool assignments.

### Bot Commands

- `/start` - Register and get your user ID
- `/myid` - Get your user ID and see how many pools are assigned
**Request Fields:**
- `pool_addresses` (array, required): List of Balancer pool addresses
- `anchor_token_address` (string, required): Anchor token address for analysis
- `recipient_email` (string, required): Email address (used for record-keeping)
- `telegram_chat_id` (string, optional): Telegram chat ID to send report to (overrides env variable)
- `ranking_by` (array, optional): Metrics to rank by in multi-pool reports (default: `["volume", "tvl_growth"]`)

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
│   ├── telegram_sender.py         # Telegram card generation and sending
│   ├── anchor_token_info.py       # NEW: Anchor token lending & volume data
│   ├── dune_metrics.py            # Dune Analytics integration
│   └── insights_generator.py      # AI-powered insights generation
├── templates/
│   ├── telegram_card.html         # Single pool Telegram card (with anchor info)
│   └── telegram_card_multi.html   # Multi-pool Telegram card (with anchor info)
├── tests/
│   ├── test_anchor_token_info.py  # Unit tests for anchor token service
│   ├── test_anchor_integration.py # Integration tests
│   └── interactive_anchor_test.py # Manual testing script (generates CSV)
├── requirements.txt               # Python dependencies
├── .env                           # Environment variables (create this)
├── ANCHOR_TOKEN_SETUP.md          # Dune Analytics query setup guide
├── ANCHOR_TOKEN_IMPROVEMENTS.md   # Feature documentation
└── README.md                      # This file
```

## Testing

### Run All Tests
```bash
PYTHONPATH=. ./venv/bin/pytest -v
```

### Run Anchor Token Tests Only
```bash
PYTHONPATH=. ./venv/bin/pytest tests/test_anchor*.py -v
```

**Current Test Coverage:**
- ✅ 11 anchor token tests (unit + integration)
- ✅ Pool metrics calculation
- ✅ Multi-pool aggregation
- ✅ Token symbol resolution
- ✅ CSV export functionality

## Support

For issues or questions, please open an issue on the repository.
