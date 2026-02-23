"""Gmail SMTP client for sending HTML emails."""

from __future__ import annotations

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

GMAIL_SMTP_HOST = "smtp.gmail.com"
GMAIL_SMTP_PORT = 587


class SmtpClient:
    """Send emails via Gmail SMTP."""

    def __init__(
        self,
        smtp_user: str | None = None,
        smtp_password: str | None = None,
    ):
        self.smtp_user = smtp_user or os.environ.get("GMAIL_ADDRESS", "")
        self.smtp_password = smtp_password or os.environ.get("GMAIL_APP_PASSWORD", "")

        if not self.smtp_user or not self.smtp_password:
            logger.warning("GMAIL_ADDRESS or GMAIL_APP_PASSWORD not configured")

    def send(
        self,
        to: str,
        subject: str,
        body_html: str,
        body_text: str = "",
    ) -> bool:
        """Send an email.

        Args:
            to: Recipient email address.
            subject: Email subject.
            body_html: HTML body content.
            body_text: Plain text fallback (auto-generated from HTML if empty).

        Returns:
            True if sent successfully.
        """
        if not self.smtp_user or not self.smtp_password:
            logger.error("SMTP credentials not configured, skipping email")
            return False

        if not body_text:
            # Simple HTML to text fallback
            import re
            body_text = re.sub(r"<[^>]+>", "", body_html)

        msg = MIMEMultipart("alternative")
        msg["From"] = self.smtp_user
        msg["To"] = to
        msg["Subject"] = subject

        msg.attach(MIMEText(body_text, "plain", "utf-8"))
        msg.attach(MIMEText(body_html, "html", "utf-8"))

        try:
            with smtplib.SMTP(GMAIL_SMTP_HOST, GMAIL_SMTP_PORT) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(self.smtp_user, self.smtp_password)
                server.sendmail(self.smtp_user, to, msg.as_string())

            logger.info(f"Email sent to {to}: {subject}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email to {to}: {e}")
            return False
