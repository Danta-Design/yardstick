"""Compare two runs.

The question this module answers is not "what is the score" but "what changed".
An aggregate delta alone hides regressions: a run can gain two points overall
while quietly failing the twenty hardest cases. So comparison reports three
things, in this order of importance:

1. the per-case flips (which cases passed before and fail now),
2. the aggregate delta per metric,
3. whether that delta is larger than the noise, via a bootstrap confidence
   interval. If the interval crosses zero, the honest answer is "no significant
   change", even when the raw number moved.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean
from typing import Any

from rich.console import Console
from rich.table import Table


class CompareError(ValueError):
    """The two runs cannot be compared, or a run cannot be read."""


@dataclass
class CaseDiff:
    """One case, as it appears in both runs."""

    case_key: str
    input: str
    expected: str | None
    before_output: str | None
    after_output: str | None
    before: dict[str, float]
    after: dict[str, float]

    def delta(self, metric: str) -> float | None:
        if metric not in self.before or metric not in self.after:
            return None
        return self.after[metric] - self.before[metric]

    def status(self, metric: str, epsilon: float = 1e-9) -> str:
        delta = self.delta(metric)
        if delta is None:
            return "incomparable"
        if delta > epsilon:
            return "improved"
        if delta < -epsilon:
            return "regressed"
        return "unchanged"


@dataclass
class MetricSummary:
    """Aggregate view of one metric across all comparable cases."""

    metric: str
    before: float | None
    after: float | None
    delta: float | None
    ci_low: float | None
    ci_high: float | None
    improved: int = 0
    regressed: int = 0
    unchanged: int = 0
    incomparable: int = 0

    @property
    def significant(self) -> bool:
        if self.ci_low is None or self.ci_high is None:
            return False
        return self.ci_low > 0 or self.ci_high < 0

    @property
    def verdict(self) -> str:
        if self.delta is None:
            return "no data"
        if not self.significant:
            return "no significant change"
        return "better" if self.delta > 0 else "worse"


@dataclass
class CompareResult:
    run_a_id: str
    run_b_id: str
    comparable: bool
    dataset_hash_a: str
    dataset_hash_b: str
    metrics: list[MetricSummary] = field(default_factory=list)
    regressions: list[CaseDiff] = field(default_factory=list)
    improvements: list[CaseDiff] = field(default_factory=list)
    only_in_a: list[str] = field(default_factory=list)
    only_in_b: list[str] = field(default_factory=list)

    @property
    def has_significant_regression(self) -> bool:
        return any(m.delta is not None and m.significant and m.delta < 0 for m in self.metrics)


def load_run(target: str | Path, runs_dir: Path = Path("runs")) -> dict[str, Any]:
    """Accept either a run directory or a run id under ``runs_dir``."""
    path = Path(target)
    if not path.is_dir():
        path = runs_dir / str(target)
    report = path / "report.json"
    if not report.is_file():
        raise CompareError(f"no report.json in {path}")
    try:
        payload = json.loads(report.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CompareError(f"{report} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict) or "cases" not in payload:
        raise CompareError(f"{report} is not a Yardstick run report")
    return payload


def compare_runs(
    run_a: dict[str, Any],
    run_b: dict[str, Any],
    resamples: int = 1000,
    seed: int = 0,
) -> CompareResult:
    """Compare ``run_b`` against ``run_a`` (a = before, b = after)."""
    hash_a = run_a.get("dataset", {}).get("content_hash", "")
    hash_b = run_b.get("dataset", {}).get("content_hash", "")
    comparable = bool(hash_a) and hash_a == hash_b

    cases_a = {case["case_key"]: case for case in run_a["cases"]}
    cases_b = {case["case_key"]: case for case in run_b["cases"]}

    diffs: list[CaseDiff] = []
    for key in cases_a.keys() & cases_b.keys():
        first, second = cases_a[key], cases_b[key]
        diffs.append(
            CaseDiff(
                case_key=key,
                input=second.get("input", first.get("input", "")),
                expected=second.get("expected", first.get("expected")),
                before_output=first.get("output"),
                after_output=second.get("output"),
                before=first.get("scores", {}),
                after=second.get("scores", {}),
            )
        )

    metrics = sorted(
        {metric for diff in diffs for metric in diff.before} & {
            metric for diff in diffs for metric in diff.after
        }
    )

    summaries: list[MetricSummary] = []
    for metric in metrics:
        summary = MetricSummary(
            metric=metric,
            before=_average(diff.before.get(metric) for diff in diffs),
            after=_average(diff.after.get(metric) for diff in diffs),
            delta=None,
            ci_low=None,
            ci_high=None,
        )
        deltas = [d for d in (diff.delta(metric) for diff in diffs) if d is not None]
        if deltas:
            summary.delta = mean(deltas)
            summary.ci_low, summary.ci_high = _bootstrap_ci(deltas, resamples, seed)

        for diff in diffs:
            status = diff.status(metric)
            if status == "improved":
                summary.improved += 1
            elif status == "regressed":
                summary.regressed += 1
            elif status == "unchanged":
                summary.unchanged += 1
            else:
                summary.incomparable += 1
        summaries.append(summary)

    primary = metrics[0] if metrics else None
    regressions = [
        diff
        for diff in diffs
        if primary and diff.status(primary) == "regressed"
    ]
    improvements = [
        diff
        for diff in diffs
        if primary and diff.status(primary) == "improved"
    ]
    regressions.sort(key=lambda diff: (diff.delta(primary) or 0, diff.case_key))
    improvements.sort(key=lambda diff: (diff.delta(primary) or 0, diff.case_key), reverse=True)

    return CompareResult(
        run_a_id=str(run_a.get("run_id", "a")),
        run_b_id=str(run_b.get("run_id", "b")),
        comparable=comparable,
        dataset_hash_a=hash_a,
        dataset_hash_b=hash_b,
        metrics=summaries,
        regressions=regressions,
        improvements=improvements,
        only_in_a=sorted(cases_a.keys() - cases_b.keys()),
        only_in_b=sorted(cases_b.keys() - cases_a.keys()),
    )


def _average(values) -> float | None:
    numbers = [value for value in values if value is not None]
    return mean(numbers) if numbers else None


def _bootstrap_ci(
    deltas: list[float],
    resamples: int,
    seed: int,
) -> tuple[float, float]:
    """Percentile bootstrap (95%) over the per-case deltas.

    With a single case there is no noise to estimate, so the interval collapses
    to the delta itself — which is the honest answer for n = 1.
    """
    if len(deltas) == 1:
        return deltas[0], deltas[0]

    rng = random.Random(seed)
    size = len(deltas)
    means = []
    for _ in range(resamples):
        sample = [deltas[rng.randrange(size)] for _ in range(size)]
        means.append(mean(sample))
    means.sort()

    low_index = int(0.025 * resamples)
    high_index = min(int(0.975 * resamples), resamples - 1)
    return means[low_index], means[high_index]


def render(result: CompareResult, console: Console | None = None) -> None:
    """Print the comparison the way a reviewer reads it: verdict first, then cases."""
    console = console or Console()
    console.print(f"[bold]{result.run_a_id}[/bold]  ->  [bold]{result.run_b_id}[/bold]")

    if not result.comparable:
        console.print(
            "[bold yellow]warning[/bold yellow] the two runs used different dataset "
            "versions; treat the deltas as indicative only"
        )

    table = Table(show_header=True, header_style="bold")
    for column in ("metric", "before", "after", "delta", "95% CI", "verdict"):
        numeric = column not in {"metric", "verdict"}
        table.add_column(column, justify="right" if numeric else "left")

    for summary in result.metrics:
        table.add_row(
            summary.metric,
            _fmt(summary.before),
            _fmt(summary.after),
            _fmt_delta(summary.delta),
            _fmt_ci(summary.ci_low, summary.ci_high),
            summary.verdict,
        )
    console.print(table)

    if result.regressions:
        console.print(f"[bold red]{len(result.regressions)} case(s) regressed[/bold red]")
        for diff in result.regressions[:10]:
            primary = result.metrics[0].metric if result.metrics else "score"
            console.print(f"  - [cyan]{diff.case_key}[/cyan] {diff.input}")
            console.print(f"    expected: {diff.expected}")
            console.print(f"    before:   {diff.before_output}")
            console.print(f"    after:    {diff.after_output}")
            console.print(f"    delta:    {_fmt_delta(diff.delta(primary))}")

    if result.improvements:
        console.print(f"[green]{len(result.improvements)} case(s) improved[/green]")

    if result.only_in_a or result.only_in_b:
        console.print(
            f"[dim]cases only in first run: {len(result.only_in_a)}; "
            f"only in second: {len(result.only_in_b)}[/dim]"
        )


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def _fmt_delta(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:+.3f}"


def _fmt_ci(low: float | None, high: float | None) -> str:
    if low is None or high is None:
        return "n/a"
    return f"[{low:+.3f}, {high:+.3f}]"
