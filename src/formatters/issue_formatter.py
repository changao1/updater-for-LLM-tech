"""Format collected and filtered items into Markdown for GitHub Issues and emails."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Localised label maps
# ---------------------------------------------------------------------------
_LABELS = {
    "en": {
        "github_updates": "GitHub Updates",
        "new_releases": "New Releases",
        "trending_repos": "Trending Repos",
        "arxiv_papers": "arXiv Papers",
        "papers_with_code": "Papers with Code",
        "relevance": "Relevance",
        "score": "score",
        "topics": "Topics",
        "authors": "Authors",
        "categories": "Categories",
        "language": "Language",
        "stars": "Stars",
        "today": "today",
        "high": "HIGH",
        "medium": "MEDIUM",
        "low": "LOW",
        "daily_title": "LLM Research & Tech Daily Update",
        "summary_github": "GitHub updates",
        "summary_arxiv": "arXiv papers",
        "summary_pwc": "Papers with Code",
        "no_items": "No new items matching the configured keywords were found today.",
        "weekly_hint": (
            "**Generate Weekly Summary**: Comment `/weekly-summary` on this issue "
            "to trigger a weekly digest of the most important updates."
        ),
    },
    "cn": {
        "github_updates": "GitHub 更新",
        "new_releases": "新发布",
        "trending_repos": "热门仓库",
        "arxiv_papers": "arXiv 论文",
        "papers_with_code": "Papers with Code",
        "relevance": "相关性",
        "score": "得分",
        "topics": "主题",
        "authors": "作者",
        "categories": "分类",
        "language": "语言",
        "stars": "Stars",
        "today": "今日",
        "high": "高",
        "medium": "中等",
        "low": "低",
        "daily_title": "LLM 研究与技术日报",
        "summary_github": "GitHub 更新",
        "summary_arxiv": "arXiv 论文",
        "summary_pwc": "Papers with Code",
        "no_items": "今日没有匹配到符合关键词的新内容。",
        "weekly_hint": (
            "**生成周报**: 在此 Issue 下评论 `/weekly-summary` "
            "即可触发过去一周的重点摘要。"
        ),
    },
}


def _l(key: str, lang: str) -> str:
    """Look up a localised label."""
    return _LABELS.get(lang, _LABELS["en"]).get(key, _LABELS["en"][key])


def _score_badge(score: float, lang: str = "en") -> str:
    """Return a visual indicator of relevance score."""
    if score >= 4.0:
        return _l("high", lang)
    elif score >= 2.0:
        return _l("medium", lang)
    return _l("low", lang)


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
        lang: Language for summaries and labels - "en" or "cn".

    Returns:
        Markdown string for the arXiv section.
    """
    if not papers:
        return ""

    lines = [f"## {_l('arxiv_papers', lang)} ({len(papers)})\n"]

    for i, paper in enumerate(papers, 1):
        badge = _score_badge(paper.relevance_score, lang)
        cats = ", ".join(paper.matched_categories) if paper.matched_categories else "general"
        authors = ", ".join(paper.authors[:3])
        if len(paper.authors) > 3:
            authors += " et al."

        lines.append(f"### {i}. [{paper.title}]({paper.url})")
        lines.append(
            f"**{_l('relevance', lang)}: {badge}** "
            f"({_l('score', lang)}: {paper.relevance_score}) | "
            f"**{_l('topics', lang)}**: {cats}"
        )
        lines.append(
            f"**{_l('authors', lang)}**: {authors} | "
            f"**{_l('categories', lang)}**: {', '.join(paper.categories[:3])}"
        )

        summary_text = _get_summary(paper, lang, "abstract")
        if summary_text:
            lines.append(f"\n> {summary_text}\n")

        lines.append(f"[PDF]({paper.pdf_url})\n")

    return "\n".join(lines)


