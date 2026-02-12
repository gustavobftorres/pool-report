# Balancer Pool Performance Reporter

<<<<<<< HEAD
A FastAPI-based Telegram bot that generates and sends performance reports for Balancer v2/v3 liquidity pools. The service queries Balancer's GraphQL APIs to fetch pool metrics, compares current performance with data from 15 days ago, and sends reports via Telegram with visual cards and markdown summaries. Supports multi-chain pools (Ethereum, Arbitrum, Plasma, etc.) and client-based pool management via Notion.
=======
A FastAPI-based web service that generates performance reports for Balancer v2/v3 liquidity pools and anchor token lending markets. The service queries Balancer's GraphQL APIs to fetch pool metrics, compares current performance with data from 15 days ago, and sends beautifully styled reports via Telegram with visual change indicators and adaptive precision formatting.

## Key Features

- 📊 **Pool Performance Tracking**: Compare pool metrics (TVL, volume, fees, APR) with 15-day historical data
- ⚓ **Anchor Token Analysis**: Track lending market APYs and trading volumes for anchor tokens (USDC, WETH, etc.)
- 📈 **Multi-Pool Comparisons**: Analyze multiple pools with customizable ranking metrics
- 🤖 **Telegram Integration**: Receive formatted reports with visual cards directly in Telegram
- 💾 **CSV Export**: Generate CSV reports for anchor token lending markets (992+ markets tracked)
- 🔍 **Dune Analytics Integration**: Historical volume data from on-chain DEX aggregators

## New Features (Phases 1-8)

### 🚀 Boosted Pool Support (Phase 1 + Phase 8)
Automatically detects ERC-4626 boosted pools (like bb-a-USD) and extracts underlying tokens for accurate competitor analysis. **Phase 8 Enhancement**: Now uses Balancer API tags for more accurate detection (BOOSTED_AAVE, BOOSTED_EULER, etc.) with heuristic fallback. Supports Aave aTokens, Lido stETH, and other wrapped yield-bearing tokens.

**Boosted Pool Types Detected:**
- AAVE - Aave boosted pools
- EULER - Euler boosted pools  
- YEARN - Yearn boosted pools
- GEARBOX - Gearbox boosted pools
- BOOSTED - Generic boosted pools

### 📁 Data Export (Phase 2 + Phase 6)
Export comprehensive pool data to Excel or CSV for offline analysis and RAG model consumption:

**Formats:**
- **Excel (.xlsx)**: Multi-sheet workbook with metrics, hold vs pool, parameter changes
- **CSV (.csv)**: Flat structure for easy import to other tools

**Usage:**
```json
POST /report
{
  "pool_addresses": ["0x3de27efa2f1aa663ae5d458857e731c129069f29"],
  "anchor_token_address": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
  "recipient_email": "user@example.com",
  "telegram_chat_id": "123456789",
  "export_format": "both"
}
```

**Response:**
```json
{
  "status": "sent",
  "timestamp": "2026-02-11T18:30:00Z",
  "pool_name": "20wstETH-80AAVE",
  "pool_address": "0x3de27efa...",
  "export_files": {
    "excel": "exports/pool_0x3de27efa_20260211_183000.xlsx",
    "csv": "exports/pool_0x3de27efa_20260211_183000.csv"
  }
}
```

**Export Contents:**
- Basic pool metrics (TVL, volume, fees, APR)
- Hold vs Pool analysis (Phase 3)
- Parameter changes (Phase 4)
- Anchor token data (if provided)

**Multi-Pool Export** (Phase 6):
- ✅ Multi-pool export now fully supported
- ✅ Excel includes Pool Comparison, Rankings, Summary, and Anchor Token tabs
- ✅ CSV format for multi-pool data
- ✅ Automatic file naming with pool count (e.g., `PoolReport_3pools_USDC_timestamp.xlsx`)

