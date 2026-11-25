"""Shared test configuration.

The built-in ``tmp_path`` fixture is overridden because this project is developed
on Windows inside a confined shell: pytest's own temp root lives outside the
repository and cannot be listed or cleaned up there. A workspace-local directory
behaves identically from a test's point of view and works in CI too.
"""

from __future__ import annotations

import shutil
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest

_TMP_ROOT = Path(__file__).parent / "_tmp"


@pytest.fixture
def tmp_path() -> Iterator[Path]:
    path = _TMP_ROOT / uuid.uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
