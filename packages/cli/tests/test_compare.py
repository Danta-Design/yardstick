"""Comparison behaviour: flips, deltas, and the significance guard."""

from __future__ import annotations

import json

import pytest

from yardstick.compare import CompareError, compare_runs, load_run


def _case(key: str, score: float) -> dict:
    return {
        "case_key": key,
        "input": f"question {key}",
        "expected": "expected",
        "output": "output",
        "scores": {"exact_match": score},
    }


def _run(scores: dict[str, float], content_hash: str = "hash-1", run_id: str = "run") -> dict:
    return {
        "run_id": run_id,
        "dataset": {"content_hash": content_hash},
        "cases": [_case(key, score) for key, score in scores.items()],
    }


def test_identical_runs_show_no_change() -> None:
    scores = {f"c{i}": 1.0 for i in range(10)}

    result = compare_runs(_run(scores), _run(scores))

    summary = result.metrics[0]
    assert summary.delta == 0
    assert summary.verdict == "no significant change"
    assert result.regressions == []
    assert result.has_significant_regression is False


def test_uniform_improvement_is_significant() -> None:
    before = {f"c{i}": 0.0 for i in range(10)}
    after = {f"c{i}": 1.0 for i in range(10)}

    result = compare_runs(_run(before), _run(after))

    summary = result.metrics[0]
    assert summary.delta == pytest.approx(1.0)
    assert summary.ci_low > 0
    assert summary.verdict == "better"
    assert len(result.improvements) == 10


def test_uniform_regression_is_significant() -> None:
    before = {f"c{i}": 1.0 for i in range(10)}
    after = {f"c{i}": 0.0 for i in range(10)}

    result = compare_runs(_run(before), _run(after))

    summary = result.metrics[0]
    assert summary.ci_high < 0
    assert summary.verdict == "worse"
    assert len(result.regressions) == 10
    assert result.has_significant_regression is True


def test_single_flip_is_reported_but_not_significant() -> None:
    before = {f"c{i}": 1.0 for i in range(10)}
    after = {f"c{i}": 1.0 for i in range(10)}
    after["c3"] = 0.0

    result = compare_runs(_run(before), _run(after))

    assert len(result.regressions) == 1
    assert result.regressions[0].case_key == "c3"
    # One flip in ten is a real signal for a human to read, but not statistically
    # distinguishable from noise — the interval must include zero.
    assert result.has_significant_regression is False


def test_dataset_hash_mismatch_is_flagged() -> None:
    result = compare_runs(_run({"a": 1.0}, "hash-1"), _run({"a": 1.0}, "hash-2"))

    assert result.comparable is False
    assert result.dataset_hash_a == "hash-1"
    assert result.dataset_hash_b == "hash-2"


def test_cases_present_in_only_one_run_are_listed() -> None:
    result = compare_runs(_run({"a": 1.0, "b": 1.0}), _run({"a": 1.0, "c": 1.0}))

    assert result.only_in_a == ["b"]
    assert result.only_in_b == ["c"]


def test_load_run_accepts_a_directory(tmp_path) -> None:
    run_dir = tmp_path / "run-1"
    run_dir.mkdir()
    (run_dir / "report.json").write_text(
        json.dumps(_run({"a": 1.0}, run_id="run-1")), encoding="utf-8"
    )

    assert load_run(run_dir)["run_id"] == "run-1"


def test_load_run_rejects_a_missing_report(tmp_path) -> None:
    with pytest.raises(CompareError, match="no report.json"):
        load_run(tmp_path / "nope")


def test_load_run_rejects_non_report_json(tmp_path) -> None:
    run_dir = tmp_path / "run-2"
    run_dir.mkdir()
    (run_dir / "report.json").write_text('{"hello": "world"}', encoding="utf-8")

    with pytest.raises(CompareError, match="not a Yardstick run report"):
        load_run(run_dir)
