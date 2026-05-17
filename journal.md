# Development Journal

## 2026-05-17 — diagnose empty weekend digests; remove Papers with Code

### Why

User reported the tracker "hasn't worked the past few days." The workflow was actually running fine (issues #84–#90 created, emails sent, `errors: []`), but the run-log showed content collapsing on the weekend: 5/16 (Sat) arXiv `200→0→0`, 5/17 (Sun) `0→0→0`.

**Root causes found:**

1. **arXiv empty on weekends.** The collector uses `sortBy=submittedDate desc, max_results=200`, then drops papers older than `lookback_days=3`. On busy weekdays the newest 200 only span a few hours, so the 3-day lookback never actually reaches back 3 days. arXiv doesn't announce on weekends, so Sat/Sun the newest 200 are stale weekday papers already in `data/seen.json` → dedup zeroes them out. The "lookback_days=3 covers weekends" comment was a false assumption.
2. **Papers with Code fully dead.** Live test: `Error fetching from Papers with Code: Expecting value: line 1 column 1 (char 0)` — non-JSON response. paperswithcode.com API was shut down by Meta in 2025. PwC has been 0 every single day, not just weekends.

GitHub collector verified healthy (33 items live).

### Changes

**1. Daily workflow runs weekdays only**

`.github/workflows/daily-update.yml` cron `0 8 * * *` → `0 8 * * 1-5`. No more empty Sat/Sun issues/emails — matches arXiv's actual publishing cadence.

**2. arXiv query now uses an explicit submittedDate range**

`arxiv_collector.py` previously queried `(cat:... OR ...)` with `sortBy=submittedDate desc` and a `max_results` cap, then post-filtered by `lookback_days`. arXiv's submittedDate sort is unreliable, so the result set was effectively "the newest ~200 papers as of query time" — a few-hours snapshot on busy weekdays, never reaching `lookback_days` back. Changed the query to `(cat:... OR ...) AND submittedDate:[<now-lookback> TO <now>]` (format `YYYYMMDDHHMM`, UTC) and raised the `max_results` cap 200 → 600. Result set is now deterministic: every paper in the window, newest-first, capped. Validated live: a 7-day lookback returned 600 papers spanning two distinct days (233 + 367) where the old code only ever saw one ~few-hour cluster. Trade-off documented: arXiv's submittedDate filter keys off the v1 submission date, so papers revised (not first-submitted) inside the window are not returned — acceptable for predictable new-paper coverage.

**3. Papers with Code removed entirely**

Deleted `src/collectors/pwc_collector.py`; removed the collect/dedup/filter/summarize/format wiring from `src/main.py`; dropped `format_pwc_section()` and the `pwc_papers` parameter from `format_daily_issue()` in `issue_formatter.py` (signature is now `(arxiv_papers, github_items, ...)`); removed PwC labels, the `papers_with_code` block in `config/sources.yaml`, the `pwc` default bucket in `dedup.py`, and the PwC section in `weekly_summary/formatter.py`. The weekly `aggregator.py` still recognises old `## Papers with Code` headers in historical issues but buckets them as `other` to avoid mis-attribution.

### Files modified/deleted

| File | Change |
|---|---|
| `.github/workflows/daily-update.yml` | cron → weekdays only (`1-5`) |
| `src/collectors/pwc_collector.py` | **deleted** |
| `src/main.py` | removed all PwC pipeline steps + import |
| `src/formatters/issue_formatter.py` | removed `format_pwc_section`, PwC param/labels |
| `config/sources.yaml` | removed `papers_with_code` block (replaced with NOTE) |
| `src/state/dedup.py` | removed `pwc` default bucket |
| `src/modules/weekly_summary/formatter.py` | removed PwC section + grouping |
| `src/modules/weekly_summary/aggregator.py` | old PwC headers → `other` bucket |
| `src/filters/keyword_filter.py`, `src/modules/summarizer.py`, `src/state/run_logger.py` | docstring/comment cleanup |
| `CLAUDE.md` | updated architecture, data flow, known issues |

## 2026-04-14 — star-history integration + retire tracked_repos

### Changes

**1. Removed `tracked_repos` entirely**

The hand-maintained list of "old favorite" repos in `config/sources.yaml` was deleted along with `collect_releases()` in `src/collectors/github_collector.py`. Rationale: keyword filter + trending + star-growth ranking can surface relevant repos automatically, and a stale manual list gave outdated projects unearned visibility. If a repo stops trending, that's itself the signal that daily updates aren't needed.

**2. New module `src/modules/star_history.py`**

- `get_svg_url()` builds `https://api.star-history.com/svg?repos=owner/repo&type=Date` for embedding inline growth curves in Issue/email Markdown.
- `StarCache` persists `(date, stars)` samples to `data/star_history_cache.json` (mirrors the dedup.py pattern, 30-day retention).
- `enrich_github_items()` picks the top-N GitHub items by relevance_score, calls GitHub API for current `stargazers_count`, records a sample, computes 7-day growth rate vs. oldest cached sample, boosts `relevance_score` by `growth_weight * growth_rate`, and attaches `star_history_url` + `star_growth_7d` fields.

**3. Formatter — new 🔥 Hot Repos board**

`format_github_section()` now emits a dedicated top-of-section listing the 3 repos with the steepest 7-day growth, each followed by the star-history SVG. Normal release/trending listings below don't re-embed the curve (avoids duplicate images in email).

**4. Settings**

New `star_history` block in `config/settings.yaml`: `enabled`, `top_n=5`, `hot_repos_count=3`, `growth_weight=0.3`, `window_days=7`, `cache_retention_days=30`.

### Files modified/created

| File | Change |
|---|---|
| `src/modules/star_history.py` | **new** — SVG URL builder, StarCache, growth rate, top-N enrichment |
| `src/collectors/github_collector.py` | removed `collect_releases()` + tracked_repos path; added `star_history_url` and `star_growth_7d` fields on `GitHubItem` |
| `src/main.py` | inserted enrichment step between filter and summarize |
| `src/formatters/issue_formatter.py` | added 🔥 Hot Repos board at top of GitHub section with embedded curves |
| `config/sources.yaml` | removed `tracked_repos` list |
| `config/settings.yaml` | added `star_history` config block |
| `CLAUDE.md` | updated architecture diagram, daily flow, and common-tasks section |

### Design notes

- star-history.com has no documented public JSON API. We use their SVG endpoint only for display, and compute the growth ranking signal from our own GitHub API calls + local cache. First run has no baseline → growth=None → no score boost → graceful degradation.
- Only top-N (default 5) items incur GitHub API calls, well under the 5000/hr authenticated limit.
- Gmail renders inline `<img>` from star-history SVG through its image proxy; Markdown `![...](...)` is already converted to HTML by `bilingual.py`.

## 2026-02-24 — Reorder email sections + bilingual AI summaries

### Changes

**1. Section order: GitHub now appears before arXiv**

- Modified `src/formatters/issue_formatter.py`: `format_daily_issue()` now emits sections in the order GitHub -> arXiv -> Papers with Code (previously arXiv -> GitHub -> PwC). The summary count line at the top was also reordered to match.
- This affects both the GitHub Issue and emails.

**2. Claude-generated bilingual key-point summaries replace truncated abstracts**

Instead of showing a truncated 300-char abstract/description, each item now gets a 2-3 sentence summary generated by Claude that highlights the core contribution and why it matters. Summaries are produced in both English and Chinese.

**Files modified:**

| File | What changed |
|---|---|
| `src/collectors/arxiv_collector.py` | Added `summary_en`, `summary_cn` fields to `ArxivPaper` dataclass |
| `src/collectors/github_collector.py` | Added `summary_en`, `summary_cn` fields to `GitHubItem` dataclass |
| `src/collectors/pwc_collector.py` | Added `summary_en`, `summary_cn` fields to `PwcPaper` dataclass |
| `src/modules/summarizer.py` | **New file.** `Summarizer` class that batches all filtered items into a single Claude API call, asks for EN+CN summaries, parses the JSON response, and attaches results to item objects in-place. Supports batching (30 items per call) for large sets. Graceful fallback on failure. |
| `src/formatters/issue_formatter.py` | Added `lang` parameter to all section formatters and `format_daily_issue()`. New `_get_summary()` helper selects the right summary field (EN/CN) with fallback to truncated original text. Section order changed to GitHub -> arXiv -> PwC. |
| `src/modules/email_sender/bilingual.py` | `send()` now accepts an optional `content_cn` parameter. When provided, the pre-generated CN content is used directly and translation is skipped. Falls back to the original translate-via-Claude behavior if `content_cn` is not given (backward compat for weekly summary). |
| `src/main.py` | Added Summarize step between Filter and Format. Generates two formatted bodies: EN (for Issue + EN email) and CN (for CN email with Chinese summaries). Passes `content_cn` to `BilingualSender.send()`. |

**Design decisions:**

- Summaries are generated in one batched API call (up to 30 items per batch) for cost efficiency. Input ~6K tokens, output ~6K tokens per batch.
- The CN email has Chinese summaries in the blockquote sections while all structural text (headings, badges, author names, links) stays in English. This avoids mistranslation of technical terms.
- The GitHub Issue uses EN summaries (same as the EN email).
- If summarization fails (API error, no key, etc.), the formatter silently falls back to truncated abstracts — the pipeline is never blocked.
- Weekly summary flow (`weekly.py`) is unaffected — it still uses the full-translation approach via `Translator`.

## 2026-02-24 — Localise CN email headings and labels

### Changes

The CN email previously kept all structural text (section headings, metadata labels, score badges) in English — only the blockquote summaries were in Chinese. This made the CN email feel inconsistent.

Added a `_LABELS` localisation dictionary to `src/formatters/issue_formatter.py` that maps every UI string to both English and Chinese. When `lang="cn"`, the formatter now produces fully localised output:

- Section headings: "GitHub 更新", "arXiv 论文", "热门仓库", "新发布"
- Metadata labels: "相关性:", "得分:", "主题:", "作者:", "分类:", "语言:"
- Score badges: "高", "中等", "低"
- Page title: "LLM 研究与技术日报"
- Summary line, no-items message, weekly trigger hint — all in Chinese
- Stars count and "今日" for trending repos

Technical terms (paper titles, repo names, URLs, author names, arXiv category codes) remain untranslated.

**Files modified:**

| File | What changed |
|---|---|
| `src/formatters/issue_formatter.py` | Added `_LABELS` dict with EN/CN maps, `_l()` lookup helper. Updated `_score_badge()` to accept `lang`. All section formatters and `format_daily_issue()` now use `_l()` for every user-facing string. |
| `journal.md` | Added this entry. |
