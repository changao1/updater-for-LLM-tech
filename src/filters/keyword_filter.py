"""Keyword-based filtering and relevance scoring for collected items."""

import logging
import re
from dataclasses import dataclass, field

import yaml

logger = logging.getLogger(__name__)


@dataclass
class KeywordCategory:
    """A category of keywords with associated weight."""

    name: str
    weight: float
    terms: list[str]
    # Pre-compiled regex patterns for each term
    patterns: list[re.Pattern] = field(default_factory=list)

    def __post_init__(self):
        if not self.patterns:
            for term in self.terms:
                # Word boundary matching, case insensitive
                pattern = re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)
                self.patterns.append(pattern)


def load_keywords(config_path: str) -> list[KeywordCategory]:
    """Load keyword categories from the keywords.yaml config file.

    Args:
        config_path: Path to keywords.yaml.

    Returns:
        List of KeywordCategory objects.
    """
    with open(config_path, "r") as f:
        data = yaml.safe_load(f)

    categories = []
    for name, cat_config in data.items():
        weight = cat_config.get("weight", 1.0)
        terms = cat_config.get("terms", [])
        categories.append(KeywordCategory(name=name, weight=weight, terms=terms))

    logger.info(f"Loaded {len(categories)} keyword categories")
    return categories


def score_text(text: str, categories: list[KeywordCategory]) -> tuple[float, list[str]]:
    """Score a text block against keyword categories.

    Args:
        text: The text to score (typically title + abstract/description).
        categories: List of KeywordCategory to match against.

    Returns:
        Tuple of (total_score, list_of_matched_category_names).
    """
    total_score = 0.0
    matched_cats = []

    for cat in categories:
        cat_matches = 0
        for pattern in cat.patterns:
            if pattern.search(text):
                cat_matches += 1

        if cat_matches > 0:
            # Score: number of matched terms * category weight
            # Diminishing returns: sqrt to avoid overweighting many matches
            cat_score = (cat_matches ** 0.5) * cat.weight
            total_score += cat_score
            matched_cats.append(cat.name)

    return round(total_score, 2), matched_cats


def filter_items(items: list, categories: list[KeywordCategory], min_score: float = 1.0) -> list:
    """Filter and score a list of items based on keyword relevance.

    Items must have 'title' and ('abstract' or 'description') attributes,
    plus 'relevance_score' and 'matched_categories' attributes to be set.

    Args:
        items: List of dataclass items (ArxivPaper, GitHubItem, PwcPaper).
        categories: Keyword categories for scoring.
        min_score: Minimum score threshold to include.

    Returns:
        Filtered and sorted list of items (highest score first).
    """
    scored = []
    for item in items:
        # Build text to score against
        text_parts = [getattr(item, "title", "")]

        # Check various description fields
        for field in ["abstract", "description", "release_body"]:
            val = getattr(item, field, "")
            if val:
                text_parts.append(val)

        text = " ".join(text_parts)
        score, matched = score_text(text, categories)

        if score >= min_score:
            item.relevance_score = score
            item.matched_categories = matched
            scored.append(item)

    # Sort by score descending
    scored.sort(key=lambda x: x.relevance_score, reverse=True)

    logger.info(f"Filtered {len(items)} items down to {len(scored)} (min_score={min_score})")
    return scored
