"""
Email sender service for sending pool performance reports via SMTP.
"""
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
        
        # Set up Jinja2 environment for template rendering
        template_dir = Path(__file__).parent.parent / "templates"
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(['html', 'xml'])
        )
    
    def render_report_email(self, metrics_data: Dict[str, Any]) -> str:
        """
        Render the email report HTML from template with metrics data.
        
        Args:
            metrics_data: Dictionary containing formatted metrics for the template
            
        Returns:
            Rendered HTML string
        """
        try:
            template = self.jinja_env.get_template("email_report.html")
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
        try:
            # Create message
            message = MIMEMultipart('alternative')
            message['Subject'] = subject
            message['From'] = self.from_email
            message['To'] = recipient_email
            
            # Attach HTML content
            html_part = MIMEText(html_content, 'html')
            message.attach(html_part)
            
            # Send email via SMTP
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(message)
            
            print(f"Email sent successfully to {recipient_email}")
            
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
        metrics_data: Dict[str, Any]
    ) -> None:
        """
        Send a complete pool performance report email.
        
        Args:
            recipient_email: Email address of the recipient
            pool_name: Name of the pool for the subject line
            metrics_data: Dictionary containing formatted metrics
        """
        # Render the email HTML
        html_content = self.render_report_email(metrics_data)
        
        # Create subject line
        subject = f"Balancer Pool Report: {pool_name}"
        
        # Send the email
        await self.send_report_email(recipient_email, subject, html_content)
