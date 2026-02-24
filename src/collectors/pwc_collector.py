"""Collect trending papers from Papers with Code."""

import logging
from datetime import datetime, timezone
from dataclasses import dataclass, field

import requests

logger = logging.getLogger(__name__)

PWC_API = "https://paperswithcode.com/api/v1"


@dataclass
class PwcPaper:
    """Represents a paper from Papers with Code."""

    paper_id: str
    title: str
    abstract: str
    authors: list[str]
    url_abs: str
    url_pdf: str
    published: str
    arxiv_id: str = ""
    repository_url: str = ""
    stars: int = 0
    tasks: list[str] = field(default_factory=list)
    source: str = "pwc"
    matched_categories: list[str] = field(default_factory=list)
    relevance_score: float = 0.0
    summary_en: str = ""
    summary_cn: str = ""

    @property
    def unique_id(self) -> str:
        return f"pwc:{self.paper_id}"


def collect(config: dict) -> list[PwcPaper]:
    """Fetch latest trending papers from Papers with Code.

    Args:
        config: The 'papers_with_code' section from sources.yaml.

    Returns:
        List of PwcPaper objects.
    """
    max_results = config.get("max_results", 50)
    papers = []

    try:
        # Fetch latest papers
        url = f"{PWC_API}/papers/"
        params = {
            "ordering": "-published",
            "items_per_page": max_results,
        }

        resp = requests.get(url, params=params, timeout=30)
        if resp.status_code != 200:
            logger.warning(f"PWC API returned status {resp.status_code}")
            return papers

        data = resp.json()
        results = data.get("results", [])

        for item in results:
            paper_id = item.get("id", "")
            title = item.get("title", "").strip()
            if not title:
                continue

            # Get repository info for this paper
            repo_url = ""
            stars = 0
            try:
                repo_resp = requests.get(
                    f"{PWC_API}/papers/{paper_id}/repositories/",
                    timeout=10,
                )
                if repo_resp.status_code == 200:
                    repos = repo_resp.json().get("results", [])
                    if repos:
                        # Pick the repo with the most stars
                        best_repo = max(repos, key=lambda r: r.get("stars", 0))
                        repo_url = best_repo.get("url", "")
                        stars = best_repo.get("stars", 0)
            except Exception:
                pass  # repo info is nice-to-have

            paper = PwcPaper(
                paper_id=str(paper_id),
                title=title,
                abstract=item.get("abstract", "").strip(),
                authors=item.get("authors", []) or [],
                url_abs=item.get("url_abs", "") or f"https://paperswithcode.com/paper/{paper_id}",
                url_pdf=item.get("url_pdf", "") or "",
                published=item.get("published", "") or datetime.now(timezone.utc).isoformat(),
                arxiv_id=item.get("arxiv_id", "") or "",
                repository_url=repo_url,
                stars=stars,
            )
            papers.append(paper)

        logger.info(f"Fetched {len(papers)} papers from Papers with Code")

    except Exception as e:
        logger.error(f"Error fetching from Papers with Code: {e}")

    return papers
