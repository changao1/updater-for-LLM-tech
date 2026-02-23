"""Bilingual email sender: English to Email A, Chinese translation to Email B."""

from __future__ import annotations

import logging
import os

import markdown

from .smtp_client import SmtpClient
from .translator import Translator

logger = logging.getLogger(__name__)


def _markdown_to_html(md_text: str) -> str:
    """Convert Markdown text to HTML with a simple email-friendly wrapper."""
    try:
        html_body = markdown.markdown(
            md_text,
            extensions=["tables", "fenced_code"],
        )
    except Exception:
        # Fallback: wrap in <pre> if markdown conversion fails
        html_body = f"<pre>{md_text}</pre>"

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; line-height: 1.6; color: #24292e; max-width: 800px; margin: 0 auto; padding: 20px; }}
h1 {{ border-bottom: 1px solid #eaecef; padding-bottom: 0.3em; }}
h2 {{ border-bottom: 1px solid #eaecef; padding-bottom: 0.3em; margin-top: 24px; }}
h3 {{ margin-top: 16px; }}
blockquote {{ padding: 0 1em; color: #6a737d; border-left: 0.25em solid #dfe2e5; margin: 0 0 16px 0; }}
a {{ color: #0366d6; text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
code {{ background-color: #f6f8fa; padding: 0.2em 0.4em; border-radius: 3px; font-size: 85%; }}
hr {{ border: 0; border-top: 1px solid #eaecef; margin: 24px 0; }}
</style>
</head>
<body>
{html_body}
</body>
</html>"""


class BilingualSender:
    """Send bilingual emails: English to Email A list, Chinese to Email B list.

    Supports multiple recipients per language. Set EMAIL_EN / EMAIL_CN as
    comma-separated addresses (e.g. "a@example.com, b@example.com").
    """

    def __init__(
        self,
        email_en: str | list[str] | None = None,
        email_cn: str | list[str] | None = None,
        smtp_client: SmtpClient | None = None,
        translator: Translator | None = None,
    ):
        # Accept comma-separated strings or lists
        raw_en = email_en or os.environ.get("EMAIL_EN", "")
        raw_cn = email_cn or os.environ.get("EMAIL_CN", "")
        self.emails_en = SmtpClient._parse_recipients(raw_en)
        self.emails_cn = SmtpClient._parse_recipients(raw_cn)
        self.smtp = smtp_client or SmtpClient()
        self.translator = translator or Translator()

        if not self.emails_en:
            logger.warning("EMAIL_EN not configured")
        else:
            logger.info(f"English recipients: {self.emails_en}")
        if not self.emails_cn:
            logger.warning("EMAIL_CN not configured")
        else:
            logger.info(f"Chinese recipients: {self.emails_cn}")

    def send(
        self,
        content_md: str,
        subject: str,
        subject_prefix: str = "[LLM Update]",
    ) -> dict[str, bool]:
        """Send bilingual emails.

        Args:
            content_md: Markdown content (English).
            subject: Email subject (without prefix).
            subject_prefix: Prefix for the subject line.

        Returns:
            Dict with send status: {"en": bool, "cn": bool}.
        """
        results = {"en": False, "cn": False}
        full_subject_en = f"{subject_prefix} {subject}"

        # 1. Send English version to all EN recipients
        if self.emails_en:
            logger.info(f"Sending English email to {self.emails_en}")
            html_en = _markdown_to_html(content_md)
            results["en"] = self.smtp.send(
                to=self.emails_en,
                subject=full_subject_en,
                body_html=html_en,
                body_text=content_md,
            )
        else:
            logger.warning("Skipping English email: EMAIL_EN not configured")

        # 2. Translate to Chinese and send to all CN recipients
        if self.emails_cn:
            logger.info("Translating content to Chinese...")
            content_cn = self.translator.translate_to_chinese(content_md)
            full_subject_cn = f"{subject_prefix} {subject} (Chinese)"

            html_cn = _markdown_to_html(content_cn)
            results["cn"] = self.smtp.send(
                to=self.emails_cn,
                subject=full_subject_cn,
                body_html=html_cn,
                body_text=content_cn,
            )
        else:
            logger.warning("Skipping Chinese email: EMAIL_CN not configured")

        return results
