# CLAUDE.md — Project Context for AI-Assisted Development

## What This Project Does

Automated daily tracker for LLM research and tools. Runs via GitHub Actions, collects updates from multiple sources, filters by keyword relevance, and delivers results through GitHub Issues and bilingual email (English + Chinese).

## Architecture Overview

```
src/
├── collectors/          # Data collection from external sources
│   ├── arxiv_collector.py      # arXiv API (arxiv Python package)
│   ├── github_collector.py     # GitHub REST API + Trending page scraping
│   └── pwc_collector.py        # Papers with Code REST API
├── filters/
│   └── keyword_filter.py       # Regex-based keyword matching with weighted scoring
├── formatters/
│   └── issue_formatter.py      # Markdown generation for Issues/emails
├── notifiers/
│   └── github_issue.py         # GitHub Issue creation via PyGithub
├── state/
│   ├── dedup.py                # JSON-file-based deduplication (data/seen.json)
│   └── run_logger.py           # Appends structured run records to data/run-log.json
├── modules/
│   ├── email_sender/           # INDEPENDENT MODULE: Bilingual email
│   │   ├── smtp_client.py      # Gmail SMTP wrapper
│   │   ├── translator.py       # Claude API translation (EN→CN)
│   │   └── bilingual.py        # Orchestrates: EN→Email A, CN→Email B
│   └── weekly_summary/         # INDEPENDENT MODULE: Weekly digest
│       ├── aggregator.py       # Parses past daily Issues via GitHub API
│       ├── ranker.py           # Ranks by weighted score (relevance × appearances)
│       └── formatter.py        # Weekly summary Markdown generation
├── main.py                     # Daily update entry point
└── weekly.py                   # Weekly summary entry point
```

## Key Data Flow

### Daily (`main.py`)
1. Collect → arXiv, GitHub (releases + trending), Papers with Code
2. Dedup → filter out previously seen items (`data/seen.json`)
3. Filter → keyword matching against `config/keywords.yaml`, score ≥ threshold
4. Format → structured Markdown
5. Notify → create GitHub Issue (label: `daily-update`)
6. Email → English to EMAIL_EN list, Claude-translated Chinese to EMAIL_CN list (comma-separated for multiple recipients)
7. Log → append run stats to `data/run-log.json` (collected/dedup/filter counts, issue URL, errors)
8. Persist → update `data/seen.json` + `data/run-log.json`, auto-commit via GitHub Actions

### Weekly (`weekly.py`)
1. Triggered by `/weekly-summary` comment on any issue, or manual workflow_dispatch
2. Aggregates all `daily-update` labeled Issues from last 7 days
3. Parses Issue bodies to extract items, deduplicates, ranks
4. Creates a new Issue (label: `weekly-summary`) + bilingual email

## Configuration Files

- `config/keywords.yaml` — Keyword categories with weights. Each category has `weight` (float) and `terms` (list). Scoring: `sqrt(matched_terms) * weight` per category, summed across categories.
- `config/sources.yaml` — arXiv categories, tracked GitHub repos list, trending settings, PWC settings.
- `config/settings.yaml` — Filter thresholds, email toggles, translation model, weekly summary params, dedup retention.

## Environment Variables / GitHub Secrets

| Variable | Purpose |
|---|---|
| `GITHUB_TOKEN` | Auto-provided by Actions. Used for Issue creation and repo API calls. |
| `GMAIL_ADDRESS` | Sender Gmail address for SMTP |
| `GMAIL_APP_PASSWORD` | Gmail App Password (16-char, NOT login password) |
| `EMAIL_EN` | Recipient(s) for English version (comma-separated for multiple) |
| `EMAIL_CN` | Recipient(s) for Chinese translated version (comma-separated for multiple) |
| `LLM_API_KEY` | Anthropic Claude API key for translation |

## Key Design Decisions

1. **GitHub Issues as primary notification** — zero-cost, zero-config, GitHub auto-pushes to email. Issues also serve as data store for weekly aggregation.
2. **Rule-based filtering (no LLM)** — keyword matching with weighted scoring. No API cost for filtering. Only translation uses Claude API.
3. **JSON file dedup** — `data/seen.json` committed to repo by Actions bot. Simple, no database needed. Auto-prunes entries older than 30 days.
4. **GitHub Trending via scraping** — no official API exists. Uses BeautifulSoup to parse `github.com/trending/{language}`.
5. **Bilingual email as independent module** — `modules/email_sender/` is self-contained. Can be used by both daily and weekly flows. Translation is done via Claude API (`claude-sonnet-4-20250514` by default).
6. **Weekly summary as independent module** — `modules/weekly_summary/` parses existing Issue bodies to aggregate. No separate data store needed.

## Code Conventions

- Python 3.11+ target (GitHub Actions). Use `from __future__ import annotations` for backward compat in files with `X | Y` union syntax.
- All modules use `logging` (not print). Logger name = `__name__`.
- Dataclasses for data models (ArxivPaper, GitHubItem, PwcPaper, AggregatedItem). Each has a `unique_id` property for dedup.
- Config loaded via PyYAML. Paths relative to project root.
- GitHub API via PyGithub library. REST calls via `requests`.

## Common Tasks

### Adding a new keyword category
Edit `config/keywords.yaml`. Add a new top-level key with `weight` and `terms`. No code changes needed.

### Adding a new tracked GitHub repo
Edit `config/sources.yaml` → `github.tracked_repos`. Append the `owner/repo` string.

### Adding a new data source
1. Create `src/collectors/new_collector.py` with a `collect(config) -> list[DataClass]` function
2. The dataclass needs `unique_id` property, `title`, `relevance_score`, `matched_categories` fields
3. Wire it into `src/main.py` (collect → dedup → filter → format)
4. Add a format function in `src/formatters/issue_formatter.py`

### Changing the translation model
Edit `config/settings.yaml` → `translation.model`. Or set a different model string.

### Adjusting filter sensitivity
Edit `config/settings.yaml` → `filter.min_score`. Lower = more items, higher = stricter.

## Known Issues / Limitations

- GitHub Trending scraping depends on page structure. If GitHub changes their HTML, `github_collector.py` may break.
- arXiv API can be slow and occasionally rate-limits. The collector has retry logic (3 retries) and uses `max(published, updated)` to catch revised papers. `lookback_days=3` covers weekends when arXiv has no new papers.
- Papers with Code API fetches the latest papers globally, not filtered by area before keyword matching. Could be optimized.
- Translation cost: each daily email translates the full Issue body via Claude API. For typical daily reports this is minimal (< $0.01/day).
- `seen.json` can grow large if many items are collected daily. Auto-pruning keeps only the last 30 days.

## Repository

- Owner: changao1
- Repo: updater-for-LLM-tech
- Remote: https://github.com/changao1/updater-for-LLM-tech.git
- Primary branch: main
