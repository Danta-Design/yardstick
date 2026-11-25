"""The runner: bounded concurrency, retries, and per-case scoring."""

from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime, timezone

from .config import Config
from .datasets import Dataset
from .metrics import compute_metric
from .report import CaseResult, RunReport
from .targets import Target, TargetError


class Runner:
    """Execute every case against a target and collect a report."""

    def __init__(self, config: Config, dataset: Dataset, target: Target) -> None:
        self._config = config
        self._dataset = dataset
        self._target = target

    async def run(self) -> RunReport:
        started_at = datetime.now(timezone.utc)
        began = time.perf_counter()

        semaphore = asyncio.Semaphore(self._config.concurrency)
        try:
            results = await asyncio.gather(
                *(self._run_case(case, semaphore) for case in self._dataset.cases)
            )
        finally:
            await self._target.aclose()

        duration = time.perf_counter() - began
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
            metrics=_aggregate(list(results), self._config.metrics),
            error_rate=_error_rate(list(results)),
            results=list(results),
            gate={
                "primary_metric": self._config.metrics[0],
                "min_score": self._config.gate.min_score,
                "max_error_rate": self._config.gate.max_error_rate,
            },
        )

    async def _run_case(self, case, semaphore: asyncio.Semaphore) -> CaseResult:
        async with semaphore:
            began = time.perf_counter()
            last_error: str | None = None

            for attempt in range(self._config.retries + 1):
                try:
                    output = await self._target.call(case)
                    latency_ms = (time.perf_counter() - began) * 1000
                    scores = self._score(case, output)
                    return CaseResult(case, output, None, latency_ms, scores)
                except TargetError as exc:
                    last_error = str(exc)
                    if attempt < self._config.retries:
                        await asyncio.sleep(min(2**attempt, 8) * 0.5)

            latency_ms = (time.perf_counter() - began) * 1000
            return CaseResult(case, None, last_error, latency_ms, {})

    def _score(self, case, output: str) -> dict[str, float]:
        if case.expected is None:
            return {}
        return {
            metric: compute_metric(metric, output, case.expected)
            for metric in self._config.metrics
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
