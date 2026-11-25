"""LLM-as-judge: rubric scoring with variance controls.

Judged metrics are the only nondeterministic part of Yardstick, so every source
of noise is handled explicitly rather than averaged away:

- a versioned rubric file (its hash is part of the cache key and the report),
- fixed temperature and a strict JSON contract,
- N independent samples with a median, not a mean,
- an optional second model whose disagreement flags a case for human review,
- a content-addressed cache so an unchanged re-run costs nothing.
"""

from __future__ import annotations

import hashlib
import json
import os
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from .config import ConfigError, JudgeConfig
from .datasets import Case

PROMPT_TEMPLATE = """\
You are grading the answer of an AI assistant.

## Rubric
{rubric}

## Question
{question}

## Reference answer
{reference}

## Answer to grade
{answer}

Grade the answer against the rubric. Use the whole scale and do not be generous
by default.

Reply with JSON only, no prose and no code fences:
{{"score": <integer from 1 to {scale}>, "reason": "<one or two sentences>", \
"failed_criteria": ["<criterion that failed, if any>"]}}
"""


class JudgeError(RuntimeError):
    """The judge could not produce a usable score for a case."""


@dataclass(frozen=True)
class JudgeResult:
    """One case, judged."""

    score: float
    raw_score: float
    reason: str
    model: str
    samples: tuple[int, ...]
    needs_review: bool = False
    cached: bool = False
    secondary_raw_score: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": round(self.score, 4),
            "raw_score": self.raw_score,
            "reason": self.reason,
            "model": self.model,
            "samples": list(self.samples),
            "needs_review": self.needs_review,
            "cached": self.cached,
            "secondary_raw_score": self.secondary_raw_score,
        }


def load_rubric(path: Path) -> str:
    """Read a rubric file and reject empty or placeholder rubrics."""
    text = path.read_text(encoding="utf-8").strip()
    if len(text) < 40:
        raise ConfigError(f"rubric {path} is too short to be useful ({len(text)} chars)")
    return text


def build_prompt(rubric: str, case: Case, answer: str, scale: int) -> str:
    reference = case.expected if case.expected is not None else "No reference answer provided."
    return PROMPT_TEMPLATE.format(
        rubric=rubric,
        question=case.input,
        reference=reference,
        answer=answer,
        scale=scale,
    )


def parse_judgement(text: str, scale: int) -> tuple[int, str]:
    """Extract ``(score, reason)`` from a model reply, tolerating stray prose."""
    payload = _first_json_object(text)
    if payload is None:
        raise JudgeError("judge reply contained no JSON object")

    raw = payload.get("score")
    if isinstance(raw, bool) or not isinstance(raw, int | float):
        raise JudgeError(f"judge score is not a number: {raw!r}")
    score = int(raw)
    if not 1 <= score <= scale:
        raise JudgeError(f"judge score {score} outside 1..{scale}")

    reason = str(payload.get("reason", "")).strip()
    return score, reason[:500]


def _first_json_object(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[1] if "\n" in stripped else stripped
        stripped = stripped.rsplit("```", 1)[0]

    decoder = json.JSONDecoder()
    for index, char in enumerate(stripped):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(stripped[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None


class Judge:
    """Scores answers with one or two models, cached and de-noised."""

    def __init__(
        self,
        config: JudgeConfig,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._config = config
        self._rubric = load_rubric(config.rubric)
        self._rubric_hash = hashlib.sha256(self._rubric.encode("utf-8")).hexdigest()

        api_key = os.environ.get(config.api_key_env)
        if not api_key:
            raise ConfigError(
                f"environment variable {config.api_key_env!r} is not set; "
                "the judge needs an API key"
            )

        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        self._client = httpx.AsyncClient(
            base_url=config.base_url.rstrip("/"),
            headers=headers,
            timeout=config.timeout_s,
            transport=transport,
        )
        self._cache_dir = Path(config.cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    @property
    def rubric_hash(self) -> str:
        return self._rubric_hash

    @property
    def model(self) -> str:
        return self._config.model

    @property
    def samples(self) -> int:
        return self._config.samples

    async def score(self, case: Case, answer: str) -> JudgeResult:
        primary = await self._score_with(self._config.model, case, answer)
        secondary = None
        needs_review = False

        if self._config.secondary_model:
            secondary = await self._score_with(self._config.secondary_model, case, answer)
            needs_review = (
                abs(primary.raw - secondary.raw) >= self._config.disagreement_threshold
            )

        scale = self._config.scale
        return JudgeResult(
            score=(primary.raw - 1) / (scale - 1),
            raw_score=primary.raw,
            reason=primary.reason,
            model=self._config.model,
            samples=primary.samples,
            needs_review=needs_review,
            cached=primary.cached and (secondary.cached if secondary else True),
            secondary_raw_score=secondary.raw if secondary else None,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _score_with(self, model: str, case: Case, answer: str) -> _Sample:
        prompt = build_prompt(self._rubric, case, answer, self._config.scale)
        raw_scores: list[int] = []
        reasons: list[str] = []
        cached_flags: list[bool] = []

        for index in range(self._config.samples):
            key = self._cache_key(model, prompt, index)
            hit = self._read_cache(key)
            if hit is not None:
                raw_scores.append(hit[0])
                reasons.append(hit[1])
                cached_flags.append(True)
                continue

            score, reason = await self._ask(model, prompt)
            self._write_cache(key, score, reason)
            raw_scores.append(score)
            reasons.append(reason)
            cached_flags.append(False)

        median = statistics.median(raw_scores)
        # Report the reason closest to the median score, so it explains the number.
        representative = next(
            (reason for reason, raw in zip(reasons, raw_scores, strict=True) if raw == median),
            reasons[0],
        )
        return _Sample(
            raw=median,
            reason=representative,
            samples=tuple(raw_scores),
            cached=all(cached_flags),
        )

    async def _ask(self, model: str, prompt: str) -> tuple[int, str]:
        body: dict[str, Any] = {
            "model": model,
            "temperature": self._config.temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        try:
            response = await self._client.post("/chat/completions", json=body)
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
        except httpx.HTTPError as exc:
            raise JudgeError(f"judge request failed: {exc}") from exc
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise JudgeError(f"unexpected judge response shape: {exc}") from exc

        return parse_judgement(content, self._config.scale)

    def _cache_key(self, model: str, prompt: str, index: int) -> str:
        material = f"{model}|{self._rubric_hash}|{prompt}|{index}"
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    def _read_cache(self, key: str) -> tuple[int, str] | None:
        path = self._cache_dir / f"{key}.json"
        if not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return int(payload["score"]), str(payload["reason"])
        except (ValueError, KeyError, TypeError):
            return None  # a corrupt cache entry is a miss, not a crash

    def _write_cache(self, key: str, score: int, reason: str) -> None:
        path = self._cache_dir / f"{key}.json"
        path.write_text(
            json.dumps({"score": score, "reason": reason}, ensure_ascii=False),
            encoding="utf-8",
        )


@dataclass(frozen=True)
class _Sample:
    raw: float
    reason: str
    samples: tuple[int, ...]
    cached: bool