### 💰 Hold vs Pool Analysis (Phase 3)
Compare LP returns against simply holding tokens:
- Trading fees earned from pool participation
- Incentives received (BAL, partner tokens)
- Impermanent loss calculated from price divergence
- Token appreciation tracked over time
- Clear recommendation: Hold or Pool

### 📅 Parameter Change Detection (Phase 4 + Phase 7)
Automatically detects and analyzes pool configuration changes with refined filtering:
- **Swap fee adjustments** - Tracks fee changes across all pool types
- **Weight changes (LBP pools only)** - Phase 7: Filters weight changes to Liquidity Bootstrapping Pools only (regular weighted pools have immutable weights)
- **Amp factor changes (Stable pools)** - Phase 7: Tracks amplification parameter updates in stable pools (AmpUpdateStarted, AmpUpdateStopped events)
- **Surge parameters (Stable Surge pools)** - Phase 7: Support for surge threshold and max surge fee tracking (when available in subgraph)
- Impact analysis: Compare metrics 7 days before/after changes
- Comprehensive change history with human-readable impact summaries
>>>>>>> @gbr/feat/takeaways

## Features

<<<<<<< HEAD
- **Telegram Bot Integration**: Request reports via Telegram commands
- **Multi-Chain Support**: Automatically detects blockchain from Balancer URLs
- **Client Management**: Manage clients and pools through Notion databases
- **User Whitelist**: Control access via Notion whitelist database
- **Performance Metrics**: TVL, volume, fees, APR comparisons over 15 days
- **Multi-Pool Reports**: Compare multiple pools with rankings
=======
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
>>>>>>> @gbr/feat/takeaways

### Anchor Token Metrics (NEW)
- **Lending Markets**: APYs from 990+ lending protocols (Aave, Morpho, Compound, etc.)
- **Trading Volume**: 30-day Balancer swap volume by chain/version/pair (via Dune Analytics)
- **Best Market Identification**: Automatically identifies highest-yield lending opportunity
- **CSV Export**: Generates `anchor_token_info.csv` with complete market data
- **Supported Tokens**: USDC, WETH, wstETH, DAI, USDT, WBTC, rETH, cbETH (extensible)

## Installation

### 1. Clone and Setup Python Environment

Create a virtual environment with Python 3.11:

```bash
python3.11 -m venv venv
source venv/bin/activate
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```env
<<<<<<< HEAD
# Telegram Bot Configuration (Required)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here

# Notion API Configuration (Required)
NOTION_API_KEY=your_notion_api_key_here

# SMTP Configuration (Optional - for email reports)
# SMTP_HOST=smtp.gmail.com
# SMTP_PORT=587
# SMTP_USERNAME=your_email@gmail.com
# SMTP_PASSWORD=your_app_password
# FROM_EMAIL=your_email@gmail.com
# ENABLE_EMAIL=true
=======
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
>>>>>>> @gbr/feat/takeaways
```

## Notion Setup

The application uses two Notion databases:

<<<<<<< HEAD
### 1. Pools Database
Create a Notion database with:
- **ID** (unique_id field)
- **Name** (title field) - Client name (e.g., "aave", "yuzu")
- **Pool addresses** (rollup/url field) - Balancer.fi URLs (e.g., `https://balancer.fi/pools/ethereum/v3/0x...`)

Update `POOLS_DATABASE_ID` in `services/notion.py` with your database ID.
=======
### Dune Analytics Setup (for Anchor Token Volume)

To enable historical volume tracking for anchor tokens:

