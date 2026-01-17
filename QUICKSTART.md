# 🚀 Quick Start Guide

Get your Balancer Pool Reporter up and running in 3 minutes!

## Prerequisites

- Python 3.11 or higher
- pip (Python package manager)

## Step 0: Set Up Python 3.11 Environment (If Needed)

If you need to recreate the virtual environment with Python 3.11:

```bash
./setup_python311.sh
```

This will:
- Remove the old virtual environment
- Create a new one with Python 3.11
- Install all dependencies

## Step 1: Configure SMTP Settings

Copy the example environment file and add your email credentials:

```bash
cp .env.example .env
```

Then edit `.env` and add your SMTP credentials:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password
FROM_EMAIL=your_email@gmail.com
```

### Gmail Setup (Recommended)

1. Enable 2-factor authentication on your Google account
2. Go to https://myaccount.google.com/apppasswords
3. Select "Mail" and your device
4. Copy the 16-character password
5. Paste it as `SMTP_PASSWORD` in your `.env` file

## Step 2: Test the API (Optional)

Before starting the server, test that the Balancer API integration works:

```bash
source venv/bin/activate
python test_api.py
```

You should see output like:
```
🧪 Testing Balancer API Integration
✅ Pool Name: [Pool Name]
✅ Current TVL: $X,XXX,XXX.XX
...
```

## Step 3: Start the Server

### Option A: Use the start script (Recommended)

```bash
./start.sh
```

### Option B: Manual start

```bash
source venv/bin/activate
python main.py
```

### Option C: Using uvicorn directly

```bash
source venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Step 4: Test the API

Once the server is running, open your browser:

**📚 API Documentation (Swagger UI)**
```
http://localhost:8000/docs
```

**🏥 Health Check**
```
http://localhost:8000/health
```

## Step 5: Send Your First Report!

### Using Swagger UI (Easiest)

1. Go to http://localhost:8000/docs
2. Click on `POST /report` → "Try it out"
3. Enter:
```json
{
  "pool_address": "0x3de27efa2f1aa663ae5d458857e731c129069f29",
  "recipient_email": "your.email@example.com"
}
```
4. Click "Execute"
5. Check your email! 📧

### Using curl

```bash
curl -X POST "http://localhost:8000/report" \
  -H "Content-Type: application/json" \
  -d '{
    "pool_address": "0x3de27efa2f1aa663ae5d458857e731c129069f29",
    "recipient_email": "your.email@example.com"
  }'
```

## What You'll Get

An email with a beautiful Balancer-styled report showing:

- 📊 **TVL**: Current vs 15 days ago with % change
- 💰 **Volume**: Total trading volume over 15 days
- 💵 **Fees**: Total fees collected over 15 days
- 📈 **APR**: Current annual percentage rate

## Project Structure

```
pool-report/
├── main.py                   # FastAPI app (start here)
├── config.py                 # Configuration
├── models.py                 # Data models
├── services/
│   ├── balancer_api.py       # Balancer GraphQL queries
│   ├── metrics_calculator.py # Metrics logic
│   └── email_sender.py       # Email sending
├── templates/
│   └── email_report.html     # Email template
├── test_api.py               # Test script
├── start.sh                  # Quick start script
├── requirements.txt          # Dependencies
└── .env                      # Your config (create this!)
```

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | API information |
| `/health` | GET | Health check |
| `/report` | POST | Generate and send report |
| `/docs` | GET | Swagger UI |
| `/redoc` | GET | ReDoc documentation |

## Troubleshooting

### "SMTP authentication failed"
- Use an App Password (Gmail) not your regular password
- Check username and password in `.env`

### "Pool not found"
- Verify the pool address is correct (42 characters starting with 0x)
- Pool must exist on the specified chain (MAINNET by default)

### "No historical snapshots found"
- Pool might be very new
- V2 subgraph might not have data for V3-only pools

### Server won't start
- Check if port 8000 is already in use
- Try: `uvicorn main:app --port 8001`

## Need More Help?

See `TESTING.md` for detailed testing instructions and troubleshooting.

## What's Next?

- 🔄 Set up scheduled reports (cron job)
- 🎨 Customize the email template
- 📊 Add more pools to monitor
- 🚀 Deploy to production (Heroku, AWS, etc.)
- 💾 Add database for historical reports

---

**Ready to go!** 🎉

Start the server with `./start.sh` and visit http://localhost:8000/docs
