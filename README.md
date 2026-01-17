# Balancer Pool Performance Reporter

A FastAPI-based web service that generates and emails performance reports for Balancer v2/v3 liquidity pools. The service queries Balancer's GraphQL APIs to fetch pool metrics and compares current performance with data from 15 days ago.

## Features

- 📊 **Works with Both V2 and V3 Pools** - Automatically detects pool version
- 📈 Compares current metrics with 15-day historical data
- 📧 Sends beautifully styled HTML email reports matching balancer.fi design
- 🚀 FastAPI with automatic API documentation
- ⚡ Async/await for efficient API calls
- 🔒 Type-safe with Pydantic models
- 🔄 Smart fallback: Tries V3 API first, then V2 Subgraph

## Metrics Tracked

- **TVL (Total Value Locked)**: Current vs 15 days ago with % change
- **Volume**: Total swap volume over the last 15 days
- **Fees**: Total fees collected over the last 15 days
- **APR**: Current Annual Percentage Rate

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
BALANCER_V3_API=https://api-v3.balancer.fi/graphql
BALANCER_V2_SUBGRAPH=https://api.thegraph.com/subgraphs/name/balancer-labs/balancer-v2
DEFAULT_CHAIN=MAINNET
```

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

### Generate a Report

Send a POST request to `/report`:

```bash
curl -X POST "http://localhost:8000/report" \
  -H "Content-Type: application/json" \
  -d '{
    "pool_address": "0x3de27efa2f1aa663ae5d458857e731c129069f29",
    "recipient_email": "your.email@example.com"
  }'
```

Or use the interactive Swagger UI at `/docs` to test the endpoint.

### Health Check

```bash
curl http://localhost:8000/health
```

## API Endpoints

### POST /report

Generate and send a pool performance report via email.

**Request Body:**
```json
{
  "pool_address": "0x3de27efa2f1aa663ae5d458857e731c129069f29",
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
│   └── email_sender.py       # SMTP email sending
├── templates/
│   └── email_report.html     # Balancer-styled email template
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

- [ ] Support for multiple pools in a single report
- [ ] Add charts and visualizations
- [ ] Store historical reports in a database
- [ ] Scheduled reports (daily/weekly cron jobs)
- [ ] Support for multiple email recipients
- [ ] Webhook notifications
- [ ] WebSocket support for real-time updates

## License

MIT

## Support

For issues or questions, please open an issue on the repository.
