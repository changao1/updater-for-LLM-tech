"""Star-history enrichment: embed growth curves and boost ranking by star growth.

Displays SVG curves from star-history.com and uses GitHub API + a local cache
to compute 7-day star growth rates for ranking.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
STAR_HISTORY_SVG = "https://api.star-history.com/svg"
DEFAULT_CACHE_PATH = Path(__file__).parent.parent.parent / "data" / "star_history_cache.json"


def get_svg_url(repo_name: str) -> str:
    return f"{STAR_HISTORY_SVG}?repos={repo_name}&type=Date"


class StarCache:
    """Persistent cache of (date, stars) samples per repo."""

    def __init__(self, path: str | Path = DEFAULT_CACHE_PATH, retention_days: int = 30):
        self.path = Path(path)
        self.retention_days = retention_days
        self._data: dict[str, list[list]] = {}
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                with open(self.path, "r") as f:
                    self._data = json.load(f)
                logger.info(f"Loaded star cache from {self.path}")
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Error loading star cache, starting fresh: {e}")
                self._data = {}
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def save(self):
        self._prune()
        with open(self.path, "w") as f:
            json.dump(self._data, f, indent=2)
        logger.info(f"Saved star cache to {self.path}")

    def _prune(self):
        cutoff = (datetime.now(timezone.utc) - timedelta(days=self.retention_days)).isoformat()
        for repo in list(self._data.keys()):
            self._data[repo] = [s for s in self._data[repo] if s[0] > cutoff]
            if not self._data[repo]:
                del self._data[repo]

    def record(self, repo_name: str, stars: int):
        now = datetime.now(timezone.utc).isoformat()
        self._data.setdefault(repo_name, []).append([now, stars])

    def stars_n_days_ago(self, repo_name: str, days: int) -> int | None:
        """Return the cached stars count closest to N days ago, or None if no sample old enough."""
        samples = self._data.get(repo_name, [])
        if not samples:
            return None
        target = datetime.now(timezone.utc) - timedelta(days=days)
        target_iso = target.isoformat()
        older = [s for s in samples if s[0] <= target_iso]
        if not older:
            return None
        # Closest to target (latest of those older than target)
        return older[-1][1]


def fetch_current_stars(repo_name: str, token: str | None = None) -> int | None:
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        resp = requests.get(f"{GITHUB_API}/repos/{repo_name}", headers=headers, timeout=15)
        if resp.status_code != 200:
            logger.warning(f"Failed to fetch stars for {repo_name}: {resp.status_code}")
            return None
        return resp.json().get("stargazers_count")
    except Exception as e:
        logger.warning(f"Error fetching stars for {repo_name}: {e}")
        return None


def compute_growth_rate(
    repo_name: str, current_stars: int, cache: StarCache, window_days: int = 7
) -> float | None:
    past = cache.stars_n_days_ago(repo_name, window_days)
    if past is None or past <= 0:
        return None
    return (current_stars - past) / past


def enrich_github_items(
    items: list,
    cache: StarCache,
    token: str | None,
    top_n: int,
    growth_weight: float = 0.3,
    window_days: int = 7,
) -> list:
    """Enrich top-N GitHub items by star growth.

    - Ranks items by current relevance_score, picks top_n.
    - For each, fetches current stars (one GitHub API call), updates cache,
      computes 7-day growth, attaches star_history_url, and boosts relevance_score
      by growth_weight * growth_rate.
    - Returns items re-sorted by updated relevance_score.
    """
    if not items:
        return items

    sorted_items = sorted(items, key=lambda x: x.relevance_score, reverse=True)
    for item in sorted_items[:top_n]:
        stars = fetch_current_stars(item.repo_name, token)
        if stars is None:
            stars = item.stars or 0
        if stars:
            cache.record(item.repo_name, stars)
            item.stars = max(item.stars, stars)

        growth = compute_growth_rate(item.repo_name, stars, cache, window_days)
        item.star_growth_7d = growth
        item.star_history_url = get_svg_url(item.repo_name)
        if growth is not None:
            boost = growth_weight * growth
            item.relevance_score += boost
            logger.info(
                f"star-history: {item.repo_name} stars={stars} growth_7d={growth:.3f} "
                f"boost=+{boost:.3f}"
            )
        else:
            logger.info(f"star-history: {item.repo_name} stars={stars} (no baseline yet)")

    return sorted(items, key=lambda x: x.relevance_score, reverse=True)
