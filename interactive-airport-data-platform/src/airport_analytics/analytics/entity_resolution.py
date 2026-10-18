"""Local code-first identity resolution; spelling candidates never become scope silently."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from collections.abc import Iterable
from difflib import get_close_matches
from pathlib import Path
from typing import Literal

from airport_analytics.models import ResolvedEntity

ALIAS_PATH = Path(__file__).resolve().parents[1] / "data" / "entity_aliases.json"
EntityKind = Literal["origin", "destination", "airline", "origin_region"]


def alias_version() -> str:
    return hashlib.sha256(ALIAS_PATH.read_bytes()).hexdigest()


def normalize_name(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


class EntityResolutionError(ValueError):
    def __init__(self, message: str, candidate_codes: Iterable[str] = ()) -> None:
        super().__init__(message)
        self.candidate_codes = tuple(sorted(set(candidate_codes)))


class EntityDirectory:
    def __init__(
        self,
        *,
        airports: Iterable[tuple[str, str | None]],
        airlines: Iterable[tuple[str, str | None]],
        observed_origins: set[str],
        observed_destinations: set[str],
        observed_airlines: set[str],
    ) -> None:
        self.airports = dict(airports)
        self.airlines = dict(airlines)
        self.observed = {
            "origin": frozenset(observed_origins),
            "destination": frozenset(observed_destinations),
            "airline": frozenset(observed_airlines),
        }
        self.version = alias_version()
        self.aliases = json.loads(ALIAS_PATH.read_text(encoding="utf-8"))
        if not isinstance(self.aliases.get("version"), str):
            raise ValueError("Entity alias data requires an explicit version.")

    def resolve(self, kind: EntityKind, text: str) -> list[ResolvedEntity]:
        normalized = normalize_name(text)
        if not normalized:
            raise EntityResolutionError("Enter an entity name or code.")
        if kind == "origin_region":
            codes = self.aliases["origin_regions"].get(normalized)
            if codes is None:
                raise EntityResolutionError("Unknown origin region; select explicit origin codes.")
            available = self.airports.keys() | self.observed["origin"]
            if not set(codes).issubset(available):
                raise EntityResolutionError(
                    "This region cannot be resolved in the pinned reference; "
                    "select origins explicitly."
                )
            return [self._entity("origin", code, "alias") for code in sorted(codes)]
        references = self.airlines if kind == "airline" else self.airports
        known_codes = references.keys() | self.observed[kind]
        code = text.strip().upper()
        if code in known_codes:
            return [self._entity(kind, code, "code")]
        matches = sorted(
            key
            for key, name in references.items()
            if name is not None and normalize_name(name) == normalized
        )
        method: Literal["name", "alias"] = "name"
        if not matches:
            aliases = self.aliases["airlines" if kind == "airline" else "airports"]
            matches = sorted(code for code in aliases.get(normalized, []) if code in known_codes)
            method = "alias"
        if len(matches) == 1:
            return [self._entity(kind, matches[0], method)]
        if matches:
            raise EntityResolutionError("The name identifies multiple codes. Select one.", matches)
        names = {normalize_name(name): key for key, name in sorted(references.items()) if name}
        suggestions = get_close_matches(normalized, sorted(names), n=5, cutoff=0.75)
        raise EntityResolutionError(
            "The entity is not resolved. Confirm a code or a spelling candidate.",
            [names[name] for name in suggestions],
        )

    def _entity(
        self,
        kind: Literal["origin", "destination", "airline"],
        code: str,
        method: Literal["code", "name", "alias", "confirmed_spelling"],
    ) -> ResolvedEntity:
        references = self.airlines if kind == "airline" else self.airports
        observed = code in self.observed[kind]
        return ResolvedEntity(
            kind=kind,
            code=code,
            name=references.get(code),
            status=("observed" if code in references else "unmatched_reference")
            if observed
            else "reference_only",
            method=method,
            alias_version=self.version,
        )
