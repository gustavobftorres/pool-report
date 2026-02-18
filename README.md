# Balancer Pool Performance Reporter

A FastAPI-based web service that generates performance reports for Balancer v2/v3 liquidity pools and anchor token lending markets. The service queries Balancer's GraphQL APIs to fetch pool metrics, compares current performance with data from 15 days ago, and sends styled reports via Telegram with visual change indicators.

## Installation

### 1. Clone and Setup

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env`:

```env
# Balancer APIs
BALANCER_V3_API=https://api-v3.balancer.fi/
BALANCER_V2_SUBGRAPH=https://api.studio.thegraph.com/query/24617/balancer-v2
BALANCER_GQL_ENDPOINT=https://gateway-arbitrum.network.thegraph.com/api/YOUR_API_KEY/subgraphs/id/YOUR_SUBGRAPH_ID

# Telegram (Required)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_default_chat_id    # Optional default

# Dune Analytics (for anchor token volume data)
DUNE_API_KEY=your_dune_api_key
DUNE_ANCHOR_VOLUME_QUERY_ID=6664013
DUNE_QUERY_PERFORMANCE=medium    # low, medium, high
DUNE_QUERY_TIMEOUT=60.0

# Notion (for client/pool management and user whitelist)
NOTION_API_KEY=your_notion_api_key_here
```

### 3. Notion Setup

The application uses two Notion databases:

**Pools Database** — create with these fields:
- `ID` (unique_id)
- `Name` (title) — client name, e.g. "aave"
- `Pool addresses` (rollup/url) — Balancer.fi URLs, e.g. `https://balancer.fi/pools/ethereum/v3/0x...`

**Whitelist Database** — create with:
- `username` (text)
- `user_id` (number) — Telegram user ID

Update `POOLS_DATABASE_ID` and `WHITELIST_DATABASE_ID` in `services/notion.py`.

**Getting a Notion database ID:** open the database in a browser — the URL is `https://www.notion.so/{database_id}?v=...`

**Getting a Notion API key:** go to https://www.notion.so/my-integrations, create an integration, copy the token, then share each database with the integration.

### 4. Telegram Bot Setup

1. Message [@BotFather](https://t.me/BotFather) → `/newbot` → copy the token into `TELEGRAM_BOT_TOKEN`
2. Once the server is running, set up the webhook:

```bash
curl -X POST "http://localhost:8000/telegram/setup-webhook?webhook_url=https://your-domain.com/telegram/webhook"
```

For local development with ngrok:
```bash
ngrok http 8000
curl -X POST "http://localhost:8000/telegram/setup-webhook?webhook_url=https://your-ngrok-url.ngrok.io/telegram/webhook"
```

3. Add users to the Notion whitelist with their Telegram `user_id` (users can get theirs by sending `/myid` to the bot).

### 5. Dune Analytics Setup (for Anchor Token Volume)

1. Create an account at [dune.com](https://dune.com) and get your API key from [dune.com/settings/api](https://dune.com/settings/api)
2. Create a query using the SQL template in `ANCHOR_TOKEN_SETUP.md`
3. Copy the Query ID from the URL and add it to `.env` as `DUNE_ANCHOR_VOLUME_QUERY_ID`

Volume tracking is skipped gracefully if Dune credentials are not configured. Lending market data (DefiLlama) works independently.

## Running the Server

```bash
uvicorn main:app --reload
```

API docs available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Telegram Bot Commands

- `/start` — Get your Telegram user ID and welcome message
- `/myid` — Get your Telegram user ID
- `{client_name}` — Request a report for a client (e.g., `aave`, `yuzu`)

## Project Structure

```
pool-report/
├── main.py                         # FastAPI app and Telegram webhook
├── config.py                       # Pydantic settings
├── models.py                       # Pydantic request/response models
├── database.py                     # Compatibility shim
├── db/
│   └── notion_adapter.py           # Notion adapter
├── services/
│   ├── balancer_api.py             # Balancer API queries (multi-chain)
│   ├── metrics_calculator.py       # Metrics comparison logic
│   ├── telegram_sender.py          # Telegram card generation and sending
│   ├── anchor_token_info.py        # Anchor token lending & volume data
│   ├── dune_metrics.py             # Dune Analytics integration
│   ├── insights_generator.py       # AI-powered insights generation
│   ├── boosted_pool_analyzer.py    # Boosted pool detection
│   ├── data_exporter.py            # Excel/CSV export
│   ├── coingecko_api.py            # CoinGecko price API
│   ├── lp_return_calculator.py     # Hold vs Pool analysis
│   ├── pool_history_analyzer.py    # Parameter change detection
│   └── notion.py                   # Notion API integration
├── templates/
│   ├── telegram_card.html          # Single pool Telegram card
│   └── telegram_card_multi.html    # Multi-pool Telegram card
├── scripts/
│   ├── test_full_report.py         # Manual integration testing
│   └── profile_performance.py      # Performance profiling
├── tests/
│   ├── test_anchor_token_info.py
│   ├── test_anchor_integration.py
│   ├── interactive_anchor_test.py
│   ├── test_boosted_pool_analyzer.py
│   ├── test_data_exporter.py
│   ├── test_lp_return_calculator.py
│   ├── test_pool_history_analyzer.py
│   └── test_full_integration.py
├── docs/
│   └── NEW_FEATURES.md
├── requirements.txt
├── .env.example
├── ANCHOR_TOKEN_SETUP.md
└── README.md
```

## Testing

```bash
# All tests
PYTHONPATH=. ./venv/bin/pytest -v

# By feature area
PYTHONPATH=. pytest tests/test_boosted_pool_analyzer.py -v   # Boosted pool detection
PYTHONPATH=. pytest tests/test_data_exporter.py -v           # Data export
PYTHONPATH=. pytest tests/test_lp_return_calculator.py -v    # Hold vs Pool
PYTHONPATH=. pytest tests/test_pool_history_analyzer.py -v   # Parameter changes
PYTHONPATH=. pytest tests/test_full_integration.py -v        # Full integration
PYTHONPATH=. pytest tests/test_anchor*.py -v                 # Anchor token

# Manual integration test with real data
python scripts/test_full_report.py
```

**Test coverage:** 114+ tests across all feature areas.
