from __future__ import annotations

import json

import pytest

from yardstick.datasets import DatasetError, load_dataset


def _write(tmp_path, rows: list[dict]) -> str:
    path = tmp_path / "data.jsonl"
    payload = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    path.write_text(payload, encoding="utf-8")
    return str(path)


def test_loads_jsonl_and_reports_summary(tmp_path) -> None:
    path = _write(
        tmp_path,
        [
            {"case_key": "a", "input": "q1", "expected": "e1"},
            {"case_key": "b", "input": "q2", "expected": "e2", "relevant_ids": ["d1", "d2"]},
        ],
    )
    dataset = load_dataset(path)

    assert len(dataset) == 2
    assert dataset.cases[1].relevant_ids == ("d1", "d2")
    assert dataset.summary()["case_count"] == 2


def test_hash_is_stable_and_content_addressed(tmp_path) -> None:
    rows = [{"case_key": "a", "input": "q1", "expected": "e1"}]
    first = load_dataset(_write(tmp_path, rows))

    other = tmp_path / "copy.jsonl"
    other.write_text(open(_write(tmp_path, rows), encoding="utf-8").read(), encoding="utf-8")
    second = load_dataset(other)

    assert first.content_hash == second.content_hash

    rows[0]["expected"] = "e2"
    changed = load_dataset(_write(tmp_path, rows))
    assert changed.content_hash != first.content_hash


def test_duplicate_case_key_is_rejected(tmp_path) -> None:
    path = _write(tmp_path, [{"case_key": "a", "input": "q1"}, {"case_key": "a", "input": "q2"}])
    with pytest.raises(DatasetError, match="duplicate case_key"):
        load_dataset(path)


def test_empty_input_is_rejected(tmp_path) -> None:
    path = _write(tmp_path, [{"case_key": "a", "input": "   "}])
    with pytest.raises(DatasetError, match="empty input"):
        load_dataset(path)


def test_missing_case_key_is_rejected(tmp_path) -> None:
    path = _write(tmp_path, [{"input": "q1"}])
    with pytest.raises(DatasetError, match="missing case_key"):
        load_dataset(path)


def test_csv_is_supported(tmp_path) -> None:
    path = tmp_path / "data.csv"
    path.write_text("case_key,input,expected,relevant_ids\na,q1,e1,d1;d2\n", encoding="utf-8")

    dataset = load_dataset(path)
    assert dataset.cases[0].relevant_ids == ("d1", "d2")


def test_unsupported_extension_raises(tmp_path) -> None:
    path = tmp_path / "data.txt"
    path.write_text("nope", encoding="utf-8")
    with pytest.raises(DatasetError, match="unsupported dataset format"):
        load_dataset(path)
