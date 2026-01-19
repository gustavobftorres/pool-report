# Deploy to Render

## Quick Start (10 minutes)

### Option 1: Using render.yaml (Recommended)

**Step 1: Push to GitHub**
```bash
git add .
git commit -m "Add Render configuration"
git push
```

**Step 2: Create Render Account**
1. Go to https://render.com
2. Sign up with GitHub

**Step 3: Deploy**
1. Click "New +" → "Blueprint"
2. Connect your GitHub repository
3. Render will detect `render.yaml` and create:
   - ✅ Web Service (FastAPI)
   - ✅ PostgreSQL Database
4. Click "Apply"

**Step 4: Set Secret Environment Variables**

Render will ask you to set these (they're marked as `sync: false` in render.yaml):

```
SMTP_HOST = smtp.gmail.com
SMTP_USERNAME = your_email@gmail.com
SMTP_PASSWORD = your_app_password
FROM_EMAIL = your_email@gmail.com
TELEGRAM_BOT_TOKEN = your_bot_token
TELEGRAM_CHAT_ID = your_default_chat_id
```

**Step 5: Wait for Deployment**
- First deploy takes ~5 minutes
- Watch logs in Render dashboard
- Your app URL: `https://pool-report-api.onrender.com`

**Step 6: Initialize Database**

Use Render Shell:
1. Go to your web service in Render dashboard
2. Click "Shell" tab
3. Run:
   ```bash
   python init_db.py
   ```

**Step 7: Configure Telegram Webhook**
```bash
curl -X POST "https://pool-report-api.onrender.com/telegram/setup-webhook?webhook_url=https://pool-report-api.onrender.com/telegram/webhook"
```

---

### Option 2: Manual Setup (More Control)

**Step 1: Create Web Service**
1. Go to Render Dashboard
2. Click "New +" → "Web Service"
3. Connect GitHub repo
4. Configure:
   - **Name**: pool-report-api
   - **Region**: Oregon (or closest to you)
   - **Branch**: main
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Plan**: Free

**Step 2: Add Environment Variables**

In "Environment" tab, add:
```
PYTHON_VERSION = 3.11.0
SMTP_HOST = smtp.gmail.com
SMTP_PORT = 587
SMTP_USERNAME = your_email@gmail.com
SMTP_PASSWORD = your_app_password
FROM_EMAIL = your_email@gmail.com
BALANCER_V3_API = https://api-v3.balancer.fi/
BALANCER_V2_SUBGRAPH = https://api.studio.thegraph.com/query/24660/balancer-ethereum-v2/version/latest
DEFAULT_CHAIN = MAINNET
BLOCKCHAIN_NAME = ethereum
TELEGRAM_BOT_TOKEN = your_bot_token
TELEGRAM_CHAT_ID = your_default_chat_id
```

**Step 3: Create PostgreSQL Database**
1. Click "New +" → "PostgreSQL"
2. Configure:
   - **Name**: pool-report-db
   - **Database**: pool_report
   - **User**: pool_report_user
   - **Plan**: Free
3. Click "Create Database"

**Step 4: Link Database to Web Service**
1. Go back to your web service
2. Environment tab → Add environment variable:
   - **Key**: `DATABASE_URL`
   - **Value**: Click "Add from database" → Select pool-report-db → Connection String (Internal)

**Step 5: Deploy & Initialize**
1. Click "Manual Deploy" → "Deploy latest commit"
2. Wait for deployment
3. Use Shell to run `python init_db.py`

---

## Deploy Streamlit to Render (Alternative to Streamlit Cloud)

If you want to deploy Streamlit to Render instead of Streamlit Cloud:

**Create another Web Service:**
1. New + → Web Service
2. Same repo
3. Configure:
   - **Name**: pool-report-admin
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `streamlit run admin_ui.py --server.port $PORT --server.address 0.0.0.0`
   - **Plan**: Free

**Add Environment Variables:**
```
DATABASE_URL = [same as FastAPI service]
API_URL = https://pool-report-api.onrender.com
```

---

## Free Tier Limitations

**Render Free Tier:**
- ✅ 750 hours/month per service
- ✅ Auto-sleep after 15 minutes of inactivity
- ⚠️ First request after sleep takes ~30 seconds
- ✅ PostgreSQL 90 days retention
- ✅ 1GB storage

**How to handle auto-sleep:**
- Use a cron job or uptime monitor to ping your API every 10 minutes
- Upgrade to paid plan ($7/month) for always-on

---

## Alternative: Use Managed Database Separately

If Render's database limitations are an issue, use a separate managed database:

### Option A: Supabase (Recommended)

**Setup:**
1. Go to https://supabase.com
2. Create new project
3. Get connection string from Settings → Database
4. Use this as `DATABASE_URL` in both Render and Streamlit

**Benefits:**
- ✅ Free tier: 500MB storage, unlimited API requests
- ✅ No auto-sleep
- ✅ Auto-backups
- ✅ Can access from anywhere

### Option B: Neon (Serverless PostgreSQL)

**Setup:**
1. Go to https://neon.tech
2. Create new project
3. Copy connection string
4. Use as `DATABASE_URL`

**Benefits:**
- ✅ Serverless (auto-scales)
- ✅ 3GB free tier
- ✅ Branch databases for testing
- ✅ Fast cold starts

---

## Deployment with Supabase Database

**Architecture:**
```
┌─────────────────────┐
│   Render (FastAPI)  │
│  your-app.onrender  │
└─────────┬───────────┘
          │
          ↓
┌─────────────────────┐
│ Supabase (Database) │
│   Free PostgreSQL   │
└─────────┬───────────┘
          │
          ↓
┌─────────────────────┐
│ Streamlit Cloud/    │
│ Render (Admin UI)   │
└─────────────────────┘
```

**Steps:**
1. Create Supabase project
2. Deploy FastAPI to Render with Supabase DATABASE_URL
3. Deploy Streamlit with same DATABASE_URL
4. Initialize database locally:
   ```bash
   DATABASE_URL="postgresql://..." python init_db.py
   ```

---

## Render vs Railway Comparison

| Feature | Render | Railway |
|---------|--------|---------|
| Free Tier | 750 hrs/month | $5 credit/month |
| Auto-sleep | Yes (15 min) | No |
| Cold Start | ~30 sec | Instant |
| Ease of Use | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Documentation | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| PostgreSQL | 90 days retention | Persistent |
| Pricing | $7/month starter | $5/month usage |

---

## Troubleshooting

**Service won't start:**
- Check logs in Render dashboard
- Verify Python version in environment variables
- Check requirements.txt has all dependencies

**Database connection fails:**
- Verify DATABASE_URL is set correctly
- Use "Internal Connection String" (not external)
- Check database is in same region

**Cold starts are slow:**
- Normal for free tier (first request takes ~30s)
- Consider paid plan ($7/month) for always-on
- Or use uptime monitor to keep it awake

**Streamlit can't connect to API:**
- Verify API_URL in environment variables
- Check API service is running
- Test API endpoint directly first

---

## Cost Comparison

**All Free:**
- Render FastAPI: Free (750 hrs)
- Supabase DB: Free (500MB)
- Streamlit Cloud: Free
- **Total: $0/month**

**Always-On Production:**
- Render FastAPI: $7/month
- Supabase DB: Free or $25/month (Pro)
- Streamlit Cloud: Free
- **Total: $7-32/month**

---

## Next Steps

1. Choose deployment option:
   - [ ] Render Blueprint (easiest)
   - [ ] Render Manual
   - [ ] Render + Supabase
   
2. Follow steps above

3. Initialize database

4. Configure Telegram webhook

5. Deploy Streamlit admin UI

6. Test everything!

---

## Support

- Render Docs: https://render.com/docs
- Render Community: https://community.render.com
- Supabase Docs: https://supabase.com/docs
- Neon Docs: https://neon.tech/docs
