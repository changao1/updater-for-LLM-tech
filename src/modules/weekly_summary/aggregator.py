"""Aggregate data from past daily update Issues for the weekly summary."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from src.notifiers.github_issue import get_issues_by_label

logger = logging.getLogger(__name__)


@dataclass
class AggregatedItem:
    """An item extracted from daily Issues for weekly aggregation."""

    title: str
    url: str
    source: str  # "arxiv", "github", "pwc"
    relevance_score: float = 0.0
    matched_categories: list[str] = field(default_factory=list)
    description: str = ""
    extra_info: str = ""
    appearances: int = 1  # how many daily issues it appeared in

    @property
    def weighted_score(self) -> float:
        """Score boosted by number of appearances across days."""
        return self.relevance_score * (1 + 0.2 * (self.appearances - 1))


def _parse_issue_body(body: str) -> list[AggregatedItem]:
    """Parse a daily issue body to extract individual items.

    This parser extracts items from the Markdown-formatted issue body
    by looking for the structured patterns produced by issue_formatter.

    Args:
        body: The issue body Markdown text.

    Returns:
        List of AggregatedItem parsed from the issue.
    """
    items = []
    current_source = "unknown"

    # Detect which section we're in
    section_patterns = {
        "arxiv": re.compile(r"^##\s+arXiv\s+Papers", re.IGNORECASE),
        "github": re.compile(r"^##\s+GitHub\s+Updates", re.IGNORECASE),
        "pwc": re.compile(r"^##\s+Papers\s+with\s+Code", re.IGNORECASE),
    }

    # Match item headers: ### N. [Title](URL) or **N. [Title](URL)**
    item_pattern = re.compile(
        r"(?:###?\s*\d+\.\s*|(?:\*\*)\d+\.\s*)"
        r"\[([^\]]+)\]\(([^)]+)\)"
    )

    # Match score: score: X.XX
    score_pattern = re.compile(r"score:\s*([\d.]+)")

    # Match topics: Topics: cat1, cat2
    topics_pattern = re.compile(r"Topics?:\s*([^\n|]+)")

    # Match blockquote descriptions
    quote_pattern = re.compile(r"^>\s*(.+)", re.MULTILINE)

    lines = body.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Check for section headers
        for source, pattern in section_patterns.items():
            if pattern.match(line):
                current_source = source
                break

        # Check for item headers
        item_match = item_pattern.search(line)
        if item_match:
            title = item_match.group(1)
            url = item_match.group(2)

            # Look ahead for score and topics in next few lines
            context = "\n".join(lines[i : i + 5])
            score = 0.0
            categories = []
            description = ""

            score_match = score_pattern.search(context)
            if score_match:
                try:
                    score = float(score_match.group(1))
                except ValueError:
                    pass

            topics_match = topics_pattern.search(context)
            if topics_match:
                categories = [
                    c.strip() for c in topics_match.group(1).split(",") if c.strip()
                ]

            # Look for blockquote description
            for j in range(i + 1, min(i + 8, len(lines))):
                quote_match = quote_pattern.match(lines[j])
                if quote_match:
                    description = quote_match.group(1).strip()
                    break

            items.append(
                AggregatedItem(
                    title=title,
                    url=url,
                    source=current_source,
                    relevance_score=score,
                    matched_categories=categories,
                    description=description,
                )
            )

        i += 1

    return items


def aggregate_weekly(label: str = "daily-update", days: int = 7) -> list[AggregatedItem]:
    """Aggregate items from daily Issues over the past N days.

    Args:
        label: The label used for daily update issues.
        days: Number of days to look back.

    Returns:
        List of AggregatedItem, deduplicated and with appearance counts.
    """
    issues = get_issues_by_label(label=label, state="all", since_days=days)
    logger.info(f"Found {len(issues)} daily issues in the past {days} days")

    # Parse all items from all issues
    all_items: dict[str, AggregatedItem] = {}

    for issue in issues:
        parsed = _parse_issue_body(issue["body"])
        for item in parsed:
            key = item.url  # Use URL as dedup key
            if key in all_items:
                all_items[key].appearances += 1
                # Keep the higher score
                if item.relevance_score > all_items[key].relevance_score:
                    all_items[key].relevance_score = item.relevance_score
                # Merge categories
                existing_cats = set(all_items[key].matched_categories)
                for cat in item.matched_categories:
                    if cat not in existing_cats:
                        all_items[key].matched_categories.append(cat)
            else:
                all_items[key] = item

    items = list(all_items.values())
    logger.info(f"Aggregated {len(items)} unique items from {len(issues)} daily issues")
    return items
