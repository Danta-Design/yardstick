"""Configuration model and loader.

The config file is the contract between a project and its evaluation. Everything
that affects a score must live here, because the whole config is snapshotted into
every run report — a run you cannot reconstruct is a run you cannot trust.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, model_validator


class ConfigError(ValueError):
    """Raised when a config file is missing, unreadable, or invalid."""


class TargetConfig(BaseModel):
    """How to reach the system under test."""

    model_config = {"extra": "forbid"}

    type: Literal["http", "python"]
    url: str | None = None
    callable: str | None = None

    # HTTP only: JSON body template. "{input}" is replaced with the case input.
    body: dict[str, Any] = Field(default_factory=lambda: {"input": "{input}"})
    headers: dict[str, str] = Field(default_factory=dict)
    headers_env: dict[str, str] = Field(
        default_factory=dict,
        description="Header name -> environment variable holding the value.",
    )
    output_path: str = Field(
        default="output",
        description="Dotted path into the JSON response, e.g. choices.0.message.content",
    )
    timeout_s: float = Field(default=60.0, gt=0)

    @model_validator(mode="after")
    def _require_transport(self) -> TargetConfig:
        if self.type == "http" and not self.url:
            raise ValueError("target.url is required when target.type is http")
        if self.type == "python" and not self.callable:
            raise ValueError("target.callable is required when target.type is python")
        return self


class GateConfig(BaseModel):
    """Thresholds that turn a report into a pass/fail signal."""

    model_config = {"extra": "forbid"}

    min_score: float | None = Field(default=None, ge=0, le=1)
    max_error_rate: float | None = Field(default=None, ge=0, le=1)


class Config(BaseModel):
    """A complete evaluation definition."""

    model_config = {"extra": "forbid"}

    name: str = "default"
    dataset: Path
    target: TargetConfig
    metrics: list[str] = Field(default_factory=lambda: ["exact_match"])
    gate: GateConfig = Field(default_factory=GateConfig)
    concurrency: int = Field(default=8, ge=1, le=64)
    retries: int = Field(default=2, ge=0, le=10)


def load_config(path: str | Path) -> Config:
    """Read and validate a YAML config, resolving paths relative to the file."""
    config_path = Path(path).expanduser()
    if not config_path.is_file():
        raise ConfigError(f"config not found: {config_path}")

    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:  # pragma: no cover - passthrough of parser detail
        raise ConfigError(f"invalid YAML in {config_path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError(f"expected a mapping at the top level of {config_path}")

    try:
        config = Config.model_validate(raw)
    except Exception as exc:  # pydantic.ValidationError
        raise ConfigError(f"invalid config {config_path}: {exc}") from exc

    if not config.dataset.is_absolute():
        config.dataset = (config_path.parent / config.dataset).resolve()

    return config
