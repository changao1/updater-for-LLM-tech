"""Rank and select top items for the weekly summary."""

from __future__ import annotations

import logging

from .aggregator import AggregatedItem

logger = logging.getLogger(__name__)


def rank_items(items: list[AggregatedItem], top_n: int = 20) -> list[AggregatedItem]:
    """Rank aggregated items by weighted score and select top N.

    Ranking criteria:
    1. weighted_score (relevance * appearance boost)
    2. Number of topic categories matched (breadth)
    3. Number of appearances across daily issues (persistence)

    Args:
        items: List of AggregatedItem from the aggregator.
        top_n: Maximum number of items to return.

    Returns:
        Top N items sorted by rank.
    """
    # Sort by (weighted_score desc, categories count desc, appearances desc)
    ranked = sorted(
        items,
        key=lambda x: (
            x.weighted_score,
            len(x.matched_categories),
            x.appearances,
        ),
        reverse=True,
    )

    top = ranked[:top_n]
    logger.info(f"Ranked {len(items)} items, selected top {len(top)}")
    return top
