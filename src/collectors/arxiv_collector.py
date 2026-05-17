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
    summary_en: str = ""
    summary_cn: str = ""

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
    max_results = config.get("max_results", 600)
    lookback_days = config.get("lookback_days", 3)

    now = datetime.now(timezone.utc)
    cutoff_date = now - timedelta(days=lookback_days)

    # Build query: categories AND an explicit submittedDate range.
    #
    # Why the date range matters: arXiv's `sortBy=submittedDate` is unreliable —
    # requesting the "newest N" returns a clustered/stale snapshot, so with only
    # a max_results cap the lookback window never actually reaches `lookback_days`
    # back on busy weekdays. Constraining `submittedDate:[start TO end]` in the
    # query makes the result set deterministic: we get *every* paper in the
    # window regardless of API sort quirks, capped by max_results.
    #
    # Note: arXiv's submittedDate filter keys off the original (v1) submission,
    # so a paper submitted before the window but revised inside it won't be
    # returned. That's an accepted trade-off for predictable, complete coverage
    # of newly-submitted papers. Format is YYYYMMDDHHMM (UTC).
    cat_query = " OR ".join(f"cat:{cat}" for cat in categories)
    date_range = f"[{cutoff_date.strftime('%Y%m%d%H%M')} TO {now.strftime('%Y%m%d%H%M')}]"
    query = f"({cat_query}) AND submittedDate:{date_range}"

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
