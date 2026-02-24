"""Daily update entry point.

Collects data from all sources, filters by keyword relevance,
deduplicates, creates a GitHub Issue, and sends bilingual emails.
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

from src.collectors import arxiv_collector, github_collector, pwc_collector
from src.filters.keyword_filter import filter_items, load_keywords
from src.formatters.issue_formatter import format_daily_issue
from src.notifiers.github_issue import create_issue
from src.state.dedup import DedupStore
from src.state.run_logger import append_run_record
from src.modules.email_sender.bilingual import BilingualSender
from src.modules.summarizer import Summarizer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def load_config(config_dir: Path) -> dict:
    """Load all configuration files."""
    configs = {}
    for name in ["keywords", "sources", "settings"]:
        path = config_dir / f"{name}.yaml"
        with open(path, "r") as f:
            configs[name] = yaml.safe_load(f)
    return configs


def main():
    config_dir = PROJECT_ROOT / "config"
    configs = load_config(config_dir)

    sources = configs["sources"]
    settings = configs["settings"]
    filter_settings = settings.get("filter", {})
    issue_settings = settings.get("issue", {})
    email_settings = settings.get("email", {})

    min_score = filter_settings.get("min_score", 1.0)
    max_items = filter_settings.get("max_items_per_source", 15)

    # Load keyword categories
    keywords = load_keywords(str(config_dir / "keywords.yaml"))

    # Initialize dedup store
    dedup = DedupStore(
        retention_days=settings.get("dedup", {}).get("retention_days", 30)
    )

    # Track stats and errors for run log
    run_errors: list[str] = []
    issue_url = None
    email_results = {"en": False, "cn": False}

    # ── Collect ──────────────────────────────────────────────────────────
    logger.info("=== Starting data collection ===")

    # arXiv
    logger.info("Collecting from arXiv...")
    arxiv_papers = []
    try:
        arxiv_papers = arxiv_collector.collect(sources.get("arxiv", {}))
    except Exception as e:
        logger.error(f"arXiv collection failed: {e}")
        run_errors.append(f"arXiv collection failed: {e}")

    # GitHub
    logger.info("Collecting from GitHub...")
    github_items = []
    try:
        github_token = os.environ.get("GITHUB_TOKEN", "")
        github_items = github_collector.collect(sources.get("github", {}), github_token)
    except Exception as e:
        logger.error(f"GitHub collection failed: {e}")
        run_errors.append(f"GitHub collection failed: {e}")

    # Papers with Code
    logger.info("Collecting from Papers with Code...")
    pwc_papers = []
    try:
        pwc_papers = pwc_collector.collect(sources.get("papers_with_code", {}))
    except Exception as e:
        logger.error(f"Papers with Code collection failed: {e}")
        run_errors.append(f"Papers with Code collection failed: {e}")

    collected_stats = {
        "arxiv": len(arxiv_papers),
        "github": len(github_items),
        "pwc": len(pwc_papers),
    }
    logger.info(
        f"Collected: {collected_stats['arxiv']} arXiv, "
        f"{collected_stats['github']} GitHub, "
        f"{collected_stats['pwc']} PWC"
    )

    # ── Dedup ────────────────────────────────────────────────────────────
    logger.info("=== Deduplicating ===")
    arxiv_papers = dedup.filter_unseen(arxiv_papers)
    github_items = dedup.filter_unseen(github_items)
    pwc_papers = dedup.filter_unseen(pwc_papers)

    dedup_stats = {
        "arxiv": len(arxiv_papers),
        "github": len(github_items),
        "pwc": len(pwc_papers),
    }

    # ── Filter ───────────────────────────────────────────────────────────
    logger.info("=== Filtering by keyword relevance ===")
    arxiv_filtered = filter_items(arxiv_papers, keywords, min_score)[:max_items]
    github_filtered = filter_items(github_items, keywords, min_score)[:max_items]
    pwc_filtered = filter_items(pwc_papers, keywords, min_score)[:max_items]

    filter_stats = {
        "arxiv": len(arxiv_filtered),
        "github": len(github_filtered),
        "pwc": len(pwc_filtered),
    }
    total = sum(filter_stats.values())
    logger.info(
        f"After filtering: {filter_stats['arxiv']} arXiv, "
        f"{filter_stats['github']} GitHub, "
        f"{filter_stats['pwc']} PWC "
        f"(total: {total})"
    )

    # ── Summarize ─────────────────────────────────────────────────────────
    logger.info("=== Generating bilingual summaries ===")
    try:
        all_filtered = arxiv_filtered + github_filtered + pwc_filtered
        summarizer = Summarizer()
        summarizer.summarize(all_filtered)
    except Exception as e:
        logger.error(f"Summarization failed (will use truncated abstracts): {e}")
        run_errors.append(f"Summarization failed: {e}")

    # ── Format ───────────────────────────────────────────────────────────
    logger.info("=== Formatting issue ===")
    issue_title, issue_body = format_daily_issue(
        arxiv_filtered, github_filtered, pwc_filtered, lang="en"
    )
    # Generate CN version with Chinese summaries for the CN email
    _, issue_body_cn = format_daily_issue(
        arxiv_filtered, github_filtered, pwc_filtered, lang="cn"
    )

    # ── Create GitHub Issue ──────────────────────────────────────────────
    logger.info("=== Creating GitHub Issue ===")
    labels = issue_settings.get("daily_labels", ["daily-update"])
    issue_url = create_issue(title=issue_title, body=issue_body, labels=labels)

    if issue_url:
        logger.info(f"Issue created: {issue_url}")
    else:
        logger.warning("Failed to create Issue (may be running locally without GITHUB_TOKEN)")
        run_errors.append("Failed to create GitHub Issue")

    # ── Send bilingual email ─────────────────────────────────────────────
    if email_settings.get("enabled") and email_settings.get("daily_enabled"):
        logger.info("=== Sending bilingual emails ===")
        try:
            sender = BilingualSender()
            subject_prefix = email_settings.get("subject_prefix", "[LLM Update]")
            email_results = sender.send(
                content_md=issue_body,
                subject=issue_title,
                subject_prefix=subject_prefix,
                content_cn=issue_body_cn,
            )
            logger.info(f"Email results: EN={email_results['en']}, CN={email_results['cn']}")
        except Exception as e:
            logger.error(f"Email sending failed: {e}")
            run_errors.append(f"Email sending failed: {e}")
    else:
        logger.info("Email sending disabled in settings")

    # ── Save dedup state ─────────────────────────────────────────────────
    logger.info("=== Saving dedup state ===")
    dedup.save()

    # ── Append run log ───────────────────────────────────────────────────
    logger.info("=== Writing run log ===")
    try:
        append_run_record(
            run_type="daily",
            collected=collected_stats,
            after_dedup=dedup_stats,
            after_filter=filter_stats,
            issue_url=issue_url,
            email_results=email_results,
            errors=run_errors,
        )
    except Exception as e:
        logger.error(f"Failed to write run log: {e}")

    logger.info("=== Daily update completed ===")
    return total


if __name__ == "__main__":
    count = main()
    sys.exit(0 if count >= 0 else 1)
