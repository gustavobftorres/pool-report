import os
import httpx
from jinja2 import Environment, FileSystemLoader
from html2image import Html2Image
from config import settings

class TelegramSender:
    def __init__(self):
        self.bot_token = settings.telegram_bot_token
        self.chat_id = settings.telegram_chat_id
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}/sendPhoto"
        
        # Configure the screenshot tool (size matches the HTML/CSS)
        self.hti = Html2Image(output_path="temp_images", size=(800, 1400))
        
        # Setup template environment
        self.template_env = Environment(loader=FileSystemLoader("templates"))
        
        # Ensure temp directory exists
        os.makedirs("temp_images", exist_ok=True)

    async def send_pool_report(self, pool_data: dict, metrics_data: dict):
        """
        Generates an image card and sends it to Telegram with Markdown text.
        """
        try:
            print("🎨 Generating Telegram report card...")
            
            # 1. Render HTML for the Image
            full_context = {**pool_data, **metrics_data}
            template = self.template_env.get_template("telegram_card.html")
            html_content = template.render(full_context)
            
            # 2. Convert HTML to PNG Image
            # Using pool ID in filename to avoid conflicts
            image_filename = f"report_{metrics_data.get('pool_id', 'temp')}.png"
            self.hti.screenshot(html_str=html_content, save_as=image_filename)
            image_path = os.path.join("temp_images", image_filename)
            
            # 3. Prepare Markdown Caption
            # Simple Markdown formatting for Telegram
            caption = (
                f"💎 *Pool Performance Update*\n"
                f"*{metrics_data.get('pool_name', 'Unknown Pool')}*\n\n"
                f"💰 *TVL:* {metrics_data.get('tvl_current', 'N/A')} ({metrics_data.get('tvl_change_percent', '0%')})\n"
                f"📊 *Volume (15d):* {metrics_data.get('volume_15d', 'N/A')}\n"
                f"💸 *Fees (15d):* {metrics_data.get('fees_15d', 'N/A')}\n"
                f"🚀 *APR:* {metrics_data.get('apr_current', 'N/A')}\n\n"
                f"[🔗 View Pool on Balancer]({metrics_data.get('pool_url', '#')})"
            )

            # 4. Send to Telegram
            print(f"✈️ Sending to Telegram Chat ID: {self.chat_id}...")
            async with httpx.AsyncClient() as client:
                with open(image_path, "rb") as img_file:
                    response = await client.post(
                        self.api_url,
                        data={"chat_id": self.chat_id, "caption": caption, "parse_mode": "Markdown"},
                        files={"photo": img_file}
                    )
                    
                if response.status_code == 200:
                    print("✅ Telegram message sent successfully!")
                else:
                    print(f"❌ Failed to send Telegram message: {response.text}")

            # Cleanup: Remove the temp image
            if os.path.exists(image_path):
                os.remove(image_path)
                
        except Exception as e:
            print(f"❌ Error in TelegramSender: {str(e)}")