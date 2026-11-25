"""Fake targets used by the end-to-end tests. No network, no model calls."""


def shout(text: str) -> str:
    """Deterministic, easy to predict: uppercases the input."""
    return text.upper()


async def shout_async(text: str) -> str:
    """Same contract, but async, to prove both call styles are supported."""
    return text.upper()


def explode(text: str) -> str:
    """Always fails, to exercise the retry and error-rate paths."""
    raise RuntimeError("target is down")


def constant(text: str) -> str:
    """Ignores the input, always answers the same thing."""
    return "3 个"
