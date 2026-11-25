"""End-to-end: dataset file -> config -> runner -> report. No network."""

from __future__ import annotations

import json

import pytest

from yardstick.config import Config
from yardstick.datasets import load_dataset
from yardstick.runner import Runner
from yardstick.targets import build_target


def _dataset(tmp_path, rows):
    path = tmp_path / "data.jsonl"
    payload = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    path.write_text(payload, encoding="utf-8")
    return load_dataset(path)


def _config(dataset_path, callable_path: str, **overrides) -> Config:
    base = {
        "name": "test",
        "dataset": dataset_path,
        "target": {"type": "python", "callable": callable_path},
        "metrics": ["exact_match"],
        "concurrency": 4,
        "retries": 1,
    }
    base.update(overrides)
    return Config.model_validate(base)


@pytest.mark.asyncio
async def test_perfect_score_end_to_end(tmp_path) -> None:
    dataset = _dataset(
        tmp_path,
        [
            {"case_key": "a", "input": "red", "expected": "RED"},
            {"case_key": "b", "input": "blue", "expected": "BLUE"},
        ],
    )
    config = _config(dataset.path, "tests.fixtures.fake_target:shout")

    report = await Runner(config, dataset, build_target(config.target)).run()

    assert report.metrics["exact_match"] == 1.0
    assert report.error_rate == 0.0
    assert report.gate_failures() == []


@pytest.mark.asyncio
async def test_partial_score_end_to_end(tmp_path) -> None:
    dataset = _dataset(
        tmp_path,
        [
            {"case_key": "a", "input": "red", "expected": "RED"},
            {"case_key": "b", "input": "blue", "expected": "GREEN"},
        ],
    )
    config = _config(dataset.path, "tests.fixtures.fake_target:shout")

    report = await Runner(config, dataset, build_target(config.target)).run()

    assert report.metrics["exact_match"] == 0.5


@pytest.mark.asyncio
async def test_async_target_is_supported(tmp_path) -> None:
    dataset = _dataset(tmp_path, [{"case_key": "a", "input": "red", "expected": "RED"}])
    config = _config(dataset.path, "tests.fixtures.fake_target:shout_async")

    report = await Runner(config, dataset, build_target(config.target)).run()

    assert report.metrics["exact_match"] == 1.0


@pytest.mark.asyncio
async def test_target_failure_becomes_error_rate_not_a_crash(tmp_path) -> None:
    dataset = _dataset(tmp_path, [{"case_key": "a", "input": "red", "expected": "RED"}])
    config = _config(dataset.path, "tests.fixtures.fake_target:explode", retries=1)

    report = await Runner(config, dataset, build_target(config.target)).run()

    assert report.error_rate == 1.0
    assert "target is down" in (report.results[0].error or "")


@pytest.mark.asyncio
async def test_gate_failure_is_reported(tmp_path) -> None:
    dataset = _dataset(
        tmp_path,
        [
            {"case_key": "a", "input": "red", "expected": "RED"},
            {"case_key": "b", "input": "blue", "expected": "GREEN"},
        ],
    )
    config = _config(dataset.path, "tests.fixtures.fake_target:shout", gate={"min_score": 0.9})

    report = await Runner(config, dataset, build_target(config.target)).run()

    failures = report.gate_failures()
    assert len(failures) == 1
    assert "min_score" in failures[0]
