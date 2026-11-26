"""The runner: bounded concurrency, retries, and per-case scoring."""

from __future__ import annotations

import asyncio
import time
import uuid
from datetime import UTC, datetime

from .config import Config
from .datasets import Dataset
from .judge import Judge, JudgeError
from .metrics import compute_metric
from .report import CaseResult, RunReport
from .targets import Target, TargetError


class Runner:
    """Execute every case against a target and collect a report."""

    def __init__(
        self,
        config: Config,
        dataset: Dataset,
        target: Target,
        judge: Judge | None = None,
    ) -> None:
        self._config = config
        self._dataset = dataset
        self._target = target
        self._judge = judge

    async def run(self) -> RunReport:
        started_at = datetime.now(UTC)
        began = time.perf_counter()

        semaphore = asyncio.Semaphore(self._config.concurrency)
        try:
            results = await asyncio.gather(
                *(self._run_case(case, semaphore) for case in self._dataset.cases)
            )
        finally:
            await self._target.aclose()
            if self._judge is not None:
                await self._judge.aclose()

        duration = time.perf_counter() - began
        results_list = list(results)
        return RunReport(
            run_id=_new_run_id(started_at),
            started_at=started_at.isoformat(timespec="seconds"),
            duration_s=duration,
            config_name=self._config.name,
            dataset=self._dataset.summary(),
            target={
                "type": self._config.target.type,
                "url": self._config.target.url,
                "callable": self._config.target.callable,
            },
            metrics=_aggregate(results_list, self._config.metrics),
            error_rate=_error_rate(results_list),
            results=results_list,
            gate={
                "primary_metric": self._config.metrics[0],
                "min_score": self._config.gate.min_score,
                "max_error_rate": self._config.gate.max_error_rate,
            },
            judge=self._judge_summary(results_list),
        )

    async def _run_case(self, case, semaphore: asyncio.Semaphore) -> CaseResult:
        async with semaphore:
            began = time.perf_counter()
            last_error: str | None = None

            for attempt in range(self._config.retries + 1):
                try:
                    output = await self._target.call(case)
                    latency_ms = (time.perf_counter() - began) * 1000
                    scores, judgement, judge_error = await self._score(case, output)
                    return CaseResult(
                        case, output, None, latency_ms, scores, judgement, judge_error
                    )
                except TargetError as exc:
                    last_error = str(exc)
                    if attempt < self._config.retries:
                        await asyncio.sleep(min(2**attempt, 8) * 0.5)

            latency_ms = (time.perf_counter() - began) * 1000
            return CaseResult(case, None, last_error, latency_ms, {})

    async def _score(
        self, case, output: str
    ) -> tuple[dict[str, float], dict | None, str | None]:
        scores: dict[str, float] = {}
        if case.expected is not None:
            for metric in self._config.metrics:
                if metric == "judge":
                    continue
                scores[metric] = compute_metric(metric, output, case.expected)

        if self._judge is None or "judge" not in self._config.metrics:
            return scores, None, None

        try:
            result = await self._judge.score(case, output)
        except JudgeError as exc:
            return scores, None, str(exc)

        scores["judge"] = result.score
        return scores, result.to_dict(), None

    def _judge_summary(self, results: list[CaseResult]) -> dict | None:
        if self._judge is None:
            return None
        judged = [result for result in results if result.judge is not None]
        return {
            "model": self._judge.model,
            "rubric_hash": self._judge.rubric_hash,
            "samples": self._judge.samples,
            "judged_cases": len(judged),
            "needs_review": sum(1 for result in judged if result.judge["needs_review"]),
            "cache_hits": sum(1 for result in judged if result.judge["cached"]),
        }


def _aggregate(results: list[CaseResult], metrics: list[str]) -> dict[str, float | None]:
    aggregate: dict[str, float | None] = {}
    for metric in metrics:
        values = [result.scores[metric] for result in results if metric in result.scores]
        aggregate[metric] = sum(values) / len(values) if values else None
    return aggregate


def _error_rate(results: list[CaseResult]) -> float:
    if not results:
        return 0.0
    return sum(1 for result in results if not result.ok) / len(results)


def _new_run_id(started_at: datetime) -> str:
    return f"{started_at:%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:6]}"
