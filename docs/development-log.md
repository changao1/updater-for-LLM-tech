# Development Log

This document records the full development history of the LLM Tech Updater project — the requirements, decisions, trade-offs, and implementation timeline. It is intended for human developers (including the original author) to understand how and why this project was built the way it is.

---

## Table of Contents

- [1. Project Genesis](#1-project-genesis)
- [2. Requirements Discovery](#2-requirements-discovery)
- [3. Architecture Decisions](#3-architecture-decisions)
- [4. Implementation Timeline](#4-implementation-timeline)
- [5. First Successful Run](#5-first-successful-run)
- [6. Feature Summary](#6-feature-summary)
- [7. Future Improvement Ideas](#7-future-improvement-ideas)

---

## 1. Project Genesis

**Date**: 2026-02-22

**Problem statement**: The project owner wanted a way to automatically track the latest LLM research progress on GitHub and other sources, focusing on transformative and impactful developments for productivity. The tracking needed to be automated, filtered for relevance, and delivered conveniently.

**Initial repo state**: Empty repository with only a README placeholder and a LaTeX-focused `.gitignore`.

---

## 2. Requirements Discovery

Requirements were gathered through an iterative Q&A process. Here are the key decisions made:

### 2.1 Core Delivery Method

| Option Considered | Decision | Reason |
|---|---|---|
| GitHub Actions automation | **Selected** | Zero-cost, reliable scheduling, integrates with GitHub natively |
| Static page / Dashboard | Rejected | More complex to maintain, less push-based |
| Markdown document | Rejected | No push notification capability |

### 2.2 Data Sources

Selected (all three):
- **arXiv** — cs.CL, cs.AI, cs.LG, cs.SE categories
- **GitHub** — Tracked repos (releases) + Trending page (daily)
- **Papers with Code** — Latest papers with open-source implementations

### 2.3 Update Frequency

- **Daily** for the main update
- **Weekly summary** on demand (added as a requirement later)

### 2.4 Focus Areas

All major LLM directions were selected:
- Reasoning / Chain-of-Thought
- Coding / Programming assistance
- RAG / Knowledge retrieval
- Agent / Automation
- Model architecture innovation
- Deployment / Inference optimization
- Training / Fine-tuning techniques
- Multimodal (added during implementation)
- Safety (added during implementation, lower weight)

### 2.5 Filtering Strategy

| Option | Decision | Reason |
|---|---|---|
| Keyword matching | **Selected for filtering** | Zero API cost, transparent, configurable |
| LLM-based scoring | Rejected for filtering | Unnecessary cost for this use case |
| Citation/influence metrics | Rejected | New papers have zero citations, unsuitable for tracking latest |

### 2.6 Notification Method

| Option | Decision | Reason |
|---|---|---|
| GitHub Issues | **Selected as primary** | Zero-cost, GitHub auto-emails, also serves as data store for weekly aggregation |
| Gmail SMTP | **Added later** | User requested bilingual email delivery |

### 2.7 Additional Features (Added Mid-Design)

Two independent modules were requested after the initial design:

1. **Weekly Summary Module** — User wanted a "button" to generate a weekly digest
   - Trigger method: Comment `/weekly-summary` on any issue (chosen over link-to-Actions or auto-schedule)
   - Output: New GitHub Issue with `weekly-summary` label
   - Implementation: Parses past daily Issues, no separate data store needed

2. **Bilingual Email Module** — User wanted dual-language email delivery
   - English original → Email A
   - Chinese translation → Email B
   - Translation via Claude API (user reversed earlier "no LLM" decision specifically for translation)
   - Email via Gmail SMTP with App Password

### 2.8 Translation API

| Option | Decision | Reason |
|---|---|---|
| Claude API (Anthropic) | **Selected** | Strong Chinese language ability, high translation quality |
| OpenAI API | Considered | Also viable but user preferred Claude |
| DeepSeek API | Considered | Cheapest but stability concerns |
| deep-translator (free) | Initially considered | Replaced by LLM when user changed mind about translation quality |

### 2.9 Programming Language

- **Python** — Best ecosystem for arXiv API, GitHub API, web scraping

---

## 3. Architecture Decisions

### 3.1 Module Independence

The two added features (weekly summary, bilingual email) were explicitly requested to be **independent modules**. This means:
- `src/modules/email_sender/` — Self-contained. Can be imported and used by both daily and weekly flows, or independently.
- `src/modules/weekly_summary/` — Self-contained. Depends only on `notifiers/github_issue.py` for fetching past Issues.

### 3.2 Deduplication Strategy

- JSON file (`data/seen.json`) committed to repo by GitHub Actions bot
- Each item tracked by `unique_id` (e.g., `arxiv:2401.12345`, `github:trending:owner/repo`)
- Auto-prunes entries older than 30 days to prevent unbounded growth
- Simple and reliable — no external database needed

### 3.3 Keyword Scoring Algorithm

```
For each keyword category:
  cat_score = sqrt(matched_terms_count) * category_weight

total_score = sum of all cat_scores
```

- `sqrt()` provides diminishing returns for many matches in the same category
- Category weights allow prioritizing certain topics (e.g., reasoning and agent at 1.5x, safety at 0.8x)
- Default threshold: `min_score = 1.0` (configurable in `settings.yaml`)

### 3.4 GitHub Trending Scraping

GitHub has no official Trending API. The collector scrapes `github.com/trending/{language}` and parses HTML with BeautifulSoup. This is fragile — if GitHub changes their page structure, it will break. This is a known trade-off documented in `CLAUDE.md`.

### 3.5 Weekly Summary Data Source

Rather than maintaining a separate data store, the weekly summary module **parses existing GitHub Issue bodies** from the past 7 days. This is elegant but means the Issue body format is a de facto API contract — changes to `issue_formatter.py` output must be compatible with `aggregator.py` parsing.

---

## 4. Implementation Timeline

All implementation was done in a single session on **2026-02-22**.

### Phase 1: Project Skeleton
- Created directory structure (14 directories)
- `requirements.txt` with 7 dependencies
- Updated `.gitignore` with Python patterns
- Initialized `data/seen.json`

### Phase 2: Configuration Files
- `config/keywords.yaml` — 9 keyword categories, 80+ terms
- `config/sources.yaml` — 30+ tracked GitHub repos, arXiv categories, PWC settings
- `config/settings.yaml` — Filter thresholds, email toggles, translation config

### Phase 3: Core Modules (built in parallel)
- `collectors/arxiv_collector.py` — Uses `arxiv` Python package, fetches last 2 days
- `collectors/github_collector.py` — GitHub REST API for releases + BeautifulSoup for trending
- `collectors/pwc_collector.py` — Papers with Code REST API
- `filters/keyword_filter.py` — Regex-based matching with weighted scoring
- `state/dedup.py` — JSON-based dedup with TTL pruning

### Phase 4: Output Layer
- `formatters/issue_formatter.py` — Markdown generation with score badges, topic tags
- `notifiers/github_issue.py` — PyGithub-based Issue creation + label management

### Phase 5: Independent Modules
- `modules/email_sender/smtp_client.py` — Gmail SMTP wrapper
- `modules/email_sender/translator.py` — Claude API translation with configurable model/prompt
- `modules/email_sender/bilingual.py` — Orchestration: EN→Email A, translate→CN→Email B
- `modules/weekly_summary/aggregator.py` — Parses daily Issue bodies, extracts items
- `modules/weekly_summary/ranker.py` — Weighted scoring with appearance boost
- `modules/weekly_summary/formatter.py` — Weekly digest Markdown generation

### Phase 6: Entry Points
- `src/main.py` — Daily flow: collect → dedup → filter → format → issue → email → save
- `src/weekly.py` — Weekly flow: aggregate → rank → format → issue → email

### Phase 7: GitHub Actions
- `.github/workflows/daily-update.yml` — Cron at 08:00 UTC, with auto-commit for seen.json
- `.github/workflows/weekly-summary.yml` — `issue_comment` trigger + `workflow_dispatch`

### Phase 8: Verification
- All Python files compile successfully (`py_compile`)
- All module imports resolve correctly
- Keyword filter tested: relevant text scores 6.32, irrelevant text scores 0.0
- Dependencies installed and verified

---

## 5. First Successful Run

**Date**: 2026-02-22 (same day as implementation)

The workflow was triggered manually from the GitHub Actions tab. Result:
- GitHub Issue created successfully with daily update content
- English email delivered to Email A
- Chinese translated email delivered to Email B
- `data/seen.json` updated and committed by the Actions bot

---

## 6. Feature Summary

| Feature | Status | Notes |
|---|---|---|
| arXiv paper collection | Working | cs.CL, cs.AI, cs.LG, cs.SE |
| GitHub release tracking | Working | 30+ repos from major AI labs |
| GitHub Trending scraping | Working | Python + Jupyter Notebook |
| Papers with Code collection | Working | Latest papers with code links |
| Keyword-based filtering | Working | 9 categories, weighted scoring |
| Deduplication | Working | JSON-based, 30-day retention |
| GitHub Issue creation (daily) | Working | Label: `daily-update` |
| GitHub Issue creation (weekly) | Working | Label: `weekly-summary` |
| English email (Email A) | Working | Gmail SMTP |
| Chinese email (Email B) | Working | Claude API translation |
| `/weekly-summary` trigger | Working | `issue_comment` event |
| Manual workflow trigger | Working | `workflow_dispatch` |
| Auto-commit seen.json | Working | GitHub Actions bot |

---

## 7. Future Improvement Ideas

These are potential enhancements identified during development but not yet implemented:

### High Priority
- ~~**Retry logic for arXiv API**~~ — Implemented in v0.2 (3 retries, `max(published, updated)` date handling)
- ~~**Multiple email recipients**~~ — Implemented in v0.2 (comma-separated in secrets)
- **Error notification** — Send an alert if the daily workflow fails (could use GitHub Actions failure notification)
- **Configurable cron schedule** — Allow changing the daily run time without editing YAML

### Medium Priority
- **Hacker News / Reddit integration** — Additional data sources for community discussion tracking
- **Awesome List tracking** — Monitor changes to curated lists like `awesome-llm`
- **Author whitelist** — Auto-include papers from key researchers regardless of keyword match
- **Semantic Scholar integration** — Enrich papers with citation counts once available
- **Email unsubscribe mechanism** — Allow disabling email via config without removing secrets

### Low Priority
- **Web dashboard** — GitHub Pages static site for browsing past updates
- **RSS feed generation** — Output an RSS/Atom feed for feed reader integration
- **Slack/Discord webhook** — Alternative notification channels
- **LLM-based summarization** — Use Claude to generate executive summaries (beyond translation)
- **Trending detection** — Identify papers/repos gaining unusual traction across sources

### Technical Debt
- **GitHub Trending scraper fragility** — Depends on HTML structure. Consider using unofficial APIs or GitHub GraphQL as fallback
- **Weekly aggregator parsing** — Tightly coupled to Issue body format. Consider storing structured data (JSON) alongside Markdown
- **Test coverage** — No unit tests exist yet. Priority areas: keyword filter, dedup store, Issue body parser
- **Type checking** — Add `mypy` configuration and fix type annotations
- **CI pipeline** — Add linting (ruff) and type checking to PR workflow

---

## Changelog

### v0.2 — 2026-02-23

Three improvements applied after first successful production run:

**1. Multiple email recipients**
- `smtp_client.py`: `send()` now accepts `str | list[str]` for the `to` parameter. Internally parses comma-separated strings.
- `bilingual.py`: Reads `EMAIL_EN` / `EMAIL_CN` as comma-separated lists. All recipients receive the same email in a single SMTP call.
- Usage: Set `EMAIL_EN=alice@gmail.com,bob@outlook.com` in GitHub Secrets.

**2. arXiv collection fix**
- Root cause: First test ran on a weekend (arXiv publishes no new papers Sat/Sun). `lookback_days: 2` was too short to bridge weekend gaps.
- Fix 1: Increased `lookback_days` from 2 → 3 in `sources.yaml`.
- Fix 2: Fixed timezone handling — replaced unsafe `datetime.replace(tzinfo=...)` with proper `_to_utc()` helper that handles both naive and aware datetimes.
- Fix 3: Now uses `max(published, updated)` as the effective date, so revised papers are also caught.
- Fix 4: Added `num_retries=3` to the arXiv client for resilience against rate-limits.
- Fix 5: Added detailed logging: raw result count, date-filtered count, final count.

**3. Automated run logging**
- New module: `src/state/run_logger.py` — appends a structured JSON record after each daily/weekly run.
- Records: timestamp, run type, collected/dedup/filter counts per source, issue URL, email status, errors.
- Storage: `data/run-log.json` (auto-committed by GitHub Actions alongside `seen.json`).
- Max 200 records retained (auto-prunes older entries).
- Both `main.py` and `weekly.py` now call `append_run_record()` at the end of each run.
- Both GitHub Actions workflows updated to commit `data/run-log.json`.
- `CLAUDE.md` updated to reflect new architecture (run_logger, multi-recipient email, arXiv improvements).

**Documentation convention established**: When making code changes to this project, always update `CLAUDE.md` (architecture/conventions) and append a changelog entry to this file.
