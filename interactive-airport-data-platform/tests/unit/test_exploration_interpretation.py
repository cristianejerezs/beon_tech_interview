from pathlib import Path

import pytest

from airport_analytics.analytics.entity_resolution import EntityDirectory, EntityResolutionError
from airport_analytics.analytics.interpretation import resolve_proposal
from airport_analytics.models import IntentProposalV2, RequestDraft, TimeRange
from tests.exploration_oracles import read_rows
from tests.unit.test_exploration_contracts import proposed_section

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "exploration"


def directory():
    flights = read_rows(FIXTURES / "nyc_flights_fixed.csv")
    return EntityDirectory(
        airports=[(row["faa"], row["name"]) for row in read_rows(FIXTURES / "nyc_airports.csv")],
        airlines=[
            (row["carrier"], row["name"]) for row in read_rows(FIXTURES / "nyc_airlines.csv")
        ],
        observed_origins={row["origin"] for row in flights},
        observed_destinations={row["dest"] for row in flights},
        observed_airlines={row["carrier"] for row in flights},
    )


def proposal(**changes):
    return IntentProposalV2.model_validate(
        {
            "intent_version": 2,
            "status": "proposed",
            "shared_scope": {},
            "sections": [proposed_section(**changes)],
            "selection_reason": None,
        }
    )


def resolve(question="How many flights?", *, previous=None, **changes):
    return resolve_proposal(
        RequestDraft(original_question=question, revision=2 if previous else 1),
        proposal(**changes),
        directory(),
        snapshot_id="a" * 64,
        context_id="b" * 64,
        previous=previous,
    )[0]


@pytest.mark.parametrize(
    "wording",
    [
        "How many flights were recorded?",
        "Give the total flight count.",
        "What's the number of departures in this dataset?",
    ],
)
def test_paraphrases_share_local_defaults_without_phrase_routing(wording):
    interpretation = resolve(wording)
    assert interpretation.measure_ids == ["flight_count"]
    assert interpretation.filters == []
    assert interpretation.date_scope is None
    assert interpretation.definition.unit == "flights"
    assert interpretation.field_provenance["filters"].source == "default"
    assert interpretation.original_clause == "How many flights?"


def test_entity_codes_names_aliases_and_unmatched_references():
    entities = directory()
    assert entities.resolve("origin", "jfk")[0].code == "JFK"
    assert entities.resolve("origin", " synthetic   kennedy ")[0].method == "name"
    assert entities.resolve("origin", "Kennedy")[0].method == "alias"
    assert entities.resolve("destination", "XXX")[0].status == "unmatched_reference"
    assert entities.resolve("destination", "ZZZ")[0].status == "reference_only"
    assert entities.resolve("airline", "synthetic alpha")[0].code == "AA"
    with pytest.raises(EntityResolutionError):
        entities.resolve("origin", "New York")
    with pytest.raises(EntityResolutionError):
        entities.resolve("origin", "JF")
    with pytest.raises(EntityResolutionError):
        entities.resolve("destination", "NOT_REAL")


def test_spelling_suggestions_never_authorize_even_single_candidate():
    with pytest.raises(EntityResolutionError) as caught:
        directory().resolve("origin", "Synthetic Kenned")
    assert "JFK" in caught.value.candidate_codes


def test_duplicate_normalized_names_require_selection_and_codes_take_precedence():
    entities = EntityDirectory(
        airports=[("ONE", "Same name"), ("TWO", "Same name"), ("JFK", "ONE")],
        airlines=[],
        observed_origins={"ONE", "TWO", "JFK"},
        observed_destinations=set(),
        observed_airlines=set(),
    )
    assert entities.resolve("origin", "ONE")[0].code == "ONE"
    with pytest.raises(EntityResolutionError) as caught:
        entities.resolve("origin", "Same name")
    assert caught.value.candidate_codes == ("ONE", "TWO")


def test_grouped_distinct_and_name_scope_are_resolved_without_answers():
    result = resolve(
        measure_ids=["distinct_destination_count"],
        family="grouped_summary",
        grouping=["origin"],
        entity_mentions=[
            {
                "kind": "destination",
                "text": "Synthetic Boston",
                "code_candidate": None,
            }
        ],
    )
    assert result.grouping == ["origin"]
    assert result.filters[0].field_id == "destination"
    assert result.filters[0].value == "BOS"
    assert result.definition.additivity == "non_additive"
    assert result.grain == "category"
    assert resolve(measure_ids=["distinct_destination_count"]).grouping == []


