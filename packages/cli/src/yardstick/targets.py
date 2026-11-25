"""Adapters that reach the system under test.

A target is anything that maps a case input to a string. Everything provider
specific is translated here so the rest of the tool never learns which API it is
talking to.
"""

from __future__ import annotations

import importlib
import inspect
import os
from typing import Any, Protocol

import httpx

from .config import ConfigError, TargetConfig
from .datasets import Case


class TargetError(RuntimeError):
    """A target could not produce an answer. Retryable at the runner level."""


class Target(Protocol):
    async def call(self, case: Case) -> str: ...

    async def aclose(self) -> None: ...


def _extract(payload: Any, path: str) -> Any:
    current = payload
    for part in path.split("."):
        if isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError) as exc:
                raise TargetError(f"output_path {path!r} does not match the response") from exc
        elif isinstance(current, dict):
            if part not in current:
                raise TargetError(f"output_path {path!r} does not match the response")
            current = current[part]
        else:
            raise TargetError(f"output_path {path!r} hit a non-container value")
    return current


def _substitute(template: Any, value: str) -> Any:
    if isinstance(template, str):
        return template.replace("{input}", value)
    if isinstance(template, list):
        return [_substitute(item, value) for item in template]
    if isinstance(template, dict):
        return {key: _substitute(item, value) for key, item in template.items()}
    return template


class HttpTarget:
    """POST a JSON body to an endpoint and pull the answer out of the response."""

    def __init__(self, config: TargetConfig) -> None:
        assert config.url is not None  # guaranteed by TargetConfig
        self._config = config
        headers = dict(config.headers)
        for name, env_var in config.headers_env.items():
            value = os.environ.get(env_var)
            if value is None:
                raise ConfigError(f"environment variable {env_var!r} is not set")
            headers[name] = value
        self._client = httpx.AsyncClient(timeout=config.timeout_s, headers=headers)

    async def call(self, case: Case) -> str:
        body = _substitute(self._config.body, case.input)
        try:
            response = await self._client.post(self._config.url, json=body)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise TargetError(f"http request failed: {exc}") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise TargetError("response was not valid JSON") from exc

        value = _extract(payload, self._config.output_path)
        return value if isinstance(value, str) else str(value)

    async def aclose(self) -> None:
        await self._client.aclose()


class PythonTarget:
    """Call ``module:function`` in-process. Useful for local experiments and tests."""

    def __init__(self, config: TargetConfig) -> None:
        assert config.callable is not None  # guaranteed by TargetConfig
        module_name, _, attribute = config.callable.partition(":")
        if not attribute:
            raise ConfigError(
                f"target.callable must look like 'module:function', got {config.callable!r}"
            )
        try:
            module = importlib.import_module(module_name)
        except ImportError as exc:
            raise ConfigError(f"cannot import {module_name!r}: {exc}") from exc
        try:
            self._function = getattr(module, attribute)
        except AttributeError as exc:
            raise ConfigError(f"{module_name!r} has no attribute {attribute!r}") from exc
        if not callable(self._function):
            raise ConfigError(f"{config.callable!r} is not callable")

    async def call(self, case: Case) -> str:
        try:
            result = self._function(case.input)
            if inspect.isawaitable(result):
                result = await result
        except Exception as exc:  # noqa: BLE001 - surfaced as a target error
            raise TargetError(f"python target raised: {exc}") from exc
        return result if isinstance(result, str) else str(result)

    async def aclose(self) -> None:
        return None


def build_target(config: TargetConfig) -> Target:
    if config.type == "http":
        return HttpTarget(config)
    if config.type == "python":
        return PythonTarget(config)
    raise ConfigError(f"unsupported target type {config.type!r}")
