"""Snapshot-specific local evidence for transformed weather measurement units."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def weather_unit_provenance(path: Path | None, weather_sha256: str) -> dict[str, str]:
    if path is None:
        return {"flight_distance": "unverified", "weather": "unverified"}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        expected = {"temp": "F", "wind_speed": "mph", "precip": "inches", "visib": "miles"}
        if (
            set(payload)
            != {
                "schema_version",
                "weather_sha256",
                "units",
                "reviewed_by",
                "evidence_reference",
                "evidence_sha256",
            }
            or payload["schema_version"] != 1
            or payload["weather_sha256"] != weather_sha256
            or payload["units"] != expected
            or not isinstance(payload["reviewed_by"], str)
            or not payload["reviewed_by"].strip()
            or "://" in payload["evidence_reference"]
        ):
            raise ValueError("Weather unit declaration is invalid or stale.")
        evidence = (path.parent / payload["evidence_reference"]).resolve()
        if hashlib.sha256(evidence.read_bytes()).hexdigest() != payload["evidence_sha256"]:
            raise ValueError("Weather unit evidence hash is stale.")
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, KeyError, TypeError):
        return {
            "flight_distance": "unverified",
            "weather": "unverified",
            "weather_warning": (
                "Configured weather units could not be verified; Pearson correlations are "
                "provisional and unit-dependent precipitation comparisons are unavailable."
            ),
        }
    return {
        "flight_distance": "unverified",
        "weather": (
            f"weather_units:v1;sha256={weather_sha256};"
            "temp=F;wind_speed=mph;precip=inches;visib=miles"
        ),
        "weather_evidence": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
