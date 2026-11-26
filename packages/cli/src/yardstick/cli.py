"""Command line entry point.

Exit codes: 0 pass, 1 gate failure, 2 configuration or runtime error.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from rich.console import Console

from . import __version__
from .compare import CompareError, compare_runs, load_run
from .compare import render as render_comparison
from .config import ConfigError, load_config
from .datasets import DatasetError, load_dataset
from .judge import Judge
from .metrics import METRICS, UnknownMetricError
from .report import render, write_report
from .runner import Runner
from .targets import build_target


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="yardstick",
        description="Evaluate an LLM application and gate on the result.",
    )
    parser.add_argument("--version", action="version", version=f"yardstick {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="evaluate a target against a dataset")
    run.add_argument("--config", required=True, type=Path, help="path to eval.yml")
    run.add_argument("--limit", type=int, default=None, help="evaluate only the first N cases")
    run.add_argument("--out", type=Path, default=Path("runs"), help="output directory")

    compare = subparsers.add_parser("compare", help="compare two runs case by case")
    compare.add_argument("run_a", help="baseline run id or directory")
    compare.add_argument("run_b", help="candidate run id or directory")
    compare.add_argument("--runs-dir", type=Path, default=Path("runs"), help="where run ids live")
    compare.add_argument(
        "--fail-on-regression",
        action="store_true",
        help="exit 1 when a metric dropped significantly",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "run":
        return run_command(args)
    if args.command == "compare":
        return compare_command(args)
    return 2  # pragma: no cover - argparse rejects unknown commands


def run_command(args: argparse.Namespace) -> int:
    console = Console()

    try:
        config = load_config(args.config)
        allowed_metrics = set(METRICS) | {"judge"}
        unknown = [metric for metric in config.metrics if metric not in allowed_metrics]
        if unknown:
            raise UnknownMetricError(f"unknown metric(s): {', '.join(unknown)}")
        if "judge" in config.metrics and config.judge is None:
            raise ConfigError("metrics includes 'judge' but there is no judge section")
        dataset = load_dataset(config.dataset)
        if args.limit is not None:
            dataset.cases = dataset.cases[: args.limit]
        target = build_target(config.target)
        judge = Judge(config.judge) if config.judge is not None else None
    except (ConfigError, DatasetError, UnknownMetricError) as exc:
        console.print(f"[bold red]error[/bold red] {exc}")
        return 2

    report = asyncio.run(Runner(config, dataset, target, judge).run())
    path = write_report(report, args.out)
    render(report, console)
    console.print(f"[dim]report: {path}[/dim]")

    return 1 if report.gate_failures() else 0


def compare_command(args: argparse.Namespace) -> int:
    console = Console()
    try:
        run_a = load_run(args.run_a, args.runs_dir)
        run_b = load_run(args.run_b, args.runs_dir)
    except CompareError as exc:
        console.print(f"[bold red]error[/bold red] {exc}")
        return 2

    result = compare_runs(run_a, run_b)
    render_comparison(result, console)

    if args.fail_on_regression and result.has_significant_regression:
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
