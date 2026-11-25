"""Run reports: the artifact a human reads and a machine gates on."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

from .datasets import Case


@dataclass
class CaseResult:
    """One case, after it was sent to the target."""

    case: Case
    output: str | None
    error: str | None
    latency_ms: float
    scores: dict[str, float] = field(default_factory=dict)
    judge: dict[str, Any] | None = None
    judge_error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_key": self.case.case_key,
            "input": self.case.input,
            "expected": self.case.expected,
            "output": self.output,
            "error": self.error,
            "judge_error": self.judge_error,
            "latency_ms": round(self.latency_ms, 2),
            "scores": self.scores,
            "judge": self.judge,
        }


@dataclass
class RunReport:
    """Everything needed to reproduce and compare a run."""

    run_id: str
    started_at: str
    duration_s: float
    config_name: str
    dataset: dict[str, Any]
    target: dict[str, Any]
    metrics: dict[str, float | None]
    error_rate: float
    results: list[CaseResult]
    gate: dict[str, Any]
    judge: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "run_id": self.run_id,
            "started_at": self.started_at,
            "duration_s": round(self.duration_s, 2),
            "config_name": self.config_name,
            "dataset": self.dataset,
            "target": self.target,
            "metrics": self.metrics,
            "error_rate": round(self.error_rate, 4),
            "gate": self.gate,
            "judge": self.judge,
            "cases": [result.to_dict() for result in self.results],
        }

    def gate_failures(self) -> list[str]:
        """Return human-readable reasons the gate did not pass."""
        failures: list[str] = []

        minimum = self.gate.get("min_score")
        primary = self.gate.get("primary_metric")
        if minimum is not None and primary is not None:
            score = self.metrics.get(primary)
            if score is None:
                failures.append(f"{primary} had no scored cases")
            elif score < minimum:
                failures.append(f"{primary} {score:.3f} < min_score {minimum:.3f}")

        max_errors = self.gate.get("max_error_rate")
        if max_errors is not None and self.error_rate > max_errors:
            failures.append(f"error_rate {self.error_rate:.1%} > max_error_rate {max_errors:.1%}")

        return failures


def write_report(report: RunReport, out_root: Path) -> Path:
    """Write the JSON report and return its path."""
    run_dir = out_root / report.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "report.json"
    path.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def render(report: RunReport, console: Console | None = None) -> None:
    """Print a compact summary plus the most useful failures."""
    console = console or Console()

    table = Table(title=f"run {report.run_id}", show_header=True, header_style="bold")
    table.add_column("metric")
    table.add_column("score", justify="right")
    table.add_column("cases", justify="right")

    scored = sum(1 for result in report.results if result.ok)
    for name, value in report.metrics.items():
        shown = "n/a" if value is None else f"{value:.3f}"
        table.add_row(name, shown, str(scored))

    table.add_row("error_rate", f"{report.error_rate:.1%}", str(len(report.results)))
    console.print(table)
    console.print(
        f"[dim]{len(report.results)} cases | {report.duration_s:.1f}s | "
        f"dataset {report.dataset['content_hash'][:12]}[/dim]"
    )
    if report.judge:
        judge = report.judge
        cached = f"{judge['cache_hits']}/{judge['judged_cases']}"
        console.print(
            f"[dim]judge {judge['model']} | rubric {judge['rubric_hash'][:12]} | "
            f"{judge['samples']} sample(s) | {cached} cached[/dim]"
        )
        if judge["needs_review"]:
            flagged = judge["needs_review"]
            console.print(
                f"[bold yellow]{flagged} case(s) flagged for human review[/bold yellow]"
            )

    failures = report.gate_failures()
    if failures:
        console.print("[bold red]gate failed[/bold red]")
        for reason in failures:
            console.print(f"  - {reason}")

    broken = [result for result in report.results if not result.ok]
    if broken:
        console.print(f"[bold yellow]{len(broken)} case(s) errored[/bold yellow]")
        for result in broken[:5]:
            console.print(f"  - {result.case.case_key}: {result.error}")

    wrong = [
        result
        for result in report.results
        if result.ok and any(score < 1.0 for score in result.scores.values())
    ]
    if wrong:
        console.print(f"[bold]{len(wrong)} case(s) below full score[/bold]")
        for result in wrong[:5]:
            console.print(f"  - [cyan]{result.case.case_key}[/cyan] {result.case.input}")
            console.print(f"    expected: {result.case.expected}")
            console.print(f"    actual:   {result.output}")
            if result.judge:
                console.print(
                    f"    judge:    {result.judge['raw_score']} — {result.judge['reason']}"
                )
