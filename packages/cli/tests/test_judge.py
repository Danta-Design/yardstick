"""Judge behaviour: parsing, sampling, caching, and disagreement flagging.

No network: every request goes through an httpx MockTransport.
"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from yardstick.config import ConfigError, JudgeConfig
from yardstick.datasets import Case
from yardstick.judge import Judge, JudgeError, build_prompt, parse_judgement

RUBRIC = """\
# Answer quality

## Correctness
- 5: fully correct and complete
- 3: mostly correct, one omission
- 1: wrong or unrelated

Count an answer as failed if it contradicts the reference answer.
"""


@pytest.fixture
def rubric_path(tmp_path):
    path = tmp_path / "rubric.md"
    path.write_text(RUBRIC, encoding="utf-8")
    return path


def _judge_config(rubric_path, **overrides) -> JudgeConfig:
    options = {
        "model": "judge-a",
        "rubric": rubric_path,
        "api_key_env": "YARDSTICK_TEST_KEY",
        "samples": 1,
        "cache_dir": rubric_path.parent / "cache",
    }
    options.update(overrides)
    return JudgeConfig.model_validate(options)


def _reply(score: int, reason: str = "fine") -> httpx.Response:
    content = json.dumps({"score": score, "reason": reason})
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


@pytest.fixture(autouse=True)
def _api_key(monkeypatch):
    monkeypatch.setenv("YARDSTICK_TEST_KEY", "test-key")


def test_parse_plain_json() -> None:
    assert parse_judgement('{"score": 4, "reason": "good"}', 5) == (4, "good")


def test_parse_fenced_json() -> None:
    text = '```json\n{"score": 2, "reason": "missing detail"}\n```'
    assert parse_judgement(text, 5) == (2, "missing detail")


def test_parse_tolerates_leading_prose() -> None:
    text = 'Here is my grade: {"score": 3, "reason": "ok"} hope that helps'
    assert parse_judgement(text, 5) == (3, "ok")


def test_parse_rejects_out_of_range_score() -> None:
    with pytest.raises(JudgeError, match="outside"):
        parse_judgement('{"score": 9, "reason": "x"}', 5)


def test_parse_rejects_non_numeric_score() -> None:
    with pytest.raises(JudgeError, match="not a number"):
        parse_judgement('{"score": "high"}', 5)


def test_prompt_contains_rubric_question_and_answer() -> None:
    case = Case(case_key="a", input="What is the refund window?", expected="30 days")
    prompt = build_prompt(RUBRIC, case, "14 days", 5)

    assert "Correctness" in prompt
    assert "What is the refund window?" in prompt
    assert "30 days" in prompt
    assert "14 days" in prompt


def test_prompt_handles_missing_reference_answer() -> None:
    case = Case(case_key="a", input="q")
    assert "No reference answer" in build_prompt(RUBRIC, case, "a", 5)


def test_score_is_normalized_to_unit_interval(rubric_path) -> None:
    transport = httpx.MockTransport(lambda request: _reply(4))

    async def run() -> float:
        judge = Judge(_judge_config(rubric_path), transport=transport)
        try:
            result = await judge.score(Case(case_key="a", input="q"), "answer")
        finally:
            await judge.aclose()
        return result.score

    assert asyncio.run(run()) == pytest.approx(0.75)


def test_sampling_takes_the_median(rubric_path) -> None:
    scores = iter([2, 4, 4])
    transport = httpx.MockTransport(lambda request: _reply(next(scores)))

    async def run():
        judge = Judge(_judge_config(rubric_path, samples=3), transport=transport)
        try:
            return await judge.score(Case(case_key="a", input="q"), "answer")
        finally:
            await judge.aclose()

    result = asyncio.run(run())
    assert result.raw_score == 4
    assert result.samples == (2, 4, 4)


def test_second_run_is_served_from_cache(rubric_path) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return _reply(5)

    transport = httpx.MockTransport(handler)

    async def run():
        judge = Judge(_judge_config(rubric_path), transport=transport)
        try:
            case = Case(case_key="a", input="q")
            first = await judge.score(case, "answer")
            second = await judge.score(case, "answer")
        finally:
            await judge.aclose()
        return first, second

    first, second = asyncio.run(run())
    assert calls["n"] == 1
    assert first.cached is False
    assert second.cached is True


def test_disagreeing_models_are_flagged_for_review(rubric_path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        return _reply(5 if body["model"] == "judge-a" else 2)

    transport = httpx.MockTransport(handler)

    async def run():
        config = _judge_config(rubric_path, secondary_model="judge-b")
        judge = Judge(config, transport=transport)
        try:
            return await judge.score(Case(case_key="a", input="q"), "answer")
        finally:
            await judge.aclose()

    result = asyncio.run(run())
    assert result.needs_review is True
    assert result.raw_score == 5
    assert result.secondary_raw_score == 2


def test_missing_api_key_is_a_config_error(rubric_path, monkeypatch) -> None:
    monkeypatch.delenv("YARDSTICK_TEST_KEY", raising=False)
    with pytest.raises(ConfigError, match="YARDSTICK_TEST_KEY"):
        Judge(_judge_config(rubric_path))
