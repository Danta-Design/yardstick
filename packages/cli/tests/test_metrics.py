from __future__ import annotations

import pytest

from yardstick.metrics import UnknownMetricError, compute_metric, exact_match, normalize, token_f1


def test_normalize_strips_case_punctuation_and_whitespace() -> None:
    assert normalize("  Hello,   World!  ") == "hello world"


def test_normalize_handles_chinese_punctuation() -> None:
    assert normalize("你好，世界！") == "你好世界"


def test_exact_match_ignores_surface_noise() -> None:
    assert exact_match("10 GB。", "10 GB") == 1.0
    assert exact_match("10 GB", "20 GB") == 0.0
    # Spacing is meaningful: "10 GB" is two tokens, "10GB" is one.
    assert exact_match("10 GB", "10GB") == 0.0


def test_token_f1_perfect_and_partial() -> None:
    assert token_f1("red green blue", "red green blue") == 1.0
    partial = token_f1("red green", "red green blue")
    assert pytest.approx(partial, rel=1e-6) == 0.8


def test_token_f1_no_overlap_is_zero() -> None:
    assert token_f1("alpha", "beta") == 0.0


def test_token_f1_empty_input_is_zero() -> None:
    assert token_f1("", "anything") == 0.0


def test_compute_metric_rejects_unknown_name() -> None:
    with pytest.raises(UnknownMetricError, match="unknown metric"):
        compute_metric("rouge_9", "a", "b")
