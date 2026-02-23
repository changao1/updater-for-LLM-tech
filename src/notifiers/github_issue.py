"""Create GitHub Issues using the GitHub API."""

from __future__ import annotations

import logging
import os

from github import Github, GithubException

logger = logging.getLogger(__name__)


def _get_repo():
    """Get the current GitHub repository object.

    Uses GITHUB_TOKEN and GITHUB_REPOSITORY environment variables
    (automatically set in GitHub Actions).
    """
    token = os.environ.get("GITHUB_TOKEN", "")
    repo_name = os.environ.get("GITHUB_REPOSITORY", "")

    if not token:
        raise ValueError("GITHUB_TOKEN environment variable is not set")
    if not repo_name:
        raise ValueError("GITHUB_REPOSITORY environment variable is not set")

    g = Github(token)
    return g.get_repo(repo_name)


def create_issue(
    title: str,
    body: str,
    labels: list[str] | None = None,
) -> str | None:
    """Create a new GitHub Issue.

    Args:
        title: Issue title.
        body: Issue body (Markdown).
        labels: List of label names to apply.

    Returns:
        URL of the created issue, or None on failure.
    """
    try:
        repo = _get_repo()

        # Ensure labels exist
        if labels:
            existing_labels = {l.name for l in repo.get_labels()}
            for label in labels:
                if label not in existing_labels:
                    try:
                        repo.create_label(name=label, color="0e8a16")
                    except GithubException:
                        pass

        issue = repo.create_issue(title=title, body=body, labels=labels or [])
        logger.info(f"Created issue: {issue.html_url}")
        return issue.html_url

    except Exception as e:
        logger.error(f"Failed to create issue: {e}")
        return None


def get_issues_by_label(
    label: str,
    state: str = "all",
    since_days: int = 7,
) -> list[dict]:
    """Fetch issues with a specific label.

    Args:
        label: Label name to filter by.
        state: Issue state ("open", "closed", "all").
        since_days: Only return issues created within the last N days.

    Returns:
        List of dicts with issue data (title, body, created_at, url).
    """
    from datetime import datetime, timedelta, timezone

    try:
        repo = _get_repo()
        since = datetime.now(timezone.utc) - timedelta(days=since_days)

        issues = repo.get_issues(
            labels=[repo.get_label(label)],
            state=state,
            since=since,
            sort="created",
            direction="desc",
        )

        result = []
        for issue in issues:
            if issue.pull_request:
                continue
            created = issue.created_at.replace(tzinfo=timezone.utc)
            if created < since:
                continue
            result.append(
                {
                    "title": issue.title,
                    "body": issue.body or "",
                    "created_at": created.isoformat(),
                    "url": issue.html_url,
                    "number": issue.number,
                }
            )

        logger.info(f"Found {len(result)} issues with label '{label}' in last {since_days} days")
        return result

    except Exception as e:
        logger.error(f"Failed to fetch issues: {e}")
        return []
