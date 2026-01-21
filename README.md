# Balancer Pool Performance Reporter

A FastAPI-based Telegram bot that generates and sends performance reports for Balancer v2/v3 liquidity pools. The service queries Balancer's GraphQL APIs to fetch pool metrics, compares current performance with data from 15 days ago, and sends reports via Telegram with visual cards and markdown summaries. Supports multi-chain pools (Ethereum, Arbitrum, Plasma, etc.) and client-based pool management via Notion.

## Features

- **Telegram Bot Integration**: Request reports via Telegram commands
- **Multi-Chain Support**: Automatically detects blockchain from Balancer URLs
- **Client Management**: Manage clients and pools through Notion databases
- **User Whitelist**: Control access via Notion whitelist database
- **Performance Metrics**: TVL, volume, fees, APR comparisons over 15 days
- **Multi-Pool Reports**: Compare multiple pools with rankings

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
```

## Notion Setup

The application uses two Notion databases:

### 1. Pools Database
Create a Notion database with:
- **ID** (unique_id field)
- **Name** (title field) - Client name (e.g., "aave", "yuzu")
- **Pool addresses** (rollup/url field) - Balancer.fi URLs (e.g., `https://balancer.fi/pools/ethereum/v3/0x...`)

Update `POOLS_DATABASE_ID` in `services/notion.py` with your database ID.

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

### Telegram Bot Commands

- `/start` - Get your Telegram user ID and welcome message
- `/myid` - Get your Telegram user ID
- `{client_name}` - Request a report for a client (e.g., `aave`, `yuzu`)

### REST API Endpoint

You can also generate reports via REST API:

```bash
curl -X POST "http://localhost:8000/report" \
  -H "Content-Type: application/json" \
  -d '{
    "pool_addresses": ["0x3de27efa2f1aa663ae5d458857e731c129069f29"],
    "recipient_email": "your.email@example.com",
    "telegram_chat_id": "123456789"
  }'
```

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

## License

MIT
