"""Collect updates from GitHub: tracked repo releases and trending repos."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
TRENDING_URL = "https://github.com/trending"


@dataclass
class GitHubItem:
    """Represents a GitHub repo update (release or trending)."""

    repo_name: str  # e.g. "huggingface/transformers"
    title: str
    description: str
    url: str
    stars: int = 0
    stars_today: int = 0
    release_tag: str = ""
    release_body: str = ""
    item_type: str = "release"  # "release" or "trending"
    language: str = ""
    published: str = ""
    source: str = "github"
    matched_categories: list[str] = field(default_factory=list)
    relevance_score: float = 0.0
    summary_en: str = ""
    summary_cn: str = ""

    @property
    def unique_id(self) -> str:
        if self.item_type == "release":
            return f"github:release:{self.repo_name}:{self.release_tag}"
        return f"github:trending:{self.repo_name}"


def _get_headers(token: str | None = None) -> dict:
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def collect_releases(config: dict, token: str | None = None) -> list[GitHubItem]:
    """Fetch recent releases from tracked repositories.

    Args:
        config: The 'github' section from sources.yaml.
        token: GitHub API token.

    Returns:
        List of GitHubItem objects for new releases.
    """
    tracked_repos = config.get("tracked_repos", [])
    headers = _get_headers(token)
    cutoff = datetime.now(timezone.utc) - timedelta(days=2)
    items = []

    for repo in tracked_repos:
        try:
            url = f"{GITHUB_API}/repos/{repo}/releases"
            resp = requests.get(url, headers=headers, params={"per_page": 5}, timeout=15)

            if resp.status_code == 404:
                # Try tags instead (some repos don't use GitHub Releases)
                url = f"{GITHUB_API}/repos/{repo}/tags"
                resp = requests.get(url, headers=headers, params={"per_page": 3}, timeout=15)
                if resp.status_code == 200:
                    tags = resp.json()
                    if tags:
                        # Get repo info for description
                        repo_resp = requests.get(
                            f"{GITHUB_API}/repos/{repo}", headers=headers, timeout=15
                        )
                        repo_info = repo_resp.json() if repo_resp.status_code == 200 else {}
                        tag = tags[0]
                        item = GitHubItem(
                            repo_name=repo,
                            title=f"{repo} - {tag['name']}",
                            description=repo_info.get("description", "") or "",
                            url=f"https://github.com/{repo}/releases/tag/{tag['name']}",
                            stars=repo_info.get("stargazers_count", 0),
                            release_tag=tag["name"],
                            item_type="release",
                            language=repo_info.get("language", "") or "",
                        )
                        items.append(item)
                continue

            if resp.status_code != 200:
                logger.warning(f"Failed to fetch releases for {repo}: {resp.status_code}")
                continue

            releases = resp.json()
            for release in releases:
                pub_str = release.get("published_at") or release.get("created_at", "")
                if not pub_str:
                    continue
                pub_date = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
                if pub_date < cutoff:
                    continue

                item = GitHubItem(
                    repo_name=repo,
                    title=f"{repo} - {release.get('name') or release.get('tag_name', '')}",
                    description=release.get("body", "")[:500] or "",
                    url=release.get("html_url", f"https://github.com/{repo}"),
                    release_tag=release.get("tag_name", ""),
                    release_body=release.get("body", "")[:1000] or "",
                    item_type="release",
                    published=pub_date.isoformat(),
                )
                items.append(item)

        except Exception as e:
            logger.warning(f"Error fetching releases for {repo}: {e}")

    logger.info(f"Fetched {len(items)} releases from tracked repos")
    return items


def collect_trending(config: dict) -> list[GitHubItem]:
    """Scrape GitHub Trending page for AI/ML repos.

    Args:
        config: The 'github.trending' section from sources.yaml.

    Returns:
        List of GitHubItem objects for trending repos.
    """
    trending_config = config.get("trending", {})
    languages = trending_config.get("languages", ["python"])
    min_stars = trending_config.get("min_stars", 50)
    spoken_language = trending_config.get("spoken_language", "")

    items = []

    for language in languages:
        try:
            params = {"since": "daily"}
            if spoken_language:
                params["spoken_language_code"] = spoken_language

            url = f"{TRENDING_URL}/{language}"
            resp = requests.get(url, params=params, timeout=15)
            if resp.status_code != 200:
                logger.warning(f"Failed to fetch trending for {language}: {resp.status_code}")
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            articles = soup.select("article.Box-row")

            for article in articles:
                # Repository name
                name_el = article.select_one("h2 a")
                if not name_el:
                    continue
                href = name_el.get("href") or ""
                repo_name = str(href).strip("/")
                if not repo_name:
                    continue

                # Description
                desc_el = article.select_one("p")
                description = desc_el.get_text(strip=True) if desc_el else ""

                # Stars
                star_els = article.select("a.Link--muted")
                total_stars = 0
                if star_els:
                    star_text = star_els[0].get_text(strip=True).replace(",", "")
                    try:
                        total_stars = int(star_text)
                    except ValueError:
                        pass

                # Stars today
                stars_today = 0
                today_el = article.select_one("span.d-inline-block.float-sm-right")
                if today_el:
                    today_text = today_el.get_text(strip=True).split(" ")[0].replace(",", "")
                    try:
                        stars_today = int(today_text)
                    except ValueError:
                        pass

                # Language
                lang_el = article.select_one("span[itemprop='programmingLanguage']")
                lang = lang_el.get_text(strip=True) if lang_el else language

                if total_stars < min_stars:
                    continue

                item = GitHubItem(
                    repo_name=repo_name,
                    title=repo_name,
                    description=description,
                    url=f"https://github.com/{repo_name}",
                    stars=total_stars,
                    stars_today=stars_today,
                    item_type="trending",
                    language=lang,
                    published=datetime.now(timezone.utc).isoformat(),
                )
                items.append(item)

        except Exception as e:
            logger.warning(f"Error fetching trending for {language}: {e}")

    logger.info(f"Fetched {len(items)} trending repos")
    return items


def collect(config: dict, token: str | None = None) -> list[GitHubItem]:
    """Collect all GitHub updates (releases + trending).

    Args:
        config: The 'github' section from sources.yaml.
        token: GitHub API token.

    Returns:
        Combined list of GitHubItem objects.
    """
    releases = collect_releases(config, token)
    trending = collect_trending(config)
    return releases + trending
