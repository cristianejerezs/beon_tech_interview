from airport_analytics.analytics.follow_up import merge_follow_up_plan
from airport_analytics.analytics.plan_schema import validate_analysis_plan


def plan(*, filters=None, date_range=None, group_by=None, metric="mean_departure_delay"):
    return validate_analysis_plan(
        {
            "status": "ready",
            "intent": "compare",
            "metric_id": metric,
            "group_by": group_by or ["carrier"],
            "filters": filters or [],
            "time_range": date_range,
            "sort": {"field_id": metric, "direction": "desc"},
            "row_limit": 20,
            "chart_intent": "bar",
            "clarification_question": None,
            "unsupported_reason": None,
        }
    )


def test_follow_up_adds_filters_and_preserves_unmodified_scope() -> None:
    previous = plan(
        filters=[{"field_id": "origin", "operator": "eq", "value": "EWR"}],
        date_range={"start": "2013-01-01", "end": "2013-06-30"},
    )
    followup = plan(
        filters=[{"field_id": "carrier", "operator": "eq", "value": "B6"}],
        group_by=["carrier"],
    )
    merged = merge_follow_up_plan(
        previous,
        followup,
        "Add B6 as the airline filter.",
    )
    assert {(item.field_id, item.value) for item in merged.filters} == {
        ("origin", "EWR"),
        ("carrier", "B6"),
    }
    assert merged.time_range.start.isoformat() == "2013-01-01"
    assert merged.time_range.end.isoformat() == "2013-06-30"


def test_follow_up_replaces_contradictory_airport_airline_and_date_scope() -> None:
    previous = plan(
        filters=[
            {"field_id": "origin", "operator": "eq", "value": "EWR"},
            {"field_id": "carrier", "operator": "eq", "value": "UA"},
        ],
        date_range={"start": "2013-01-01", "end": "2013-03-31"},
    )
    followup = plan(
        filters=[
            {"field_id": "origin", "operator": "eq", "value": "JFK"},
            {"field_id": "carrier", "operator": "eq", "value": "DL"},
        ],
        date_range={"start": "2013-04-01", "end": "2013-06-30"},
    )
    merged = merge_follow_up_plan(
        previous,
        followup,
        "Instead use flights from JFK for Delta in April through June.",
    )
    values = {item.field_id: item.value for item in merged.filters}
    assert values == {"origin": "JFK", "carrier": "DL"}
    assert merged.time_range.start.isoformat() == "2013-04-01"
    assert merged.time_range.end.isoformat() == "2013-06-30"


def test_explicit_scope_removal_does_not_retain_old_constraints() -> None:
    previous = plan(
        filters=[
            {"field_id": "origin", "operator": "eq", "value": "EWR"},
            {"field_id": "carrier", "operator": "eq", "value": "UA"},
        ],
        date_range={"start": "2013-01-01", "end": "2013-03-31"},
    )
    followup = plan()
    merged = merge_follow_up_plan(
        previous,
        followup,
        "Remove the airport and airline filters and use the full period.",
    )
    assert merged.filters == []
    assert merged.time_range is None
