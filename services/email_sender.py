"""
Email sender service for sending pool performance reports via SMTP.
"""
import asyncio
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
from typing import Dict, Any
from config import settings


class EmailSenderError(Exception):
    """Custom exception for email sending errors."""
    pass


class EmailSender:
    """Service for sending HTML emails via SMTP."""
    
    def __init__(self):
        self.smtp_host = settings.smtp_host
        self.smtp_port = settings.smtp_port
        self.smtp_username = settings.smtp_username
        self.smtp_password = settings.smtp_password
        self.from_email = settings.from_email
        self.enabled = bool(
            settings.enable_email
            and self.smtp_host
            and self.smtp_port
            and self.smtp_username
            and self.smtp_password
            and self.from_email
        )
        
        # Set up Jinja2 environment for template rendering
        template_dir = Path(__file__).parent.parent / "templates"
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(['html', 'xml'])
        )
    
    def render_report_email(self, metrics_data: Dict[str, Any], multi_pool: bool = False) -> str:
        """
        Render the email report HTML from template with metrics data.
        
        Args:
            metrics_data: Dictionary containing formatted metrics for the template
            multi_pool: If True, use multi-pool template; otherwise use single pool template
            
        Returns:
            Rendered HTML string
        """
        try:
            template_name = "email_report_multi.html" if multi_pool else "email_report.html"
            template = self.jinja_env.get_template(template_name)
            html_content = template.render(**metrics_data)
            return html_content
        except Exception as e:
            raise EmailSenderError(f"Error rendering email template: {str(e)}")
    
    async def send_report_email(
        self,
        recipient_email: str,
        subject: str,
        html_content: str
    ) -> None:
        """
        Send an HTML email report via SMTP.
        
        Args:
            recipient_email: Email address of the recipient
            subject: Email subject line
            html_content: HTML content of the email
            
        Raises:
            EmailSenderError: If email sending fails
        """
        if not self.enabled:
            print("ℹ️  Email sending disabled or SMTP not configured; skipping email.")
            return

        def _send_sync() -> None:
            # Create message
            message = MIMEMultipart('alternative')
            message['Subject'] = subject
            message['From'] = self.from_email
            message['To'] = recipient_email

            # Attach HTML content
            html_part = MIMEText(html_content, 'html')
            message.attach(html_part)

            # Send email via SMTP (explicit timeout to avoid long hangs)
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=15) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(message)

        try:
            # Run SMTP in a thread so we don't block the FastAPI event loop.
            await asyncio.to_thread(_send_sync)
            print(f"✅ Email sent successfully to {recipient_email}")
        except smtplib.SMTPAuthenticationError:
            raise EmailSenderError(
                "SMTP authentication failed. Please check your username and password."
            )
        except smtplib.SMTPException as e:
            raise EmailSenderError(f"SMTP error occurred: {str(e)}")
        except Exception as e:
            raise EmailSenderError(f"Error sending email: {str(e)}")
    
    async def send_pool_report(
        self,
        recipient_email: str,
        pool_name: str,
        metrics_data: Dict[str, Any],
        multi_pool: bool = False
    ) -> None:
        """
        Send a complete pool performance report email.
        
        Args:
            recipient_email: Email address of the recipient
            pool_name: Name of the pool (or description for multi-pool)
            metrics_data: Dictionary containing formatted metrics
            multi_pool: If True, send multi-pool comparison report
        """
        # Render the email HTML
        html_content = self.render_report_email(metrics_data, multi_pool=multi_pool)
        
        # Create subject line
        if multi_pool:
            subject = f"Balancer Pools Comparison Report ({metrics_data.get('pool_count', 0)} Pools)"
        else:
            subject = f"Balancer Pool Report: {pool_name}"
        
        # Send the email
        await self.send_report_email(recipient_email, subject, html_content)
