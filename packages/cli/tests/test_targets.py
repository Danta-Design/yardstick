from __future__ import annotations

import pytest

from yardstick.targets import TargetError, _extract, _substitute


def test_substitute_replaces_nested_strings() -> None:
    body = {"messages": [{"role": "user", "content": "{input}"}], "n": 1}
    assert _substitute(body, "hello") == {
        "messages": [{"role": "user", "content": "hello"}],
        "n": 1,
    }


def test_extract_walks_dicts_and_lists() -> None:
    payload = {"choices": [{"message": {"content": "answer"}}]}
    assert _extract(payload, "choices.0.message.content") == "answer"


def test_extract_reports_a_readable_error() -> None:
    with pytest.raises(TargetError, match="output_path"):
        _extract({"choices": []}, "choices.0.message.content")
