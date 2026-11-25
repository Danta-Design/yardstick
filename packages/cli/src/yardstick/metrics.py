"""Deterministic metrics.

Nothing here calls a model. These functions must be pure and stable: the same
inputs always produce the same score, forever. If a normalization rule changes,
every historical score changes with it — so the rules are written down in
docs/metrics.md and changed only alongside a dataset version bump.
"""

from __future__ import annotations

import string
import unicodedata
from collections import Counter

_EXTRA_PUNCTUATION = "，。！？、；：""''（）《》【】…—·「」『』〈〉"


def normalize(text: str) -> str:
    """Lowercase, drop punctuation, collapse whitespace."""
    normalized = unicodedata.normalize("NFKC", text).lower()
    table = str.maketrans("", "", string.punctuation + _EXTRA_PUNCTUATION)
    return " ".join(normalized.translate(table).split())


def exact_match(prediction: str, expected: str) -> float:
    """1.0 when the normalized strings are identical, else 0.0."""
    return 1.0 if normalize(prediction) == normalize(expected) else 0.0


def token_f1(prediction: str, expected: str) -> float:
    """F1 over normalized token multisets."""
    predicted_tokens = normalize(prediction).split()
    expected_tokens = normalize(expected).split()
    if not predicted_tokens or not expected_tokens:
        return 0.0

    overlap = sum((Counter(predicted_tokens) & Counter(expected_tokens)).values())
    if overlap == 0:
        return 0.0

    precision = overlap / len(predicted_tokens)
    recall = overlap / len(expected_tokens)
    return 2 * precision * recall / (precision + recall)


METRICS = {
    "exact_match": exact_match,
    "token_f1": token_f1,
}


class UnknownMetricError(ValueError):
    """Raised when a config references a metric that does not exist."""


def compute_metric(name: str, prediction: str, expected: str) -> float:
    try:
        metric = METRICS[name]
    except KeyError:
        available = ", ".join(sorted(METRICS))
        raise UnknownMetricError(f"unknown metric {name!r}; available: {available}") from None
    return metric(prediction, expected)
