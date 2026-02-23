# LLM Tech Updater

Automated daily tracker for impactful LLM research and tools. Collects updates from arXiv, GitHub, and Papers with Code, filters by keyword relevance, and delivers results via GitHub Issues and bilingual email (English + Chinese).

## Features

- **Multi-source collection**: arXiv papers, GitHub releases & trending repos, Papers with Code
- **Keyword-based filtering**: Configurable keyword categories with weighted scoring
- **Deduplication**: Tracks seen items to avoid duplicate notifications
- **GitHub Issues**: Auto-creates daily update Issues with structured Markdown
- **Bilingual email**: Sends English original to Email A, Claude-translated Chinese version to Email B
- **Weekly summary**: Comment `/weekly-summary` on any issue to generate a weekly digest of top highlights
- **Fully configurable**: All keywords, sources, and settings in YAML config files

## Architecture

```
GitHub Actions (cron daily / issue_comment trigger)
  │
  ├─ Collectors ──→ arXiv API, GitHub API, Papers with Code API
  ├─ Filter ──────→ Keyword matching + relevance scoring
  ├─ Dedup ───────→ Tracks seen items in data/seen.json
  ├─ Formatter ───→ Markdown for Issues and emails
  ├─ Notifier ────→ Creates GitHub Issues
  └─ Email ───────→ Gmail SMTP (EN → Email A, CN → Email B)
```

## Setup

### 1. Fork or clone this repository

```bash
git clone https://github.com/YOUR_USERNAME/updater-for-LLM-tech.git
cd updater-for-LLM-tech
```

### 2. Configure GitHub Secrets

Go to your repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Add the following secrets:

| Secret Name | Description | Required |
|---|---|---|
| `GMAIL_ADDRESS` | Gmail address used to send emails (e.g. `yourname@gmail.com`) | Yes (for email) |
| `GMAIL_APP_PASSWORD` | Gmail App Password (NOT your login password, see below) | Yes (for email) |
| `EMAIL_EN` | Email address(es) to receive English version. Comma-separated for multiple: `a@example.com,b@example.com` | Yes (for email) |
| `EMAIL_CN` | Email address(es) to receive Chinese version. Comma-separated for multiple: `a@example.com,b@example.com` | Yes (for email) |
| `LLM_API_KEY` | Anthropic Claude API key (for translation) | Yes (for Chinese email) |

> **Note**: `GITHUB_TOKEN` is automatically provided by GitHub Actions. You do NOT need to add it manually.

### 3. Generate a Gmail App Password

Gmail requires an **App Password** (not your regular password) for SMTP:

1. Go to [Google Account Security](https://myaccount.google.com/security)
2. Enable **2-Step Verification** if not already enabled
3. Go to [App Passwords](https://myaccount.google.com/apppasswords)
4. Select **Mail** and your device, then click **Generate**
5. Copy the 16-character password and save it as the `GMAIL_APP_PASSWORD` secret

### 4. Get a Claude API Key

1. Go to [Anthropic Console](https://console.anthropic.com/)
2. Create an account or sign in
3. Go to **API Keys** → **Create Key**
4. Copy the key and save it as the `LLM_API_KEY` secret

### 5. Customize configuration (optional)

Edit files in the `config/` directory:

- **`keywords.yaml`** — Add/remove/adjust keyword categories and weights
- **`sources.yaml`** — Add/remove tracked GitHub repos, change arXiv categories
- **`settings.yaml`** — Adjust scoring thresholds, email toggles, weekly summary settings

### 6. Enable GitHub Actions

Go to your repo → **Actions** tab → Enable workflows if prompted.

The daily update will run automatically at **08:00 UTC (16:00 Beijing Time)** every day.

### 7. Manual trigger

You can also trigger a run manually:
- Go to **Actions** → **Daily LLM Update** → **Run workflow**
- For weekly summary: comment `/weekly-summary` on any issue, or go to **Actions** → **Weekly LLM Summary** → **Run workflow**

## Project Structure

```
.github/workflows/
  daily-update.yml              # Daily cron job
  weekly-summary.yml            # Weekly summary (issue_comment + manual)
config/
  keywords.yaml                 # Keyword categories with weights
  sources.yaml                  # Data sources configuration
  settings.yaml                 # General settings
src/
  collectors/
    arxiv_collector.py          # arXiv API collection
    github_collector.py         # GitHub Trending + release tracking
    pwc_collector.py            # Papers with Code API
  filters/
    keyword_filter.py           # Keyword matching + scoring
  formatters/
    issue_formatter.py          # Markdown formatting for Issues
  notifiers/
    github_issue.py             # GitHub Issue creation via API
  state/
    dedup.py                    # Deduplication with seen.json
  modules/
    email_sender/               # Independent Module: Bilingual Email
      smtp_client.py            # Gmail SMTP wrapper
      translator.py             # Claude API translation (EN→CN)
      bilingual.py              # Bilingual send logic
    weekly_summary/             # Independent Module: Weekly Summary
      aggregator.py             # Aggregate past daily Issues
      ranker.py                 # Rank and select top items
      formatter.py              # Weekly summary formatting
  main.py                       # Daily update entry point
  weekly.py                     # Weekly summary entry point
data/
  seen.json                     # Dedup records (auto-updated)
```

## Local Testing

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export GITHUB_TOKEN="your_github_pat"
export GITHUB_REPOSITORY="your_username/updater-for-LLM-tech"
export GMAIL_ADDRESS="your_email@gmail.com"
export GMAIL_APP_PASSWORD="your_app_password"
export EMAIL_EN="english_recipient@example.com"
export EMAIL_CN="chinese_recipient@example.com"
export LLM_API_KEY="your_claude_api_key"

# Run daily update
python src/main.py

# Run weekly summary
python src/weekly.py
```

## How It Works

### Daily Update Flow

1. **Collect** — Fetch papers from arXiv, releases from tracked GitHub repos, trending repos, and papers from PWC
2. **Dedup** — Filter out items that were already sent in previous runs
3. **Filter** — Score each item against keyword categories, keep items above threshold
4. **Format** — Generate structured Markdown with scores and topic tags
5. **Notify** — Create a GitHub Issue labeled `daily-update`
6. **Email** — Send English version to Email A, translate and send Chinese version to Email B
7. **Persist** — Save seen item IDs to `data/seen.json` and commit

### Weekly Summary Flow

1. **Trigger** — Comment `/weekly-summary` on any issue, or manual trigger
2. **Aggregate** — Parse all `daily-update` Issues from the past 7 days
3. **Rank** — Score items by relevance, category breadth, and appearance frequency
4. **Format** — Generate a weekly digest with top highlights
5. **Notify** — Create a GitHub Issue labeled `weekly-summary`
6. **Email** — Send bilingual weekly digest emails

## License

MIT
