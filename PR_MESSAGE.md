# Improve Pool Reports: Email Redesign + Telegram Integration

## Summary

This PR modernizes the email report templates, adds Telegram delivery for both single-pool and multi-pool reports, and enhances the FastAPI service with better lifecycle management and API discovery. The changes improve user experience across multiple communication channels while maintaining backward compatibility.

## Key Changes

### 📧 Email Report Redesign

- **Single Pool Template (`templates/email_report.html`)**
  - Complete visual redesign with responsive layout
  - Modern gradient header aligned with Balancer branding
  - Dark theme (#31363F) with improved contrast and readability
  - Enhanced card-based layout for TVL, volume, fees, and APR metrics
  - Better spacing and visual hierarchy, especially for the "Current APR" section
  - Improved mobile responsiveness with media queries
  - Email client compatibility improvements (color-scheme meta tags, semantic HTML structure)

- **Multi-Pool Template (`templates/email_report_multi.html`)**
  - Maintained existing comparison report functionality
  - Consistent styling with single-pool template

### ✈️ Telegram Integration

- **New Service (`services/telegram_sender.py`)**
  - `TelegramSender` class for sending rich report cards via Telegram Bot API
  - HTML-to-image conversion using `html2image` library
  - Support for both single-pool and multi-pool report cards
  - Markdown-formatted captions with key metrics and pool links

- **New Templates**
  - `templates/telegram_card.html` - Single pool Telegram card
  - `templates/telegram_card_multi.html` - Multi-pool comparison Telegram card

- **Configuration**
  - Added `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` environment variables
  - Updated `config.py` to load Telegram settings

### 🚀 API Enhancements (`main.py`)

- **New Root Endpoint (`GET /`)**
  - Returns API metadata and available endpoints
  - Useful for API discovery and documentation

- **Lifecycle Management**
  - Implemented `lifespan` context manager for startup/shutdown events
  - Logs configuration details (Balancer API endpoints, email sender) on startup
  - Clean shutdown logging

- **Enhanced `/report` Endpoint Behavior**
  - **Single pool requests**: Sends HTML email report + Telegram card (image + markdown)
  - **Multiple pool requests**: Sends HTML email comparison report + Telegram multi-pool card
  - Improved logging throughout the report generation process
  - Better error handling with global exception handler

### 📚 Documentation Updates (`README.md`)

- Updated features list to include Telegram integration
- Added Telegram configuration section with environment variables
- Clarified behavior differences between single-pool and multi-pool reports
- Updated API endpoint documentation
- Added `telegram_sender.py` to project structure
- Updated Balancer API endpoint URLs in configuration examples

## Technical Details

### Dependencies

- Added `html2image` for HTML-to-image conversion
- Added `httpx` for async HTTP requests to Telegram Bot API

### Configuration

New environment variables required:
```env
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### Report Delivery Flow

**Single Pool:**
1. Calculate metrics for the pool
2. Format data for email template
3. Send HTML email to `recipient_email`
4. Generate Telegram card image
5. Send Telegram card with markdown caption

**Multiple Pools:**
1. Calculate metrics for all pools
2. Rank pools by volume and TVL growth
3. Format aggregated data for email template
4. Send HTML email comparison report to `recipient_email`
5. Generate multi-pool Telegram card image
6. Send Telegram card with markdown summary

## Testing

### Prerequisites

1. Configure `.env` with valid SMTP credentials
2. Set up Telegram bot:
   - Create a bot via [@BotFather](https://t.me/botfather)
   - Obtain bot token
   - Get chat ID (private chat or group/channel)
   - Add bot to the chat if using group/channel

### Test Single Pool Report

```bash
curl -X POST "http://localhost:8000/report" \
  -H "Content-Type: application/json" \
  -d '{
    "pool_addresses": ["0x3de27efa2f1aa663ae5d458857e731c129069f29"],
    "recipient_email": "your.email@example.com"
  }'
```

**Expected Results:**
- ✅ HTML email received in inbox
- ✅ Telegram card image received in configured chat
- ✅ Logs show both email and Telegram delivery success

### Test Multi-Pool Report

```bash
curl -X POST "http://localhost:8000/report" \
  -H "Content-Type: application/json" \
  -d '{
    "pool_addresses": [
      "0x3de27efa2f1aa663ae5d458857e731c129069f29",
      "0x5c6ee304399dbdb9c8ef030ab642b10820db8f56"
    ],
    "recipient_email": "your.email@example.com"
  }'
```

**Expected Results:**
- ✅ HTML email comparison report received
- ✅ Telegram multi-pool card received in configured chat
- ✅ Rankings and aggregated metrics displayed correctly

### Test Root Endpoint

```bash
curl http://localhost:8000/
```

**Expected Response:**
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

## Breaking Changes

**None** - All changes are backward compatible. Existing API consumers will continue to work without modification.

## Migration Notes

- If you want to use Telegram features, add the new environment variables to your `.env` file
- Telegram delivery is optional - if not configured, only email reports will be sent
- The email template changes are visual only and don't affect the data structure

## Files Changed

- `main.py` - API enhancements, lifecycle management, Telegram integration
- `services/telegram_sender.py` - New Telegram service
- `services/email_sender.py` - No changes (maintained for compatibility)
- `templates/email_report.html` - Complete redesign
- `templates/telegram_card.html` - New single-pool Telegram card
- `templates/telegram_card_multi.html` - New multi-pool Telegram card
- `config.py` - Added Telegram configuration
- `README.md` - Updated documentation
- `requirements.txt` - Added `html2image` and `httpx` dependencies

## Future Enhancements

- [ ] Add support for scheduled reports via Telegram
- [ ] Implement report history/storage
- [ ] Add interactive buttons in Telegram messages
- [ ] Support for multiple Telegram chat recipients
- [ ] Webhook notifications

---

**Ready for Review** ✅
