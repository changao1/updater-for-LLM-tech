"""Append structured run records to data/run-log.json after each workflow run."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_PATH = Path(__file__).parent.parent.parent / "data" / "run-log.json"

# Keep only the last N run records to prevent unbounded growth
MAX_RECORDS = 200


def append_run_record(
    run_type: str,
    collected: dict[str, int],
    after_dedup: dict[str, int],
    after_filter: dict[str, int],
    issue_url: str | None = None,
    email_results: dict[str, bool] | None = None,
    errors: list[str] | None = None,
    path: str | Path = DEFAULT_PATH,
) -> None:
    """Append a run record to the run log.

    Args:
        run_type: "daily" or "weekly".
        collected: Raw item counts per source, e.g. {"arxiv": 45, "github": 12, "pwc": 30}.
        after_dedup: Item counts after deduplication.
        after_filter: Item counts after keyword filtering.
        issue_url: URL of the created GitHub Issue (if any).
        email_results: Email send status, e.g. {"en": True, "cn": True}.
        errors: List of error messages encountered during the run.
        path: Path to the run-log.json file.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing records
    records = []
    if path.exists():
        try:
            with open(path, "r") as f:
                records = json.load(f)
                if not isinstance(records, list):
                    records = []
        except (json.JSONDecodeError, TypeError):
            records = []

    # Build new record
    record = {
        "date": datetime.now(timezone.utc).isoformat(),
        "type": run_type,
        "collected": collected,
        "after_dedup": after_dedup,
        "after_filter": after_filter,
        "issue_url": issue_url or "",
        "email": email_results or {"en": False, "cn": False},
        "errors": errors or [],
    }

    records.append(record)

    # Prune old records if too many
    if len(records) > MAX_RECORDS:
        records = records[-MAX_RECORDS:]

    # Write back
    with open(path, "w") as f:
        json.dump(records, f, indent=2)

    logger.info(f"Run record appended to {path} (total: {len(records)} records)")
