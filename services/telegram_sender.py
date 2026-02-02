import os
import httpx
from jinja2 import Environment, FileSystemLoader
from html2image import Html2Image
from config import settings

class TelegramSender:
    def __init__(self):
        self.bot_token = settings.telegram_bot_token
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        self.api_url = f"{self.base_url}/sendPhoto"
        
        # Try to configure the screenshot tool (might not be available in some environments)
        try:
            # Check if we're on Render or similar environment with Chromium installed
            chromium_path = self._find_chromium()
            if chromium_path:
                self.hti = Html2Image(
                    output_path="temp_images", 
                    size=(800, 1400),
                    browser_executable=chromium_path
                )
            else:
                self.hti = Html2Image(output_path="temp_images", size=(800, 1400))
            
            self.image_support = True
            print(f"✅ Image generation enabled (Chrome: {chromium_path or 'auto-detected'})")
        except Exception as e:
            print(f"⚠️  Image generation not available: {e}")
            print("📝 Will send text-only Telegram messages")
            self.hti = None
            self.image_support = False
        
        # Setup template environment
        self.template_env = Environment(loader=FileSystemLoader("templates"))
        
        # Ensure temp directory exists
        os.makedirs("temp_images", exist_ok=True)

    def _find_chromium(self):
        """Find Chromium executable in common locations."""
        import shutil
        
        # Common Chromium paths on different systems
        chromium_paths = [
            '/usr/bin/chromium',           # Render/Ubuntu
            '/usr/bin/chromium-browser',   # Alternative Ubuntu
            '/usr/bin/google-chrome',      # If Chrome is installed instead
            shutil.which('chromium'),      # Try PATH
            shutil.which('chromium-browser'),
            shutil.which('google-chrome'),
        ]
        
        for path in chromium_paths:
            if path and os.path.exists(path):
                return path
        
        return None
    
    async def send_message(self, chat_id: str, text: str):
        """
        Send a simple text message to a Telegram chat.
        Used for responding to bot commands like /start and /myid.
        """
        url = f"{self.base_url}/sendMessage"
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown"
            })
            
            if response.status_code == 200:
                print(f"✅ Telegram message sent to chat {chat_id}")
            else:
                print(f"❌ Failed to send Telegram message: {response.text}")
            
            return response

    async def send_pool_report(self, pool_data: dict, metrics_data: dict, chat_id: str):
        """
        Generates an image card and sends it to Telegram with Markdown text.
        Falls back to text-only if image generation is not available.
        
        Args:
            pool_data: Pool information dictionary
            metrics_data: Formatted metrics dictionary
            chat_id: Chat ID to send to (required)
        """
        try:
            target_chat_id = chat_id
            
            # If image generation is not available, send text-only message
            if not self.image_support:
                print("📝 Sending text-only Telegram message...")
                caption = (
                    f"💎 *Pool Performance Update*\n"
                    f"*{metrics_data.get('pool_name', 'Unknown Pool')}*\n\n"
                    f"💰 *TVL:* {metrics_data.get('tvl_current', 'N/A')} ({metrics_data.get('tvl_change_percent', '0%')})\n"
                    f"📊 *Volume (15d):* {metrics_data.get('volume_15d', 'N/A')} ({metrics_data.get('volume_change_percent', '0%')})\n"
                    f"💸 *Fees (15d):* {metrics_data.get('fees_15d', 'N/A')} ({metrics_data.get('fees_change_percent', '0%')})\n"
                    f"🚀 *APR:* {metrics_data.get('apr_current', 'N/A')}\n\n"
                    f"[🔗 View Pool on Balancer]({metrics_data.get('pool_url', '#')})"
                )
                await self.send_message(str(target_chat_id), caption)
                return
            
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
            caption_lines = [
                f"💎 *Pool Performance Update*",
                f"*{metrics_data.get('pool_name', 'Unknown Pool')}*\n",
                f"💰 *TVL:* {metrics_data.get('tvl_current', 'N/A')} ({metrics_data.get('tvl_change_percent', '0%')})",
                f"📊 *Volume (15d):* {metrics_data.get('volume_15d', 'N/A')}",
                f"💸 *Fees (15d):* {metrics_data.get('fees_15d', 'N/A')}",
                f"📈 *Swap Fee Rate (24h):* {metrics_data.get('volume_fees_ratio_24h', 'N/A')}",
            ]
            
            # Add alert if swap fee changed (15 days comparison)
            if metrics_data.get('volume_fees_ratio_has_changed'):
                change_percent = metrics_data.get('volume_fees_ratio_change_percent', 'N/A')
                value_15d = metrics_data.get('volume_fees_ratio_24h_15d_ago', 'N/A')
                value_now = metrics_data.get('volume_fees_ratio_24h', 'N/A')
                
                if metrics_data.get('volume_fees_ratio_increased'):
                    caption_lines.append("")
                    caption_lines.append("✏️ *Parameter Changes*")
                    caption_lines.append(f"SwapFee:")
                    caption_lines.append(f"📈 Increased by {change_percent}")
                    caption_lines.append(f"15 days ago: {value_15d} → Now: {value_now}")
                elif metrics_data.get('volume_fees_ratio_decreased'):
                    caption_lines.append("")
                    caption_lines.append("✏️ *Parameter Changes*")
                    caption_lines.append(f"SwapFee:")
                    caption_lines.append(f"📉 Decreased by {change_percent}")
                    caption_lines.append(f"15 days ago: {value_15d} → Now: {value_now}")
            
            # Add alert if swap fee changed vs 30-day average
            if metrics_data.get('volume_fees_ratio_30d_has_changed'):
                change_30d_percent = metrics_data.get('volume_fees_ratio_30d_change_percent', 'N/A')
                avg_30d = metrics_data.get('volume_fees_ratio_30d_avg', 'N/A')
                value_now_30d = metrics_data.get('volume_fees_ratio_24h', 'N/A')
                
                if metrics_data.get('volume_fees_ratio_30d_increased'):
                    caption_lines.append("")
                    caption_lines.append("✏️ *Parameter Changes*")
                    caption_lines.append(f"SwapFee:")
                    caption_lines.append(f"📈 Increased by {change_30d_percent} (vs 30d average)")
                    caption_lines.append(f"30-day average: {avg_30d} → Now: {value_now_30d}")
                elif metrics_data.get('volume_fees_ratio_30d_decreased'):
                    caption_lines.append("")
                    caption_lines.append("✏️ *Parameter Changes*")
                    caption_lines.append(f"SwapFee:")
                    caption_lines.append(f"📉 Decreased by {change_30d_percent} (vs 30d average)")
                    caption_lines.append(f"30-day average: {avg_30d} → Now: {value_now_30d}")
            
            caption_lines.extend([
                f"\n🚀 *APR:* {metrics_data.get('apr_current', 'N/A')}\n",
                f"[🔗 View Pool on Balancer]({metrics_data.get('pool_url', '#')})"
            ])
            
            caption = "\n".join(caption_lines)

            # 4. Send to Telegram
            print(f"✈️ Sending to Telegram Chat ID: {target_chat_id}...")
            async with httpx.AsyncClient() as client:
                with open(image_path, "rb") as img_file:
                    response = await client.post(
                        self.api_url,
                        data={"chat_id": target_chat_id, "caption": caption, "parse_mode": "Markdown"},
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
            import traceback
            error_msg = str(e) if str(e) else repr(e)
            print(f"❌ Error in TelegramSender: {error_msg}")
            print(f"   Traceback: {traceback.format_exc()}")

    async def send_multi_pool_report(self, metrics_data: dict, chat_id: str):
        """
        Generates a multi-pool comparison image card and sends it to Telegram with Markdown text.
        Falls back to text-only if image generation is not available.
        Expects metrics_data to match MetricsCalculator.format_multi_pool_metrics_for_email output.
        
        Args:
            metrics_data: Formatted multi-pool metrics dictionary
            chat_id: Chat ID to send to (required)
        """
        try:
            target_chat_id = chat_id
            caption_lines = []  # Initialize early to avoid UnboundLocalError
            
            # If image generation is not available, send text-only message
            if not self.image_support:
                print("📝 Sending text-only Telegram multi-pool message...")
                caption_lines = [
                    "📊 *Pools Comparison Update*",
                    f"*{metrics_data.get('pool_count', 0)} Pools • 15-Day Analysis*",
                    "",
                    f"💰 *Total Fees (15d):* {metrics_data.get('total_fees', 'N/A')}",
                    f"🚀 *Weighted Avg APR:* {metrics_data.get('total_apr', 'N/A')}",
                ]
                
                # Show each pool with all its metrics (compact format with labels)
                pools = metrics_data.get("pools", [])
                if pools:
                    caption_lines.append("")
                    for idx, pool in enumerate(pools, 1):
                        # Compact format: Pool name on one line, metrics on next lines
                        pool_name = pool.get('name', 'Unknown')
                        # Truncate long pool names to avoid exceeding Telegram limit
                        if len(pool_name) > 50:
                            pool_name = pool_name[:47] + "..."
                        caption_lines.append(f"*{idx}. {pool_name}*")
                        caption_lines.append(
                            f"💎 TVL: {pool.get('tvl')} ({pool.get('tvl_change')}) | "
                            f"🏆 Vol: {pool.get('volume')} ({pool.get('volume_change')})"
                        )
                        caption_lines.append(
                            f"🚀 APR: {pool.get('apr')} | "
                            f"📈 Swap Fee: {pool.get('swap_fee')}"
                        )
                    
                    # Add alerts for pools with significant swap fee changes (compact)
                    pools_with_changes = [p for p in pools if p.get('swap_fee_changed', False)]
                    if pools_with_changes:
                        caption_lines.append("")
                        caption_lines.append("✏️ *Parameter Changes*")
                        for p in pools_with_changes:
                            change_percent = p.get('swap_fee_change', 'N/A')
                            if change_percent and change_percent != 'N/A':
                                direction = "📈" if '+' in str(change_percent) else "📉"
                                pool_name = p.get('name', 'Unknown')
                                if len(pool_name) > 40:
                                    pool_name = pool_name[:37] + "..."
                                caption_lines.append(
                                    f"{direction} {pool_name}: {change_percent} "
                                    f"({p.get('swap_fee_15d_ago', 'N/A')} → {p.get('swap_fee', 'N/A')})"
                                )
                
                caption = "\n".join(caption_lines)
                await self.send_message(str(target_chat_id), caption)
                return
            
            print("🎨 Generating Telegram multi-pool report card...")

            # 1. Render HTML for the Image
            template = self.template_env.get_template("telegram_card_multi.html")
            html_content = template.render(**metrics_data)

            # 2. Convert HTML to PNG Image
            image_filename = f"report_multi_{metrics_data.get('pool_count', 'n')}.png"
            self.hti.screenshot(html_str=html_content, save_as=image_filename)
            image_path = os.path.join("temp_images", image_filename)

            # 3. Prepare Markdown Caption (compact format to avoid Telegram length limit)
            caption_lines = [
                "📊 *Pools Comparison Update*",
                f"*{metrics_data.get('pool_count', 0)} Pools • 15-Day Analysis*",
                "",
                f"💰 *Total Fees (15d):* {metrics_data.get('total_fees', 'N/A')}",
                f"🚀 *Weighted Avg APR:* {metrics_data.get('total_apr', 'N/A')}",
            ]

            # Show each pool with all its metrics (compact format with labels)
            pools = metrics_data.get("pools", [])
            if pools:
                caption_lines.append("")
                for idx, pool in enumerate(pools, 1):
                    # Compact format: Pool name on one line, metrics on next lines
                    pool_name = pool.get('name', 'Unknown')
                    # Truncate long pool names to avoid exceeding Telegram limit
                    if len(pool_name) > 50:
                        pool_name = pool_name[:47] + "..."
                    caption_lines.append(f"*{idx}. {pool_name}*")
                    caption_lines.append(
                        f"💎 TVL: {pool.get('tvl')} ({pool.get('tvl_change')}) | "
                        f"🏆 Vol: {pool.get('volume')} ({pool.get('volume_change')})"
                    )
                    caption_lines.append(
                        f"🚀 APR: {pool.get('apr')} | "
                        f"📈 Swap Fee: {pool.get('swap_fee')}"
                    )
                
                # Add alerts for pools with significant swap fee changes (compact)
                pools_with_changes = [p for p in pools if p.get('swap_fee_changed', False)]
                if pools_with_changes:
                    caption_lines.append("")
                    caption_lines.append("✏️ *Parameter Changes*")
                    for p in pools_with_changes:
                        change_percent = p.get('swap_fee_change', 'N/A')
                        if change_percent and change_percent != 'N/A':
                            direction = "📈" if '+' in str(change_percent) else "📉"
                            pool_name = p.get('name', 'Unknown')
                            if len(pool_name) > 40:
                                pool_name = pool_name[:37] + "..."
                            caption_lines.append(
                                f"{direction} {pool_name}: {change_percent} "
                                f"({p.get('swap_fee_15d_ago', 'N/A')} → {p.get('swap_fee', 'N/A')})"
                            )

            caption = "\n".join(caption_lines)

            # 4. Send to Telegram
            print(f"✈️ Sending multi-pool card to Telegram Chat ID: {target_chat_id}...")
            async with httpx.AsyncClient() as client:
                with open(image_path, "rb") as img_file:
                    response = await client.post(
                        self.api_url,
                        data={"chat_id": target_chat_id, "caption": caption, "parse_mode": "Markdown"},
                        files={"photo": img_file}
                    )

                if response.status_code == 200:
                    print("✅ Telegram multi-pool message sent successfully!")
                else:
                    print(f"❌ Failed to send Telegram multi-pool message: {response.text}")

            # Cleanup
            if os.path.exists(image_path):
                os.remove(image_path)

        except Exception as e:
            import traceback
            error_msg = str(e) if str(e) else repr(e)
            print(f"❌ Error in TelegramSender (multi-pool): {error_msg}")
            print(f"   Traceback: {traceback.format_exc()}")