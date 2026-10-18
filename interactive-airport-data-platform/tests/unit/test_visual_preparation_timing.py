import json
import logging

import pytest

from airport_analytics.errors import VisualEvidenceError
from airport_analytics.observability.timing import (
    capture_stage_timings,
    capture_visual_preparation,
)


def test_visual_preparation_timing_records_only_bounded_metadata(monkeypatch, caplog):
    import airport_analytics.observability.timing as timing

    clock = iter([10.0, 11.25])
    monkeypatch.setattr(timing, "perf_counter", lambda: next(clock))
    monkeypatch.setattr(timing.platform, "system", lambda: "TestOS")
    monkeypatch.setattr(timing.platform, "python_version", lambda: "3.12.0")

    with caplog.at_level(logging.INFO, logger="airport_analytics.observability.timing"):
        with capture_stage_timings() as timings:
            with capture_visual_preparation() as record:
                record.set_evidence("time_series", 4096)

    assert timings == {"visual_preparation": 1.25}
    event = next(item for item in caplog.records if item.getMessage() == "visual_preparation")
    assert event.duration_ms == 1250.0
    assert event.environment == {"platform": "TestOS", "python": "3.12.0"}
    assert event.family == "time_series"
    assert event.evidence_size_bytes == 4096
    assert event.failure_category is None
    assert "report" not in json.dumps(event.__dict__, default=str).lower()


def test_visual_preparation_timing_rethrows_without_logging_exception_content(
    monkeypatch,
    caplog,
):
    import airport_analytics.observability.timing as timing

    clock = iter([20.0, 21.0])
    monkeypatch.setattr(timing, "perf_counter", lambda: next(clock))
    with caplog.at_level(logging.INFO, logger="airport_analytics.observability.timing"):
        with pytest.raises(VisualEvidenceError, match="private report wording"):
            with capture_visual_preparation() as record:
                record.set_evidence("category", 512)
                raise VisualEvidenceError("private report wording")

    event = next(item for item in caplog.records if item.getMessage() == "visual_preparation")
    assert event.failure_category == "invalid_evidence"
    assert event.evidence_size_bytes == 512
    assert "private report wording" not in event.getMessage()
    assert "private report wording" not in json.dumps(event.__dict__, default=str)
