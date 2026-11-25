from __future__ import annotations

import pytest

from yardstick.config import ConfigError, load_config


def _write(tmp_path, body: str) -> str:
    path = tmp_path / "eval.yml"
    path.write_text(body, encoding="utf-8")
    return str(path)


def test_loads_minimal_config_and_resolves_dataset(tmp_path) -> None:
    (tmp_path / "data.jsonl").write_text('{"case_key":"a","input":"q"}', encoding="utf-8")
    path = _write(
        tmp_path,
        """
dataset: data.jsonl
target:
  type: python
  callable: module:fn
""",
    )

    config = load_config(path)

    assert config.dataset == (tmp_path / "data.jsonl").resolve()
    assert config.metrics == ["exact_match"]
    assert config.concurrency == 8


def test_http_target_requires_url(tmp_path) -> None:
    path = _write(tmp_path, "dataset: d.jsonl\ntarget:\n  type: http\n")
    with pytest.raises(ConfigError, match="target.url"):
        load_config(path)


def test_python_target_requires_callable(tmp_path) -> None:
    path = _write(tmp_path, "dataset: d.jsonl\ntarget:\n  type: python\n")
    with pytest.raises(ConfigError, match="target.callable"):
        load_config(path)


def test_unknown_key_is_rejected(tmp_path) -> None:
    path = _write(
        tmp_path,
        "dataset: d.jsonl\nsurprise: 1\ntarget:\n  type: python\n  callable: a:b\n",
    )
    with pytest.raises(ConfigError, match="invalid config"):
        load_config(path)


def test_missing_file_raises(tmp_path) -> None:
    with pytest.raises(ConfigError, match="config not found"):
        load_config(tmp_path / "nope.yml")