def format_github_section(items: list, lang: str = "en") -> str:
    """Format GitHub items into Markdown.

    Args:
        items: List of GitHubItem objects (already filtered and scored).
        lang: Language for summaries and labels - "en" or "cn".

    Returns:
        Markdown string for the GitHub section.
    """
    if not items:
        return ""

    releases = [i for i in items if i.item_type == "release"]
    trending = [i for i in items if i.item_type == "trending"]

    lines = [f"## {_l('github_updates', lang)} ({len(items)})\n"]

    if releases:
        lines.append(f"### {_l('new_releases', lang)}\n")
        for i, item in enumerate(releases, 1):
            badge = _score_badge(item.relevance_score, lang)
            cats = ", ".join(item.matched_categories) if item.matched_categories else ""
            tag_str = f" `{item.release_tag}`" if item.release_tag else ""

            lines.append(f"**{i}. [{item.repo_name}]({item.url})**{tag_str}")
            lines.append(
                f"{_l('relevance', lang)}: {badge} "
                f"({_l('score', lang)}: {item.relevance_score})"
                + (f" | {_l('topics', lang)}: {cats}" if cats else "")
            )
            summary_text = _get_summary(item, lang, "description")
            if summary_text:
                lines.append(f"\n> {summary_text}\n")
            else:
                lines.append("")

    if trending:
        lines.append(f"### {_l('trending_repos', lang)}\n")
        for i, item in enumerate(trending, 1):
            badge = _score_badge(item.relevance_score, lang)
            cats = ", ".join(item.matched_categories) if item.matched_categories else ""
            stars_info = f"{_l('stars', lang)}: {item.stars:,}"
            if item.stars_today:
                stars_info += f" (+{item.stars_today:,} {_l('today', lang)})"

            lines.append(f"**{i}. [{item.repo_name}]({item.url})** | {stars_info}")
            lines.append(
                f"{_l('relevance', lang)}: {badge} "
                f"({_l('score', lang)}: {item.relevance_score})"
                + (f" | {_l('topics', lang)}: {cats}" if cats else "")
            )
            if item.language:
                lines.append(f"{_l('language', lang)}: {item.language}")
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
        lang: Language for summaries and labels - "en" or "cn".

    Returns:
        Markdown string for the PWC section.
    """
    if not papers:
        return ""

    lines = [f"## {_l('papers_with_code', lang)} ({len(papers)})\n"]

    for i, paper in enumerate(papers, 1):
        badge = _score_badge(paper.relevance_score, lang)
        cats = ", ".join(paper.matched_categories) if paper.matched_categories else ""

        lines.append(f"### {i}. [{paper.title}]({paper.url_abs})")
        lines.append(
            f"**{_l('relevance', lang)}: {badge}** "
            f"({_l('score', lang)}: {paper.relevance_score})"
            + (f" | **{_l('topics', lang)}**: {cats}" if cats else "")
        )

        if paper.authors:
            authors = ", ".join(paper.authors[:3])
            if len(paper.authors) > 3:
                authors += " et al."
            lines.append(f"**{_l('authors', lang)}**: {authors}")

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
        lang: Language for summaries and labels - "en" or "cn".

    Returns:
        Tuple of (issue_title, issue_body).
    """
    if date_str is None:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    total = len(arxiv_papers) + len(github_items) + len(pwc_papers)

    title = f"LLM Daily Update - {date_str} ({total} items)"

    body_parts = [f"# {_l('daily_title', lang)} - {date_str}\n"]

    # Summary line (GitHub first to match section order)
    body_parts.append(
        f"**{len(github_items)}** {_l('summary_github', lang)} | "
        f"**{len(arxiv_papers)}** {_l('summary_arxiv', lang)} | "
        f"**{len(pwc_papers)}** {_l('summary_pwc', lang)}\n"
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
        body_parts.append(f"*{_l('no_items', lang)}*\n")

    # Weekly summary trigger hint
    body_parts.append(f"\n---\n{_l('weekly_hint', lang)}\n")

    body = "\n".join(body_parts)
    return title, body
