# 🚂 Deploy to Railway - Complete Guide

Railway is a modern deployment platform with excellent Python support and automatic PostgreSQL provisioning.

## 📋 Prerequisites

1. **Railway Account**: Sign up at [railway.app](https://railway.app)
2. **GitHub Account**: Your code needs to be in a GitHub repository
3. **Supabase PostgreSQL** (already set up) OR Railway's PostgreSQL (we'll add it)

---

## 🚀 Deployment Steps

### Step 1: Push Your Code to GitHub

```bash
cd /Users/gustavotorres/Desktop/Projects/personal/pool-report

# Add new files
git add railway.json nixpacks.toml admin_ui.py RAILWAY_DEPLOYMENT.md

# Commit
git commit -m "feat: Add Railway deployment configuration"

# Push
git push origin main
```

### Step 2: Create New Project on Railway

1. Go to [railway.app](https://railway.app)
2. Click **"New Project"**
3. Select **"Deploy from GitHub repo"**
4. **Authorize Railway** to access your GitHub
5. Select your **`pool-report`** repository
6. Railway will automatically detect Python and start building

### Step 3: Add Environment Variables

Once deployed, click on your service, then go to **Variables** tab:

#### Required Variables:

```bash
# Database (use your existing Supabase)
DATABASE_URL=postgresql://postgres.[ref]:[password]@aws-0-us-west-1.pooler.supabase.com:6543/postgres

# Balancer API
BALANCER_GQL_ENDPOINT=https://gateway-arbitrum.network.thegraph.com/api/[YOUR-API-KEY]/subgraphs/id/[SUBGRAPH-ID]
BALANCER_V3_API=https://api-v3.balancer.fi/
BALANCER_V2_SUBGRAPH=https://api.studio.thegraph.com/query/24660/balancer-ethereum-v2/version/latest

# Blockchain
DEFAULT_CHAIN=MAINNET
BLOCKCHAIN_NAME=ethereum

# Telegram Bot
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather

# Email (SMTP) - Optional for now
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password
FROM_EMAIL=your_email@gmail.com
```

#### Optional Variables:
```bash
TELEGRAM_CHAT_ID=  # Leave empty, managed per-user now
PYTHON_VERSION=3.11.0
```

### Step 4: Get Your Railway URL

After deployment completes:

1. Go to your service **Settings** tab
2. Scroll to **Networking** section
3. Click **Generate Domain**
4. Copy your URL (e.g., `https://pool-report-api-production.up.railway.app`)

### Step 5: Configure Telegram Webhook

Update your webhook to point to Railway:

```bash
curl -X POST "https://YOUR-RAILWAY-URL.railway.app/telegram/setup-webhook?webhook_url=https://YOUR-RAILWAY-URL.railway.app/telegram/webhook"
```

### Step 6: Update Streamlit Environment Variable

In your Streamlit Cloud settings, update:

```bash
API_URL=https://YOUR-RAILWAY-URL.railway.app
```

### Step 7: Initialize Database Tables

Run once to create tables:

```bash
# Using Railway CLI (install: npm i -g @railway/cli)
railway run python init_db.py

# OR make a temporary curl request that triggers DB connection
curl https://YOUR-RAILWAY-URL.railway.app/health
```

---

## ✅ Verify Deployment

### Test Health Endpoint
```bash
curl https://YOUR-RAILWAY-URL.railway.app/health
```

Expected response:
```json
{
  "status": "healthy",
  "timestamp": "2026-01-19T..."
}
```

### Test API Docs
Visit: `https://YOUR-RAILWAY-URL.railway.app/docs`

### Test Telegram Bot
1. Send `/start` to your Telegram bot
2. Bot should respond with your user ID
3. Check Streamlit UI - user should appear

---

## 🎯 Railway Advantages Over Render

✅ **No cold starts** on paid plans ($5/month)
✅ **Faster deployments** (typically 1-2 minutes)
✅ **Better logs** with real-time streaming
✅ **Built-in PostgreSQL** (if you want to switch from Supabase)
✅ **More generous free tier** ($5 credit/month)
✅ **Automatic HTTPS** and custom domains
✅ **Better developer experience** overall

---

## 🔧 Troubleshooting

### Issue: Build Fails with Chromium Error

**Solution**: Railway will automatically install Chromium via `nixpacks.toml`. If it fails:
- Check the build logs for specific errors
- Verify `nixpacks.toml` is in the root directory

### Issue: Database Connection Errors

**Solution**: 
- Verify `DATABASE_URL` is correct
- Use Supabase's **Connection Pooler** URL (port 6543)
- Check if Supabase IP allowlist includes Railway's IPs (usually not needed)

### Issue: Telegram Webhook Not Working

**Solution**:
1. Verify `TELEGRAM_BOT_TOKEN` is set correctly
2. Re-run the webhook setup curl command
3. Check webhook status:
   ```bash
   curl https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getWebhookInfo
   ```

### Issue: App Crashes on Startup

**Solution**:
- Check Railway logs (click on your service → Deployments → View logs)
- Most common: missing environment variable
- Verify all required env vars are set

---

## 💰 Railway Pricing

### Free Tier
- ✅ $5 credit/month (enough for small projects)
- ✅ Auto-sleeps after inactivity (like Render)
- ✅ 500 hours/month execution time

### Starter Plan ($5/month)
- ✅ $5 credit + $5 included usage = $10 total
- ✅ **No sleeping** (always on!)
- ✅ Better performance
- **Recommended for production**

### Pro Plan ($20/month)
- ✅ $20 credit + team features
- ✅ Priority support
- ✅ Higher resource limits

---

## 📊 Monitoring

Railway provides:
- **Real-time logs** (better than Render)
- **Metrics** (CPU, Memory, Network)
- **Deployments history**
- **Health checks** (automatic)

Access all in your service dashboard.

---

## 🔄 CI/CD

Railway automatically deploys when you push to your repository:

1. `git push origin main`
2. Railway detects the push
3. Automatically builds and deploys
4. Your service is updated (with zero-downtime for paid plans)

---

## 📝 Next Steps

1. ✅ Deploy to Railway (follow steps above)
2. ✅ Update Streamlit `API_URL`
3. ✅ Configure Telegram webhook
4. ✅ Test sending a report
5. 🎉 You're done!

---

## 🆘 Need Help?

- **Railway Docs**: https://docs.railway.app
- **Railway Discord**: https://discord.gg/railway
- **This project's GitHub**: Create an issue if you encounter problems

---

**Deployment should take ~5 minutes total!** 🚂💨
