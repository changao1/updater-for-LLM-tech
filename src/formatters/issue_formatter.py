"""Format collected and filtered items into Markdown for GitHub Issues and emails."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def _score_badge(score: float) -> str:
    """Return a visual indicator of relevance score."""
    if score >= 4.0:
        return "HIGH"
    elif score >= 2.0:
        return "MEDIUM"
    return "LOW"


def _truncate(text: str, max_len: int = 300) -> str:
    """Truncate text to max_len characters."""
    if len(text) <= max_len:
        return text
    return text[:max_len].rstrip() + "..."


def _get_summary(item, lang: str, fallback_field: str) -> str:
    """Get the appropriate summary text for an item.

    If a Claude-generated summary exists for the requested language, use it.
    Otherwise fall back to the truncated original text.

    Args:
        item: A data item (ArxivPaper, GitHubItem, or PwcPaper).
        lang: Language code - "en" or "cn".
        fallback_field: Attribute name to use as fallback (e.g. "abstract", "description").

    Returns:
        The summary or truncated fallback text.
    """
    if lang == "cn":
        summary = getattr(item, "summary_cn", "")
        if summary:
            return summary
    # For "en" or if CN summary is missing, try EN summary
    summary = getattr(item, "summary_en", "")
    if summary:
        return summary
    # Fallback to original truncated text
    fallback = getattr(item, fallback_field, "")
    return _truncate(fallback) if fallback else ""


def format_arxiv_section(papers: list, lang: str = "en") -> str:
    """Format arXiv papers into Markdown.

    Args:
        papers: List of ArxivPaper objects (already filtered and scored).
        lang: Language for summaries - "en" or "cn".

    Returns:
        Markdown string for the arXiv section.
    """
    if not papers:
        return ""

    lines = [f"## arXiv Papers ({len(papers)})\n"]

    for i, paper in enumerate(papers, 1):
        badge = _score_badge(paper.relevance_score)
        cats = ", ".join(paper.matched_categories) if paper.matched_categories else "general"
        authors = ", ".join(paper.authors[:3])
        if len(paper.authors) > 3:
            authors += " et al."

        lines.append(f"### {i}. [{paper.title}]({paper.url})")
        lines.append(f"**Relevance: {badge}** (score: {paper.relevance_score}) | "
                      f"**Topics**: {cats}")
        lines.append(f"**Authors**: {authors} | "
                      f"**Categories**: {', '.join(paper.categories[:3])}")

        summary_text = _get_summary(paper, lang, "abstract")
        if summary_text:
            lines.append(f"\n> {summary_text}\n")

        lines.append(f"[PDF]({paper.pdf_url})\n")

    return "\n".join(lines)


def format_github_section(items: list, lang: str = "en") -> str:
    """Format GitHub items into Markdown.

    Args:
        items: List of GitHubItem objects (already filtered and scored).
        lang: Language for summaries - "en" or "cn".

    Returns:
        Markdown string for the GitHub section.
    """
    if not items:
        return ""

    releases = [i for i in items if i.item_type == "release"]
    trending = [i for i in items if i.item_type == "trending"]

    lines = [f"## GitHub Updates ({len(items)})\n"]

    if releases:
        lines.append("### New Releases\n")
        for i, item in enumerate(releases, 1):
            badge = _score_badge(item.relevance_score)
            cats = ", ".join(item.matched_categories) if item.matched_categories else ""
            tag_str = f" `{item.release_tag}`" if item.release_tag else ""

            lines.append(f"**{i}. [{item.repo_name}]({item.url})**{tag_str}")
            lines.append(f"Relevance: {badge} (score: {item.relevance_score})"
                          + (f" | Topics: {cats}" if cats else ""))
            summary_text = _get_summary(item, lang, "description")
            if summary_text:
                lines.append(f"\n> {summary_text}\n")
            else:
                lines.append("")

    if trending:
        lines.append("### Trending Repos\n")
        for i, item in enumerate(trending, 1):
            badge = _score_badge(item.relevance_score)
            cats = ", ".join(item.matched_categories) if item.matched_categories else ""
            stars_info = f"Stars: {item.stars:,}"
            if item.stars_today:
                stars_info += f" (+{item.stars_today:,} today)"

            lines.append(f"**{i}. [{item.repo_name}]({item.url})** | {stars_info}")
            lines.append(f"Relevance: {badge} (score: {item.relevance_score})"
                          + (f" | Topics: {cats}" if cats else ""))
            if item.language:
                lines.append(f"Language: {item.language}")
            summary_text = _get_summary(item, lang, "description")
            if summary_text:
                lines.append(f"\n> {summary_text}\n")
            else:
                lines.append("")

    return "\n".join(lines)


def format_pwc_section(papers: list, lang: str = "en") -> str:
    """Format Papers with Code items into Markdown.

    Args:
        papers: List of PwcPaper objects (already filtered and scored).
        lang: Language for summaries - "en" or "cn".

    Returns:
        Markdown string for the PWC section.
    """
    if not papers:
        return ""

    lines = [f"## Papers with Code ({len(papers)})\n"]

    for i, paper in enumerate(papers, 1):
        badge = _score_badge(paper.relevance_score)
        cats = ", ".join(paper.matched_categories) if paper.matched_categories else ""

        lines.append(f"### {i}. [{paper.title}]({paper.url_abs})")
        lines.append(f"**Relevance: {badge}** (score: {paper.relevance_score})"
                      + (f" | **Topics**: {cats}" if cats else ""))

        if paper.authors:
            authors = ", ".join(paper.authors[:3])
            if len(paper.authors) > 3:
                authors += " et al."
            lines.append(f"**Authors**: {authors}")

        summary_text = _get_summary(paper, lang, "abstract")
        if summary_text:
            lines.append(f"\n> {summary_text}\n")

        link_parts = []
        if paper.url_pdf:
            link_parts.append(f"[PDF]({paper.url_pdf})")
        if paper.repository_url:
            star_str = f" ({paper.stars:,} stars)" if paper.stars else ""
            link_parts.append(f"[Code]({paper.repository_url}){star_str}")
        if link_parts:
            lines.append(" | ".join(link_parts) + "\n")

    return "\n".join(lines)


def format_daily_issue(
    arxiv_papers: list,
    github_items: list,
    pwc_papers: list,
    date_str: str | None = None,
    lang: str = "en",
) -> tuple[str, str]:
    """Format all sections into a complete daily update Issue.

    Sections are ordered: GitHub -> arXiv -> Papers with Code.

    Args:
        arxiv_papers: Filtered arXiv papers.
        github_items: Filtered GitHub items.
        pwc_papers: Filtered PWC papers.
        date_str: Date string for the title (default: today).
        lang: Language for summaries - "en" or "cn".

    Returns:
        Tuple of (issue_title, issue_body).
    """
    if date_str is None:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    total = len(arxiv_papers) + len(github_items) + len(pwc_papers)

    title = f"LLM Daily Update - {date_str} ({total} items)"

    body_parts = [f"# LLM Research & Tech Daily Update - {date_str}\n"]

    # Summary line (GitHub first to match section order)
    body_parts.append(
        f"**{len(github_items)}** GitHub updates | "
        f"**{len(arxiv_papers)}** arXiv papers | "
        f"**{len(pwc_papers)}** Papers with Code\n"
    )
    body_parts.append("---\n")

    # Sections: GitHub first, then arXiv, then PwC
    github_md = format_github_section(github_items, lang=lang)
    if github_md:
        body_parts.append(github_md)
        body_parts.append("---\n")

    arxiv_md = format_arxiv_section(arxiv_papers, lang=lang)
    if arxiv_md:
        body_parts.append(arxiv_md)
        body_parts.append("---\n")

    pwc_md = format_pwc_section(pwc_papers, lang=lang)
    if pwc_md:
        body_parts.append(pwc_md)
        body_parts.append("---\n")

    if total == 0:
        body_parts.append("*No new items matching the configured keywords were found today.*\n")

    # Weekly summary trigger hint
    body_parts.append(
        "\n---\n"
        "**Generate Weekly Summary**: Comment `/weekly-summary` on this issue "
        "to trigger a weekly digest of the most important updates.\n"
    )

    body = "\n".join(body_parts)
    return title, body
