"""Generate bilingual (EN + CN) key-point summaries for collected items via Claude API.

Instead of showing truncated abstracts/descriptions, this module asks Claude to
distill each item into 2-3 sentences highlighting what it does and why it matters.
Summaries are generated in a single batched API call for cost efficiency.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import anthropic

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-20250514"

SYSTEM_PROMPT = (
    "You are an expert AI/ML research analyst. Your job is to read paper abstracts "
    "and project descriptions, then write concise key-point summaries that help a "
    "busy researcher quickly decide whether each item is worth reading.\n\n"
    "Rules:\n"
    "- Write exactly 2-3 sentences per item.\n"
    "- First sentence: what the project/paper does (the core contribution).\n"
    "- Second/third sentence: why it matters, what problem it solves, or what makes it novel.\n"
    "- Be specific and informative, not vague.\n"
    "- Generate BOTH an English summary and a Chinese summary for each item.\n"
    "- The Chinese summary should be a natural Chinese version conveying the same key points, "
    "not a literal translation. Keep technical terms in English where appropriate.\n"
    "- Return ONLY valid JSON, no markdown fences, no extra text."
)


def _build_user_prompt(items_data: list[dict]) -> str:
    """Build the user message listing all items to summarize."""
    lines = [
        "Summarize each of the following items. Return a JSON array where each element has "
        '"id" (the item id I provide), "en" (English summary), and "cn" (Chinese summary).\n'
    ]
    for item in items_data:
        lines.append(f'--- Item id: {item["id"]} ---')
        lines.append(f'Title: {item["title"]}')
        lines.append(f'Text: {item["text"]}')
        lines.append("")

    lines.append(
        "Return ONLY the JSON array. Example format:\n"
        '[{"id": "arxiv:2401.00001", "en": "This paper ...", "cn": "..."}]'
    )
    return "\n".join(lines)


def _extract_text(item: Any) -> str:
    """Extract the abstract / description text from an item regardless of type."""
    # ArxivPaper / PwcPaper have 'abstract'; GitHubItem has 'description' + 'release_body'
    text = getattr(item, "abstract", "") or ""
    if not text:
        text = getattr(item, "description", "") or ""
    # For GitHub releases, release_body is usually more detailed
    release_body = getattr(item, "release_body", "") or ""
    if release_body and len(release_body) > len(text):
        text = release_body
    # Cap at 600 chars to keep the prompt size reasonable
    return text[:600]


def _parse_response(raw: str, expected_ids: set[str]) -> dict[str, dict[str, str]]:
    """Parse Claude's JSON response into {id: {"en": ..., "cn": ...}}.

    Tries hard to extract valid JSON even if there's surrounding text.
    """
    # Try direct parse first
    text = raw.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        # Remove opening fence (possibly ```json)
        first_newline = text.index("\n") if "\n" in text else 3
        text = text[first_newline + 1:]
    if text.endswith("```"):
        text = text[:-3].rstrip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON array in the text
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1 and end > start:
            try:
                data = json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                logger.error("Failed to parse summarizer response as JSON")
                return {}
        else:
            logger.error("No JSON array found in summarizer response")
            return {}

    result: dict[str, dict[str, str]] = {}
    if not isinstance(data, list):
        logger.error(f"Expected JSON array, got {type(data).__name__}")
        return {}

    for entry in data:
        if not isinstance(entry, dict):
            continue
        item_id = entry.get("id", "")
        en = entry.get("en", "")
        cn = entry.get("cn", "")
        if item_id and (en or cn):
            result[item_id] = {"en": en, "cn": cn}

    parsed_ids = set(result.keys())
    missing = expected_ids - parsed_ids
    if missing:
        logger.warning(f"Summarizer missed {len(missing)} items: {missing}")

    return result


class Summarizer:
    """Generate bilingual summaries for a batch of items using Claude API."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ):
        self.api_key = api_key or os.environ.get("LLM_API_KEY", "")
        self.model = model or DEFAULT_MODEL

        if not self.api_key:
            logger.warning("LLM_API_KEY not configured, summarization will be disabled")

    def summarize(self, items: list[Any]) -> None:
        """Generate EN + CN summaries and attach them to item objects in-place.

        Each item is expected to have:
          - unique_id (property): used as the identifier
          - title (str): item title
          - abstract or description (str): text to summarize
          - summary_en / summary_cn (str): fields to write results into

        On failure, items keep their default empty summary fields and the
        formatter will fall back to truncated abstracts.
        """
        if not self.api_key:
            logger.info("Skipping summarization: no API key")
            return

        if not items:
            return

        # Build lookup and prompt data
        id_to_item: dict[str, Any] = {}
        items_data: list[dict] = []

        for item in items:
            uid = item.unique_id
            text = _extract_text(item)
            if not text.strip():
                continue
            id_to_item[uid] = item
            items_data.append({
                "id": uid,
                "title": item.title,
                "text": text,
            })

        if not items_data:
            logger.info("No items with text to summarize")
            return

        logger.info(f"Summarizing {len(items_data)} items via Claude API...")

        # If many items, split into batches to stay within token limits
        # Empirically, ~30 items per batch keeps input well under limits
        BATCH_SIZE = 30
        all_summaries: dict[str, dict[str, str]] = {}

        for batch_start in range(0, len(items_data), BATCH_SIZE):
            batch = items_data[batch_start:batch_start + BATCH_SIZE]
            batch_summaries = self._call_api(batch)
            all_summaries.update(batch_summaries)

        # Attach summaries to items
        attached = 0
        for uid, summaries in all_summaries.items():
            item = id_to_item.get(uid)
            if item:
                item.summary_en = summaries.get("en", "")
                item.summary_cn = summaries.get("cn", "")
                attached += 1

        logger.info(
            f"Summarization complete: {attached}/{len(items_data)} items got summaries"
        )

    def _call_api(self, items_data: list[dict]) -> dict[str, dict[str, str]]:
        """Make a single Claude API call for a batch of items."""
        expected_ids = {d["id"] for d in items_data}
        user_prompt = _build_user_prompt(items_data)

        try:
            client = anthropic.Anthropic(api_key=self.api_key)
            message = client.messages.create(
                model=self.model,
                max_tokens=8192,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
            raw = message.content[0].text
            logger.info(
                f"Summarizer API call: {len(user_prompt)} chars in, "
                f"{len(raw)} chars out"
            )
            return _parse_response(raw, expected_ids)

        except anthropic.APIError as e:
            logger.error(f"Claude API error during summarization: {e}")
            return {}
        except Exception as e:
            logger.error(f"Summarization failed: {e}")
            return {}
