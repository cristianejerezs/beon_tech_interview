"""Opt-in context-local stage durations with no content or exception recording."""

import logging
import platform
from collections.abc import Callable, Generator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from functools import wraps
from time import perf_counter
from typing import Literal, ParamSpec, TypeVar

from airport_analytics.errors import (
    MissingVisualEvidenceError,
    PresentationPreferenceError,
    VisualEvidenceError,
    VisualRenderError,
)

Stage = Literal[
    "source_validation",
    "interpretation",
    "execution",
    "table_preparation",
    "server_preparation",
    "visual_preparation",
    "export_generation",
]
VisualFamily = Literal[
    "unknown",
    "listing",
    "scalar",
    "category",
    "ranking",
    "time",
    "time_series",
    "two_category",
    "period_change",
    "distribution",
    "relationship",
    "weather",
]
VisualFailureCategory = Literal[
    "missing_evidence",
    "invalid_preference",
    "invalid_evidence",
    "chart_render",
    "unexpected",
]
_VISUAL_FAMILIES: dict[str, VisualFamily] = {
    "listing": "listing",
    "scalar": "scalar",
    "category": "category",
    "ranking": "ranking",
    "time": "time",
    "time_series": "time_series",
    "two_category": "two_category",
    "period_change": "period_change",
    "distribution": "distribution",
    "relationship": "relationship",
    "weather": "weather",
}
P = ParamSpec("P")
R = TypeVar("R")
_current: ContextVar[dict[str, float] | None] = ContextVar("stage_durations", default=None)
_active: ContextVar[frozenset[Stage]] = ContextVar("active_stages", default=frozenset())
_LOGGER = logging.getLogger(__name__)


@dataclass
class VisualPreparationRecord:
    family: VisualFamily = "unknown"
    evidence_size_bytes: int = 0
    failure_category: VisualFailureCategory | None = None

    def set_evidence(self, family: str, evidence_size_bytes: int) -> None:
        known_family = _VISUAL_FAMILIES.get(family)
        if known_family is None or type(evidence_size_bytes) is not int or evidence_size_bytes < 0:
            raise ValueError("Visual timing metadata must be a known family and nonnegative size.")
        self.family = known_family
        self.evidence_size_bytes = evidence_size_bytes

    def set_failure(self, category: VisualFailureCategory) -> None:
        self.failure_category = category


@contextmanager
def capture_visual_preparation() -> Generator[VisualPreparationRecord, None, None]:
    """Record only safe visual-preparation metadata and optionally capture its duration."""
    record = VisualPreparationRecord()
    started = perf_counter()
    try:
        yield record
    except MissingVisualEvidenceError:
        record.failure_category = record.failure_category or "missing_evidence"
        raise
    except PresentationPreferenceError:
        record.failure_category = record.failure_category or "invalid_preference"
        raise
    except VisualRenderError:
        record.failure_category = record.failure_category or "chart_render"
        raise
    except VisualEvidenceError:
        record.failure_category = record.failure_category or "invalid_evidence"
        raise
    except Exception:
        record.failure_category = record.failure_category or "unexpected"
        raise
    finally:
        duration = perf_counter() - started
        timings = _current.get()
        if timings is not None:
            timings["visual_preparation"] = timings.get("visual_preparation", 0.0) + duration
        _LOGGER.info(
            "visual_preparation",
            extra={
                "duration_ms": duration * 1000,
                "environment": {
                    "platform": platform.system(),
                    "python": platform.python_version(),
                },
                "family": record.family,
                "evidence_size_bytes": record.evidence_size_bytes,
                "failure_category": record.failure_category,
            },
        )


@contextmanager
def capture_stage_timings() -> Generator[dict[str, float], None, None]:
    timings: dict[str, float] = {}
    parent = _current.get()
    token = _current.set(timings)
    try:
        yield timings
    finally:
        _current.reset(token)
        if parent is not None:
            for key, value in timings.items():
                parent[key] = parent.get(key, 0.0) + value


def timed_stage(stage: Stage) -> Callable[[Callable[P, R]], Callable[P, R]]:
    def decorate(function: Callable[P, R]) -> Callable[P, R]:
        @wraps(function)
        def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
            timings = _current.get()
            if timings is None or stage in _active.get():
                return function(*args, **kwargs)
            token = _active.set(_active.get() | {stage})
            started = perf_counter()
            try:
                return function(*args, **kwargs)
            finally:
                timings[stage] = timings.get(stage, 0.0) + perf_counter() - started
                _active.reset(token)

        return wrapped

    return decorate
