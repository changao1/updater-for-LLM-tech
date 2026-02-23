"""Collect recent papers from arXiv using the arxiv Python package."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field

import arxiv

logger = logging.getLogger(__name__)


@dataclass
class ArxivPaper:
    """Represents a single arXiv paper."""

    arxiv_id: str
    title: str
    authors: list[str]
    abstract: str
    categories: list[str]
    published: str  # ISO format date string
    url: str
    pdf_url: str
    source: str = "arxiv"
    matched_categories: list[str] = field(default_factory=list)
    relevance_score: float = 0.0

    @property
    def unique_id(self) -> str:
        return f"arxiv:{self.arxiv_id}"


def _to_utc(dt: datetime) -> datetime:
    """Safely convert a datetime to UTC, handling both naive and aware datetimes."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def collect(config: dict) -> list[ArxivPaper]:
    """Fetch recent papers from arXiv based on configured categories.

    Args:
        config: The 'arxiv' section from sources.yaml.

    Returns:
        List of ArxivPaper objects.
    """
    categories = config.get("categories", ["cs.CL", "cs.AI", "cs.LG"])
    max_results = config.get("max_results", 200)
    lookback_days = config.get("lookback_days", 3)

    cutoff_date = datetime.now(timezone.utc) - timedelta(days=lookback_days)

    # Build query: search across all configured categories
    cat_query = " OR ".join(f"cat:{cat}" for cat in categories)
    query = f"({cat_query})"

    logger.info(f"Querying arXiv: {query} (max {max_results} results, lookback {lookback_days} days)")

    client = arxiv.Client(
        page_size=100,
        delay_seconds=3.0,
        num_retries=3,
    )
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending,
    )

    papers = []
    raw_count = 0
    skipped_by_date = 0

    try:
        for result in client.results(search):
            raw_count += 1

            # Use the more recent of published and updated dates
            # - published: when the first version was posted
            # - updated: when the latest version was posted (catches revisions)
            pub_date = _to_utc(result.published)
            upd_date = _to_utc(result.updated)
            effective_date = max(pub_date, upd_date)

            if effective_date < cutoff_date:
                skipped_by_date += 1
                continue

            paper = ArxivPaper(
                arxiv_id=result.entry_id.split("/abs/")[-1],
                title=result.title.replace("\n", " ").strip(),
                authors=[a.name for a in result.authors[:5]],  # first 5 authors
                abstract=result.summary.replace("\n", " ").strip(),
                categories=[c for c in result.categories],
                published=effective_date.isoformat(),
                url=result.entry_id,
                pdf_url=result.pdf_url or "",
            )
            papers.append(paper)

        logger.info(
            f"arXiv: {raw_count} raw results, "
            f"{skipped_by_date} skipped by date, "
            f"{len(papers)} papers within lookback window"
        )
    except Exception as e:
        logger.error(f"Error fetching from arXiv: {e}")
        # Return whatever we collected before the error
        if papers:
            logger.info(f"Returning {len(papers)} papers collected before error")

    return papers
