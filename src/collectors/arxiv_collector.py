"""Collect recent papers from arXiv using the arxiv Python package."""

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


def collect(config: dict) -> list[ArxivPaper]:
    """Fetch recent papers from arXiv based on configured categories.

    Args:
        config: The 'arxiv' section from sources.yaml.

    Returns:
        List of ArxivPaper objects.
    """
    categories = config.get("categories", ["cs.CL", "cs.AI", "cs.LG"])
    max_results = config.get("max_results", 200)
    lookback_days = config.get("lookback_days", 2)

    cutoff_date = datetime.now(timezone.utc) - timedelta(days=lookback_days)

    # Build query: search across all configured categories
    cat_query = " OR ".join(f"cat:{cat}" for cat in categories)
    query = f"({cat_query})"

    logger.info(f"Querying arXiv: {query} (max {max_results} results)")

    client = arxiv.Client()
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending,
    )

    papers = []
    try:
        for result in client.results(search):
            # Filter by date
            pub_date = result.published.replace(tzinfo=timezone.utc)
            if pub_date < cutoff_date:
                continue

            paper = ArxivPaper(
                arxiv_id=result.entry_id.split("/abs/")[-1],
                title=result.title.replace("\n", " ").strip(),
                authors=[a.name for a in result.authors[:5]],  # first 5 authors
                abstract=result.summary.replace("\n", " ").strip(),
                categories=[c for c in result.categories],
                published=pub_date.isoformat(),
                url=result.entry_id,
                pdf_url=result.pdf_url,
            )
            papers.append(paper)

        logger.info(f"Fetched {len(papers)} papers from arXiv")
    except Exception as e:
        logger.error(f"Error fetching from arXiv: {e}")

    return papers
