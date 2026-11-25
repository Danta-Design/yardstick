"""Dataset loading, validation, and content hashing.

A dataset version is identified by the hash of its normalized content, not by a
filename or a timestamp. Two runs are comparable exactly when their hashes match;
anything else is a guess.
"""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class DatasetError(ValueError):
    """Raised when a dataset file is missing, malformed, or fails validation."""


@dataclass(frozen=True)
class Case:
    """One evaluation case."""

    case_key: str
    input: str
    expected: str | None = None
    relevant_ids: tuple[str, ...] = ()
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_key": self.case_key,
            "input": self.input,
            "expected": self.expected,
            "relevant_ids": list(self.relevant_ids),
            "meta": self.meta,
        }


@dataclass
class Dataset:
    """An immutable collection of cases plus its content hash."""

    path: Path
    cases: list[Case]
    content_hash: str

    def __len__(self) -> int:
        return len(self.cases)

    def summary(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "content_hash": self.content_hash,
            "case_count": len(self.cases),
        }


def load_dataset(path: str | Path) -> Dataset:
    """Load a JSONL or CSV dataset, validate it, and compute its content hash."""
    dataset_path = Path(path).expanduser()
    if not dataset_path.is_file():
        raise DatasetError(f"dataset not found: {dataset_path}")

    suffix = dataset_path.suffix.lower()
    if suffix == ".jsonl":
        cases = _load_jsonl(dataset_path)
    elif suffix == ".csv":
        cases = _load_csv(dataset_path)
    else:
        raise DatasetError(f"unsupported dataset format {suffix!r}; expected .jsonl or .csv")

    _validate(cases, dataset_path)
    return Dataset(
        path=dataset_path,
        cases=cases,
        content_hash=_content_hash(cases),
    )


def _load_jsonl(path: Path) -> list[Case]:
    cases: list[Case] = []
    with path.open(encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, start=1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise DatasetError(f"{path}:{lineno}: invalid JSON: {exc}") from exc
            if not isinstance(row, dict):
                raise DatasetError(f"{path}:{lineno}: expected a JSON object")
            cases.append(_row_to_case(row, f"{path}:{lineno}"))
    return cases


def _load_csv(path: Path) -> list[Case]:
    cases: list[Case] = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise DatasetError(f"{path}: empty CSV, missing header")
        for lineno, row in enumerate(reader, start=2):
            cases.append(_row_to_case(row, f"{path}:{lineno}"))
    return cases


def _row_to_case(row: dict[str, Any], where: str) -> Case:
    case_key = row.get("case_key")
    if case_key is None or str(case_key).strip() == "":
        raise DatasetError(f"{where}: missing case_key")

    text = row.get("input")
    if text is None:
        raise DatasetError(f"{where}: missing input")

    raw_relevant = row.get("relevant_ids") or ""
    if isinstance(raw_relevant, str):
        relevant = tuple(part.strip() for part in raw_relevant.split(";") if part.strip())
    else:
        relevant = tuple(str(part) for part in raw_relevant)

    known = {"case_key", "input", "expected", "relevant_ids"}
    meta = {
        key: value
        for key, value in row.items()
        if key not in known and value not in ("", None)
    }

    expected = row.get("expected")
    return Case(
        case_key=str(case_key),
        input=str(text),
        expected=None if expected in (None, "") else str(expected),
        relevant_ids=relevant,
        meta=meta,
    )


def _validate(cases: list[Case], path: Path) -> None:
    if not cases:
        raise DatasetError(f"{path}: dataset contains no cases")

    seen: set[str] = set()
    for case in cases:
        if not case.input.strip():
            raise DatasetError(f"{path}: case {case.case_key!r} has an empty input")
        if case.case_key in seen:
            raise DatasetError(f"{path}: duplicate case_key {case.case_key!r}")
        seen.add(case.case_key)


def _content_hash(cases: list[Case]) -> str:
    payload = json.dumps(
        [case.to_dict() for case in cases],
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
