"""Opt-in real-provider baseline, never a mocked performance claim."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.skipif(
    os.getenv("AIRPORT_RUN_LIVE_EVALUATION") != "true",
    reason="Live provider acceptance/latency requires explicit operator authorization.",
)
def test_real_provider_latency_baseline():
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "airport_analytics.analytics.evaluation",
            "--run-live",
            "--acknowledge-hosted-processing",
        ],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        timeout=1800,
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert len(result["cases"]) == 12
    assert result["passed"]
    assert all(case["seconds"] >= 0 for case in result["cases"])
    print(json.dumps(result, indent=2))