def test_fresh_question_does_not_inherit_and_typed_follow_up_removes_only_named_scope():
    first = resolve(
        scope_edits=[
            {"field_id": "origin", "action": "add", "operator": "eq", "value": "JFK"},
            {"field_id": "carrier", "action": "add", "operator": "eq", "value": "AA"},
        ]
    )
    assert resolve().filters == []
    follow_up = resolve(
        previous=first,
        scope_edits=[
            {"field_id": "origin", "action": "remove", "operator": None, "value": None},
        ],
    )
    assert [(item.field_id, item.value) for item in follow_up.filters] == [("carrier", "AA")]
    assert follow_up.field_provenance["filters"].source == "explicit"
    inherited = resolve(previous=first)
    assert inherited.filters == first.filters
    assert inherited.field_provenance["filters"].source == "inherited"


@pytest.mark.parametrize(
    "changes",
    [
        {
            "scope_edits": [
                {"field_id": "origin", "action": "add", "operator": "eq", "value": "BAD"}
            ]
        },
        {"entity_mentions": [{"kind": "origin", "text": "BAD", "code_candidate": "JFK"}]},
        {
            "scope_edits": [
                {"field_id": "origin", "action": "add", "operator": "eq", "value": "JFK"},
                {"field_id": "origin", "action": "add", "operator": "eq", "value": "LGA"},
            ]
        },
    ],
)
def test_invalid_entities_candidates_and_contradictions_never_broaden_scope(changes):
    with pytest.raises(ValueError):
        resolve(**changes)


def test_unresolved_envelope_never_produces_interpretations():
    unresolved = IntentProposalV2.model_validate(
        {
            "intent_version": 2,
            "status": "needs_clarification",
            "shared_scope": {},
            "sections": [
                proposed_section(
                    status="needs_clarification",
                    clarification={
                        "field_id": "origin",
                        "question": "Which airport?",
                        "choices": [],
                    },
                )
            ],
            "selection_reason": None,
        }
    )
    with pytest.raises(ValueError, match="unresolved"):
        resolve_proposal(
            RequestDraft(original_question="At the airport"),
            unresolved,
            directory(),
            snapshot_id="a" * 64,
            context_id="b" * 64,
        )


def test_ranking_and_trend_defaults_and_catalog_rejection():
    ranked = resolve(family="ranking", grouping=["carrier"])
    assert ranked.selection == 10
    assert ranked.order[0].field_id == "flight_count"
    assert ranked.order[0].direction == "desc"
    trend = resolve(family="historical_trend")
    assert trend.grouping == ["flight_month"]
    assert trend.order[0].field_id == "flight_month"
    assert trend.order[0].direction == "asc"
    with pytest.raises(ValueError):
        resolve(
            family="grouped_summary",
            measure_ids=["distinct_destination_count"],
            grouping=["carrier"],
        )


def test_follow_up_keeps_compatible_trend_grain_and_records_actual_field_sources():
    first = resolve(family="historical_trend", grouping=["flight_date"])
    inherited = resolve(previous=first, family="historical_trend")
    assert inherited.grouping == ["flight_date"]
    assert inherited.field_provenance["grouping"].source == "inherited"
    overall = resolve(previous=first)
    assert overall.grouping == []
    assert overall.order == []
    assert overall.selection == 500
    assert overall.field_provenance["grouping"].source == "default"
    assert overall.field_provenance["selection"].source == "default"


def test_date_scope_cannot_contradict_inherited_explicit_date_filter():
    first = resolve(
        scope_edits=[
            {"field_id": "flight_date", "action": "add", "operator": "eq", "value": "2013-01-01"},
        ]
    )
    follow_up = proposal()
    follow_up.shared_scope.dates = TimeRange(start="2013-02-01", end="2013-02-28")
    with pytest.raises(ValueError, match="Contradictory"):
        resolve_proposal(
            RequestDraft(original_question="During February", revision=2),
            follow_up,
            directory(),
            snapshot_id=first.snapshot_id,
            context_id=first.context_id,
            previous=first,
        )
