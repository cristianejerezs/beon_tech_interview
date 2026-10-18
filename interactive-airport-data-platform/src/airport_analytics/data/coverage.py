"""Local, evidence-backed snapshot coverage; absent evidence never verifies a day."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


@dataclass(frozen=True)
class CoverageDeclaration:
    days: dict[str, frozenset[date]]
    warning: str | None = None


def _dates(interval):
    start, end = date.fromisoformat(interval["start"]), date.fromisoformat(interval["end"])
    if start > end:
        raise ValueError("Reversed coverage interval.")
    if (end - start).days > 36600:
        raise ValueError("Coverage interval exceeds supported historical range.")
    return {start + timedelta(days=index) for index in range((end - start).days + 1)}


def load_coverage(path: Path | None, snapshot_id: str, origins: set[str]) -> CoverageDeclaration:
    if path is None:
        return CoverageDeclaration({}, "No source-completeness declaration is configured.")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        schema_path = (
            Path(__file__).resolve().parents[3]
            / "specs"
            / ("002-natural-language-exploration")
            / "contracts"
            / "coverage.schema.json"
        )
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        errors = list(
            Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(payload)
        )
        if errors or payload["snapshot_id"] != snapshot_id:
            raise ValueError("Coverage schema or snapshot does not match.")
        if not payload["validation"]["checks"] or any(
            not check["passed"] for check in payload["validation"]["checks"]
        ):
            raise ValueError("Coverage checks are not passed.")
        # References are local reviewed evidence, never URLs to retrieve.
        references = {}
        for document in payload["documentation"]:
            reference = document["reference"]
            if "://" in reference:
                raise ValueError("Coverage evidence must be verifiable local files.")
            local = (path.parent / reference).resolve()
            if hashlib.sha256(local.read_bytes()).hexdigest() != document["sha256"]:
                raise ValueError("Coverage evidence hash differs.")
            references[reference] = local
        if any(
            check["evidence_reference"] not in references
            for check in payload["validation"]["checks"]
        ):
            raise ValueError("Coverage check evidence must reference a verified document.")
        days = {}
        for origin in payload["origins"]:
            code = origin["code"]
            if code not in origins or code in days:
                raise ValueError("Unknown or duplicate coverage origin.")
            covered = set()
            for interval in origin["covered_intervals"]:
                span = _dates(interval)
                if covered & span:
                    raise ValueError("Overlapping coverage intervals.")
                covered |= span
            gaps = set()
            for interval in origin["gaps"]:
                span = _dates(interval)
                if not span.issubset(covered) or gaps & span:
                    raise ValueError("Coverage gaps conflict or lie outside intervals.")
                gaps |= span
            days[code] = frozenset(covered - gaps)
        return CoverageDeclaration(days)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, KeyError, TypeError):
        return CoverageDeclaration(
            {},
            "Coverage declaration could not be verified; complete-day eligibility is unknown.",
        )


def calendar_eligibility(
    declaration: CoverageDeclaration,
    origins: list[str],
    start: date,
    end: date,
    observed_dates: set[date],
    denominator_basis: str,
):
    requested = _dates({"start": start.isoformat(), "end": end.isoformat()})
    verified = (
        set.intersection(*(set(declaration.days.get(origin, ())) for origin in origins)) & requested
        if origins
        else set()
    )
    observed = observed_dates & requested
    eligible = observed if denominator_basis == "observed_operating_days" else verified
    return dict(
        requested_days=len(requested),
        verified_days=len(verified),
        unknown_days=len(requested - verified),
        observed_days=len(observed),
        eligible_days=len(eligible),
        dates=sorted(eligible),
        per_weekday={
            str(day): sum(value.isoweekday() == day for value in eligible) for day in range(1, 8)
        },
    )
