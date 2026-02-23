"""Format weekly summary into Markdown."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from .aggregator import AggregatedItem

logger = logging.getLogger(__name__)


def format_weekly_summary(
    items: list[AggregatedItem],
    lookback_days: int = 7,
) -> tuple[str, str]:
    """Format ranked items into a weekly summary Issue.

    Args:
        items: Ranked list of AggregatedItem.
        lookback_days: Number of days covered.

    Returns:
        Tuple of (issue_title, issue_body_markdown).
    """
    now = datetime.now(timezone.utc)
    start_date = (now - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    end_date = now.strftime("%Y-%m-%d")

    title = f"LLM Weekly Summary - {start_date} to {end_date} ({len(items)} highlights)"

    body_parts = [
        f"# LLM Research & Tech Weekly Summary",
        f"**Period**: {start_date} to {end_date} | **Highlights**: {len(items)}\n",
        "---\n",
    ]

    if not items:
        body_parts.append("*No items found for this period.*\n")
        return title, "\n".join(body_parts)

    # Group by source
    arxiv_items = [i for i in items if i.source == "arxiv"]
    github_items = [i for i in items if i.source == "github"]
    pwc_items = [i for i in items if i.source == "pwc"]
    other_items = [i for i in items if i.source not in ("arxiv", "github", "pwc")]

    # Top highlights section (overall top 5)
    body_parts.append("## Top Highlights\n")
    for i, item in enumerate(items[:5], 1):
        cats = ", ".join(item.matched_categories) if item.matched_categories else ""
        appear = f" (appeared {item.appearances}x)" if item.appearances > 1 else ""
        body_parts.append(
            f"**{i}. [{item.title}]({item.url})** "
            f"| Score: {item.weighted_score:.1f}{appear}"
        )
        if cats:
            body_parts.append(f"   Topics: {cats}")
        if item.description:
            body_parts.append(f"   > {item.description[:200]}")
        body_parts.append("")

    body_parts.append("---\n")

    # Detailed sections by source
    if arxiv_items:
        body_parts.append(f"## arXiv Papers ({len(arxiv_items)})\n")
        for i, item in enumerate(arxiv_items, 1):
            cats = ", ".join(item.matched_categories)
            body_parts.append(f"{i}. [{item.title}]({item.url}) | Score: {item.weighted_score:.1f}")
            if cats:
                body_parts.append(f"   Topics: {cats}")
            if item.description:
                body_parts.append(f"   > {item.description[:200]}")
            body_parts.append("")
        body_parts.append("---\n")

    if github_items:
        body_parts.append(f"## GitHub Updates ({len(github_items)})\n")
        for i, item in enumerate(github_items, 1):
            cats = ", ".join(item.matched_categories)
            body_parts.append(f"{i}. [{item.title}]({item.url}) | Score: {item.weighted_score:.1f}")
            if cats:
                body_parts.append(f"   Topics: {cats}")
            if item.description:
                body_parts.append(f"   > {item.description[:200]}")
            body_parts.append("")
        body_parts.append("---\n")

    if pwc_items:
        body_parts.append(f"## Papers with Code ({len(pwc_items)})\n")
        for i, item in enumerate(pwc_items, 1):
            cats = ", ".join(item.matched_categories)
            body_parts.append(f"{i}. [{item.title}]({item.url}) | Score: {item.weighted_score:.1f}")
            if cats:
                body_parts.append(f"   Topics: {cats}")
            if item.description:
                body_parts.append(f"   > {item.description[:200]}")
            body_parts.append("")
        body_parts.append("---\n")

    if other_items:
        body_parts.append(f"## Other ({len(other_items)})\n")
        for i, item in enumerate(other_items, 1):
            body_parts.append(f"{i}. [{item.title}]({item.url}) | Score: {item.weighted_score:.1f}")
            body_parts.append("")

    body = "\n".join(body_parts)
    return title, body