1. Create a free account at [dune.com](https://dune.com)
2. Get your API key from [dune.com/settings/api](https://dune.com/settings/api)
3. Create a new query using the SQL template in `ANCHOR_TOKEN_SETUP.md`
4. Copy the Query ID from the URL (e.g., `https://dune.com/queries/123456` → ID is `123456`)
5. Add both to your `.env` file

**Note:** Volume tracking will be skipped if Dune credentials are not configured. Lending market data (DefiLlama) works independently.
>>>>>>> @gbr/feat/takeaways

### 2. Whitelist Database
Create a Notion database with:
- **username** (text field)
- **user_id** (number field) - Telegram user ID

Update `WHITELIST_DATABASE_ID` in `services/notion.py` with your database ID.

### Getting Notion Database IDs
1. Open your Notion database in a browser
2. The URL format is: `https://www.notion.so/{database_id}?v=...`
3. Copy the `database_id` (32 characters, with hyphens)

### Getting Notion API Key
1. Go to https://www.notion.so/my-integrations
2. Create a new integration
3. Copy the "Internal Integration Token"
4. Share your databases with the integration (click "..." → "Add connections")

## Telegram Bot Setup

### 1. Create Your Bot

1. Open Telegram and message [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the prompts
3. Copy the bot token and add it to `.env` as `TELEGRAM_BOT_TOKEN`

### 2. Configure Webhook

Once your FastAPI server is running:

```bash
curl -X POST "http://localhost:8000/telegram/setup-webhook?webhook_url=https://your-domain.com/telegram/webhook"
```

**For local development with ngrok:**
```bash
# Start ngrok
ngrok http 8000

# Use the ngrok URL for webhook
curl -X POST "http://localhost:8000/telegram/setup-webhook?webhook_url=https://your-ngrok-url.ngrok.io/telegram/webhook"
```

### 3. Whitelist Users

Add users to your Notion whitelist database with their Telegram `user_id` (users can get this by sending `/myid` to the bot).

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

<<<<<<< HEAD
### Telegram Bot Commands

- `/start` - Get your Telegram user ID and welcome message
- `/myid` - Get your Telegram user ID
- `{client_name}` - Request a report for a client (e.g., `aave`, `yuzu`)

### REST API Endpoint

You can also generate reports via REST API:
=======
### Generate a Single Pool Report with Anchor Token Analysis

Send a POST request to `/report` with one pool and an anchor token address.

For single-pool requests, the service:
- Fetches pool performance metrics (15-day comparison)
- Retrieves anchor token lending markets and trading volume
- Generates CSV export with complete anchor token data
- Sends a Telegram image card + markdown summary with anchor token info
>>>>>>> @gbr/feat/takeaways

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

<<<<<<< HEAD
=======
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

### Complete Analysis with All Features

Request comprehensive analysis with data export and advanced features:

```bash
curl -X POST "http://localhost:8000/report" \
  -H "Content-Type: application/json" \
  -d '{
    "pool_addresses": ["0x3de27efa2f1aa663ae5d458857e731c129069f29"],
    "anchor_token_address": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
    "export_format": "both",
    "recipient_email": "user@example.com",
    "telegram_chat_id": "123456789"
  }'
```

**New Parameters:**
- `export_format` (optional): `"excel"`, `"csv"`, or `"both"` - Generates downloadable reports
- Response includes `export_files` with paths to generated files

**Features Enabled:**
- ✅ Boosted pool detection (automatic)
- ✅ Hold vs Pool analysis (automatic for supported pools)
- ✅ Parameter change detection (automatic, 30-day lookback)
- ✅ Data export (when `export_format` specified)

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

>>>>>>> @gbr/feat/takeaways
## Project Structure

```
pool-report/
├── main.py                        # FastAPI application and Telegram webhook
├── config.py                      # Pydantic settings configuration
├── models.py                      # Pydantic request/response models
├── database.py                    # Compatibility shim
├── db/
│   └── notion_adapter.py         # Notion adapter (SQLAlchemy-compatible)
├── services/
│   ├── balancer_api.py            # Balancer API queries (multi-chain)
│   ├── metrics_calculator.py      # Metrics comparison logic
<<<<<<< HEAD
│   ├── email_sender.py            # SMTP email sending
│   ├── telegram_sender.py         # Telegram card generation
│   └── notion.py                  # Notion API integration
├── templates/
│   ├── email_report.html          # Single pool email template
│   ├── email_report_multi.html    # Multi-pool email template
│   ├── telegram_card.html         # Single pool Telegram card
│   └── telegram_card_multi.html   # Multi-pool Telegram card
├── requirements.txt               # Python dependencies
├── .env.example                   # Environment variables template
└── README.md                      # This file
```

## Multi-Chain Support

Pool URLs are automatically parsed to extract blockchain information:
- Format: `https://balancer.fi/pools/{blockchain}/{version}/{address}`
- Supported chains: Ethereum, Arbitrum, Polygon, Base, Plasma, and more
- The system automatically queries the correct chain API based on the URL
=======
│   ├── telegram_sender.py         # Telegram card generation and sending
│   ├── anchor_token_info.py       # Anchor token lending & volume data
│   ├── dune_metrics.py            # Dune Analytics integration
│   ├── insights_generator.py      # AI-powered insights generation
│   ├── boosted_pool_analyzer.py   # NEW: Boosted pool detection (Phase 1)
│   ├── data_exporter.py           # NEW: Excel/CSV export (Phase 2)
│   ├── coingecko_api.py           # NEW: CoinGecko price API (Phase 3)
│   ├── lp_return_calculator.py    # NEW: Hold vs Pool analysis (Phase 3)
│   └── pool_history_analyzer.py   # NEW: Parameter change detection (Phase 4)
├── templates/
│   ├── telegram_card.html         # Single pool Telegram card (with anchor info)
│   └── telegram_card_multi.html   # Multi-pool Telegram card (with anchor info)
├── scripts/                       # NEW: Testing and profiling scripts
│   ├── test_full_report.py        # Manual integration testing
│   └── profile_performance.py     # Performance profiling
├── tests/
│   ├── test_anchor_token_info.py  # Unit tests for anchor token service
│   ├── test_anchor_integration.py # Integration tests
│   ├── interactive_anchor_test.py # Manual testing script (generates CSV)
│   ├── test_boosted_pool_analyzer.py  # NEW: Phase 1 tests
│   ├── test_data_exporter.py          # NEW: Phase 2 tests
│   ├── test_lp_return_calculator.py   # NEW: Phase 3 tests
│   ├── test_pool_history_analyzer.py  # NEW: Phase 4 tests
│   └── test_full_integration.py       # NEW: Phase 5 integration tests
├── docs/                          # NEW: Feature documentation
│   └── NEW_FEATURES.md            # Comprehensive guide to Phases 1-4
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

### Run Phase-Specific Tests
```bash
# Phase 1 + 8: Boosted Pool Detection (with API tags support)
PYTHONPATH=. pytest tests/test_boosted_pool_analyzer.py -v

# Phase 2 + 6: Data Export (single + multi-pool)
PYTHONPATH=. pytest tests/test_data_exporter.py -v

# Phase 3: Hold vs Pool Analysis
PYTHONPATH=. pytest tests/test_lp_return_calculator.py -v

# Phase 4 + 7: Parameter Change Detection (refined filtering)
PYTHONPATH=. pytest tests/test_pool_history_analyzer.py -v

# Phase 5: Full Integration
PYTHONPATH=. pytest tests/test_full_integration.py -v
```

### Manual Integration Testing
```bash
# Test complete pipeline with real data
python scripts/test_full_report.py

# Profile performance
python scripts/profile_performance.py
```

**Current Test Coverage:**
- ✅ 33 boosted pool analyzer tests (Phase 1 + Phase 8)
- ✅ 15 data exporter tests (Phase 2 + Phase 6)
- ✅ 18 LP return calculator tests (Phase 3)
- ✅ 29 pool history analyzer tests (Phase 4 + Phase 7)
- ✅ 8 full integration tests (Phase 5)
- ✅ 11 anchor token tests (existing)
- **Total: 114+ tests**
>>>>>>> @gbr/feat/takeaways

## License

MIT
