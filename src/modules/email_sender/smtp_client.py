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

    @staticmethod
    def _parse_recipients(to: str | list[str]) -> list[str]:
        """Parse recipient(s) into a flat list of email addresses.

        Supports:
            - Single address: "a@example.com"
            - Comma-separated string: "a@example.com, b@example.com"
            - List of addresses: ["a@example.com", "b@example.com"]

        Returns:
            List of stripped, non-empty email addresses.
        """
        if isinstance(to, str):
            addresses = to.split(",")
        else:
            addresses = to
        return [addr.strip() for addr in addresses if addr.strip()]

    def send(
        self,
        to: str | list[str],
        subject: str,
        body_html: str,
        body_text: str = "",
    ) -> bool:
        """Send an email to one or more recipients.

        Args:
            to: Recipient email address(es). Accepts a single address,
                a comma-separated string, or a list of addresses.
            subject: Email subject.
            body_html: HTML body content.
            body_text: Plain text fallback (auto-generated from HTML if empty).

        Returns:
            True if sent successfully to all recipients.
        """
        if not self.smtp_user or not self.smtp_password:
            logger.error("SMTP credentials not configured, skipping email")
            return False

        recipients = self._parse_recipients(to)
        if not recipients:
            logger.error("No valid recipients provided, skipping email")
            return False

        if not body_text:
            # Simple HTML to text fallback
            import re
            body_text = re.sub(r"<[^>]+>", "", body_html)

        msg = MIMEMultipart("alternative")
        msg["From"] = self.smtp_user
        msg["To"] = ", ".join(recipients)
        msg["Subject"] = subject

        msg.attach(MIMEText(body_text, "plain", "utf-8"))
        msg.attach(MIMEText(body_html, "html", "utf-8"))

        try:
            with smtplib.SMTP(GMAIL_SMTP_HOST, GMAIL_SMTP_PORT) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(self.smtp_user, self.smtp_password)
                server.sendmail(self.smtp_user, recipients, msg.as_string())

            logger.info(f"Email sent to {recipients}: {subject}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email to {recipients}: {e}")
            return False
