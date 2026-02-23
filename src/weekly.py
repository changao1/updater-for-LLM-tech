"""Weekly summary entry point.

Aggregates items from daily Issues over the past week,
ranks them, creates a weekly summary Issue, and sends bilingual emails.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import yaml

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.modules.weekly_summary.aggregator import aggregate_weekly
from src.modules.weekly_summary.ranker import rank_items
from src.modules.weekly_summary.formatter import format_weekly_summary
from src.notifiers.github_issue import create_issue
from src.state.run_logger import append_run_record
from src.modules.email_sender.bilingual import BilingualSender

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def main():
    # Load settings
    config_dir = PROJECT_ROOT / "config"
    settings_path = config_dir / "settings.yaml"
    with open(settings_path, "r") as f:
        settings = yaml.safe_load(f)

    issue_settings = settings.get("issue", {})
    email_settings = settings.get("email", {})
    weekly_settings = settings.get("weekly_summary", {})

    lookback_days = weekly_settings.get("lookback_days", 7)
    top_n = weekly_settings.get("top_n", 20)
    daily_label = issue_settings.get("daily_labels", ["daily-update"])[0]

    # Track stats and errors for run log
    run_errors: list[str] = []
    issue_url = None
    email_results = {"en": False, "cn": False}

    # ── Aggregate ────────────────────────────────────────────────────────
    logger.info(f"=== Aggregating items from the last {lookback_days} days ===")
    items = aggregate_weekly(label=daily_label, days=lookback_days)

    if not items:
        logger.warning("No items found to aggregate.")

    # ── Rank ─────────────────────────────────────────────────────────────
    logger.info("=== Ranking items ===")
    top_items = rank_items(items, top_n=top_n)

    # ── Format ───────────────────────────────────────────────────────────
    logger.info("=== Formatting weekly summary ===")
    issue_title, issue_body = format_weekly_summary(
        top_items, lookback_days=lookback_days
    )

    # ── Create GitHub Issue ──────────────────────────────────────────────
    logger.info("=== Creating weekly summary Issue ===")
    labels = issue_settings.get("weekly_labels", ["weekly-summary"])
    issue_url = create_issue(title=issue_title, body=issue_body, labels=labels)

    if issue_url:
        logger.info(f"Weekly summary Issue created: {issue_url}")
    else:
        logger.warning("Failed to create weekly summary Issue")
        run_errors.append("Failed to create weekly summary Issue")

    # ── Send bilingual email ─────────────────────────────────────────────
    if email_settings.get("enabled") and email_settings.get("weekly_enabled"):
        logger.info("=== Sending weekly summary emails ===")
        try:
            sender = BilingualSender()
            subject_prefix = email_settings.get("subject_prefix", "[LLM Update]")
            email_results = sender.send(
                content_md=issue_body,
                subject=issue_title,
                subject_prefix=subject_prefix,
            )
            logger.info(f"Email results: EN={email_results['en']}, CN={email_results['cn']}")
        except Exception as e:
            logger.error(f"Email sending failed: {e}")
            run_errors.append(f"Email sending failed: {e}")
    else:
        logger.info("Email sending disabled in settings")

    # ── Append run log ───────────────────────────────────────────────────
    logger.info("=== Writing run log ===")
    try:
        append_run_record(
            run_type="weekly",
            collected={"aggregated_items": len(items)},
            after_dedup={"unique_items": len(items)},
            after_filter={"top_items": len(top_items)},
            issue_url=issue_url,
            email_results=email_results,
            errors=run_errors,
        )
    except Exception as e:
        logger.error(f"Failed to write run log: {e}")

    logger.info("=== Weekly summary completed ===")
    return len(top_items)


if __name__ == "__main__":
    count = main()
    sys.exit(0)
