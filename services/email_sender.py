"""
Email sender service (stub implementation).

NOTE: Email functionality has been deprecated in favor of Telegram-only workflow.
This module provides a stub implementation to maintain backward compatibility
with existing code that references EmailSender.

For sending reports, use TelegramSender instead.
"""


class EmailSenderError(Exception):
    """Exception raised when email sending fails."""
    pass


class EmailSender:
    """
    Stub email sender that maintains API compatibility but does not send emails.
    
    This class is kept for backward compatibility with existing code.
    All email functionality has been moved to Telegram-based delivery.
    """
    
    def __init__(self):
        """Initialize email sender (disabled by default)."""
        self.enabled = False
        print("ℹ️  Email functionality is disabled. Using Telegram for all reports.")
    
    async def send_pool_report(
        self,
        recipient_email: str,
        pool_name: str,
        metrics_data: dict,
        multi_pool: bool = False
    ) -> None:
        """
        Stub method for sending pool reports via email.
        
        This method does nothing and is kept only for API compatibility.
        Use TelegramSender.send_pool_report() instead.
        
        Args:
            recipient_email: Email address (ignored)
            pool_name: Name of the pool (ignored)
            metrics_data: Metrics data dictionary (ignored)
            multi_pool: Whether this is a multi-pool report (ignored)
        """
        print(f"ℹ️  Email sending is disabled. Recipient {recipient_email} would have received report for {pool_name}")
