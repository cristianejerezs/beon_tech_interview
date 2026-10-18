"""Closed multi-stage analytics; complete populations stay inside DuckDB."""

from __future__ import annotations

import json
import math
from calendar import monthrange
from collections.abc import Callable
from datetime import date, timedelta

from airport_analytics.analytics.query_compiler import (
    _SUMMARY_SOURCE,
    CompiledQuery,
    _compile_filter,
)
from airport_analytics.errors import BinWidthRequiredError, InvalidPlanError, QueryTimeoutError
from airport_analytics.models import (
    DailyMeanResult,
    DistributionBin,
    DistributionResult,
    EvidenceField,
    EvidenceFormat,
    EvidenceScope,
    EvidenceSelection,
    NumericEvidence,
    PeriodChangeResult,
    PeriodEvidence,
)


def scoped_source(interpretation):
    clauses, parameters = [], []
    for predicate in interpretation.filters:
        clause, values = _compile_filter(predicate.field_id, predicate.operator, predicate.value)
        clauses.append(clause)
        parameters.extend(values)
    if interpretation.date_scope:
        for boundary, op in [
            (interpretation.date_scope.start, ">="),
            (interpretation.date_scope.end, "<="),
        ]:
            if boundary:
                clauses.append(f"make_date(f.year,f.month,f.day) {op} ?")
                parameters.append(boundary)
    return _SUMMARY_SOURCE + (" WHERE " + " AND ".join(clauses) if clauses else ""), parameters


def query(executor, interpretation, sql, parameters, columns, purpose="aggregate"):
    return executor._run_compiled_query(
        CompiledQuery(
            sql=sql,
            parameters=tuple(parameters),
            plan=interpretation,
            purpose=purpose,
            kind="owned_cte" if sql.startswith("WITH ") else "select",
            output_columns=tuple(columns),
        )
    )


def number(value, absence="no_known_values"):
    return NumericEvidence(value=value, absence=absence if value is None else None)


def common_evidence(executor, interpretation, report_id):
    source, parameters = scoped_source(interpretation)
    scope = query(
        executor,
        interpretation,
        (
            "SELECT count(*) AS n, min(make_date(f.year,f.month,f.day)) AS start, "
            "max(make_date(f.year,f.month,f.day)) AS finish, "
            "count(DISTINCT make_date(f.year,f.month,f.day)) AS days, "
            "list(DISTINCT f.origin ORDER BY f.origin) AS origins" + source
        ),
        parameters,
        ["n", "start", "finish", "days", "origins"],
    )[0]
    from airport_analytics.models import TimeRange

    return dict(
        result_version=2,
        evidence_version=2,
        report_id=report_id,
        section_id=interpretation.section_id,
        snapshot_id=interpretation.snapshot_id,
        context_id=interpretation.context_id,
        definition=interpretation.definition,
        grain=interpretation.grain,
        scope=EvidenceScope(
            filters=interpretation.filters,
            requested_period=interpretation.date_scope,
            observed_period=TimeRange(start=scope["start"], end=scope["finish"])
            if scope["start"]
            else None,
            origins=scope["origins"] or [],
            coverage_status="unknown",
            denominator_basis=interpretation.denominator_basis,
            requested_days=None,
            verified_days=0,
            unknown_days=None,
            observed_days=scope["days"],
            eligible_days=scope["days"]
            if interpretation.denominator_basis == "observed_operating_days"
            else 0
            if interpretation.denominator_basis != "not_applicable"
            else None,
        ),
        fields=[
            EvidenceField(
                field_id=measure,
                label=measure.replace("_", " "),
                role="numeric",
                unit=interpretation.definition.unit,
                unit_provenance="application_catalog",
            )
            for measure in interpretation.measure_ids
        ],
        order=interpretation.order,
        missingness={"filtered_flights": scope["n"]},
        selection=EvidenceSelection(available=1, selected=1, omitted=0, cutoff_tie=False),
        format=EvidenceFormat(
            locale="en", computed_places=2, rounding=interpretation.display_rounding
        ),
        limitations=["Historical observed data; source completeness is not inferred from rows."],
        daily_support=[],
        route_support=[],
    )


def distribution_constraints(executor, interpretation, *, timed_out: Callable[[], bool]):
    variable = interpretation.measure_ids[0]
    field = {
        "departure_delay": "f.dep_delay",
        "arrival_delay": "f.arr_delay",
        "distance": "f.distance",
    }[variable]
    source, parameters = scoped_source(interpretation)
    counts = query(
        executor,
        interpretation,
        f"SELECT count({field}) AS known, count(*)-count({field}) AS missing, "
        f"min({field}) AS minimum, max({field}) AS maximum" + source,
        parameters,
        ["known", "missing", "minimum", "maximum"],
        "eligibility",
    )[0]
    width = (
        interpretation.binning.width
        if interpretation.binning
        else (250.0 if variable == "distance" else 15.0)
    )
    if interpretation.binning and not interpretation.binning.accepted:
        raise InvalidPlanError("The distribution width must be explicitly accepted.")
    lower, total = None, 0
    if counts["known"]:
        scaled = [counts["minimum"] / width, counts["maximum"] / width]
        if any(not math.isfinite(value) or abs(value) > 2**53 for value in scaled):
            raise InvalidPlanError(
                "The distribution width exceeds exact bin-index precision. Choose a larger width."
            )
        lower = math.floor(scaled[0]) * width
        span = (counts["maximum"] - lower) / width
        if not math.isfinite(lower) or not math.isfinite(span):
            raise InvalidPlanError(
                "The distribution range needs finite boundaries. Narrow the scope."
            )
        total = math.floor(span) + 1
        if total > 100:
            # A 100-bin interval cannot span more than 100 widths; keep one rounding guard.
            multiple = max(1, math.floor((counts["maximum"] - counts["minimum"]) / width / 100) - 1)
            while True:
                if timed_out():
                    raise QueryTimeoutError()
                proposed = width * multiple
                anchor = math.floor(counts["minimum"] / proposed) * proposed
                if not math.isfinite(anchor) or not math.isfinite(proposed):
                    raise InvalidPlanError("A finite distribution width cannot cover this range.")
                if math.floor((counts["maximum"] - anchor) / proposed) + 1 <= 100:
                    break
                multiple += 1
            raise BinWidthRequiredError(float(proposed))
        if not math.isfinite(lower + total * width) or lower + total * width <= counts["maximum"]:
            raise InvalidPlanError(
                "The distribution needs representable finite bin edges. Choose another width."
            )
    return field, source, parameters, counts, width, lower, total


def distribution(executor, interpretation, common, *, timed_out: Callable[[], bool]):
    variable = interpretation.measure_ids[0]
    field, source, parameters, counts, width, lower, total = distribution_constraints(
        executor,
        interpretation,
        timed_out=timed_out,
    )
    bins = []
    if counts["known"]:
        grouped = query(
            executor,
            interpretation,
            f"SELECT CAST(floor(({field} - ?) / ?) AS BIGINT) AS bucket, count(*) AS n"
            + source
            + (" AND " if " WHERE " in source else " WHERE ")
            + f"{field} IS NOT NULL GROUP BY bucket ORDER BY bucket",
            [lower, width, *parameters],
            ["bucket", "n"],
            "distribution",
        )
        by_bucket = {row["bucket"]: row["n"] for row in grouped}
        bins = [
            DistributionBin(
                lower=lower + index * width,
                upper=lower + (index + 1) * width,
                count=by_bucket.get(index, 0),
                upper_inclusive=index == total - 1,
            )
            for index in range(total)
        ]
    common["selection"] = EvidenceSelection(
        available=len(bins),
        selected=len(bins),
        omitted=0,
        cutoff_tie=False,
    )
    return DistributionResult(
        **common,
        kind="distribution",
        variable=variable,
        width=float(width),
        bins=bins,
        known_count=counts["known"],
        missing_count=counts["missing"],
    )


def comparison_periods(comparison):
    current = comparison.comparison
    if current.start is None or current.end is None:
        raise ValueError("Choose inclusive start and end dates for the comparison period.")
    if comparison.baseline_rule == "explicit":
        if (
            comparison.baseline is None
            or comparison.baseline.start is None
            or comparison.baseline.end is None
        ):
            raise ValueError("Choose inclusive start and end dates for the baseline period.")
        return comparison.baseline, current, []
    from airport_analytics.models import TimeRange

    if comparison.baseline_rule == "previous_equal_days":
        days = (current.end - current.start).days + 1
        return (
            TimeRange(
                start=current.start - timedelta(days=days), end=current.start - timedelta(days=1)
            ),
            current,
            [],
        )
    unit = comparison.baseline_rule
    full_month = (
        current.start.day == 1
        and (current.start.year, current.start.month) == (current.end.year, current.end.month)
        and (current.end.day == monthrange(current.end.year, current.end.month)[1])
    )
    full_year = current.start.month == current.start.day == 1 and (
        current.end.year == current.start.year and current.end.month == 12 and current.end.day == 31
    )
    clamped = False

    def shift(value):
        nonlocal clamped
        year, month = value.year, value.month
        if unit == "previous_month":
            month -= 1
            if month == 0:
                year, month = year - 1, 12
        else:
            year -= 1
        day = min(value.day, monthrange(year, month)[1])
        clamped |= day != value.day
        return date(year, month, day)

    start, end = shift(current.start), shift(current.end)
    if unit == "previous_month" and full_month:
        end = end.replace(day=monthrange(end.year, end.month)[1])
        clamped = False
    if unit == "previous_year" and full_year:
        start, end = date(start.year, 1, 1), date(start.year, 12, 31)
        clamped = False
    warnings = ["Calendar shift clamped an invalid date to the last valid day."] if clamped else []
    return TimeRange(start=start, end=end), current, warnings


def period_change(executor, interpretation, common):
    from airport_analytics.analytics.metrics import build_summary_evidence

    if interpretation.comparison is None:
        raise InvalidPlanError("Choose explicit baseline and comparison date ranges.")
    baseline_period, comparison_period, warnings = comparison_periods(interpretation.comparison)
    values = []
    for period in [baseline_period, comparison_period]:
        if period.start is None or period.end is None:
            raise InvalidPlanError("Period comparison requires inclusive start and end dates.")
        resolved = interpretation.model_copy(
            update={
                "operation_id": "aggregate",
                "family": "overall_summary",
                "grouping": [],
                "date_scope": period,
                "order": [],
                "comparison": None,
                "grain": "scalar",
            }
        )
        result = executor.execute_summary(resolved)
        evidence = build_summary_evidence(resolved, result, report_id=common["report_id"])
        values.append(
            PeriodEvidence(
                period=period,
                value=evidence.value,
                observation_count=result.scope["known_measure"],
                day_exposure=(period.end - period.start).days + 1,
            )
        )
    baseline, comparison = values
    a, b = baseline.value.value, comparison.value.value
    absolute = None if a is None or b is None else b - a
    relative = None if a is None or b is None or a == 0 else 100 * (b - a) / a
    if a == 0:
        warnings.append("Percentage change unavailable: baseline is zero.")
    if a is not None and a < 0:
        warnings.append(
            "Negative baseline: percentage direction does not indicate improvement or worsening."
        )
    if baseline.day_exposure != comparison.day_exposure:
        warnings.append("Unequal calendar exposure; counts are not normalized to a per-day rate.")
    return PeriodChangeResult(
        **common,
        kind="period_change",
        baseline=baseline,
        comparison=comparison,
        absolute_change=number(absolute),
        relative_change=number(relative),
        warnings=warnings,
    )


def daily_mean(executor, interpretation, common):
    """No unverified day is silently included in a calendar denominator."""
    from airport_analytics.models import CategoryIdentity, DailyMeanEvidence

    source, parameters = scoped_source(interpretation)
    selected_origins = set(executor.entity_directory().observed["origin"])
    for predicate in interpretation.filters:
        if predicate.field_id != "origin":
            continue
        if predicate.operator == "eq":
            selected_origins.intersection_update({predicate.value})
        elif predicate.operator == "neq":
            selected_origins.discard(predicate.value)
        elif predicate.operator == "in":
            selected_origins.intersection_update(predicate.value)
    common["scope"] = common["scope"].model_copy(update={"origins": sorted(selected_origins)})
    weekday = "weekday" in interpretation.grouping
    categories = [field for field in interpretation.grouping if field != "weekday"]
    category = categories[0] if categories else None
    expressions = {"origin": "f.origin", "carrier": "f.carrier", "airline_name": "f.carrier"}
    if any(field not in expressions for field in categories):
        raise InvalidPlanError("Unsupported daily grouping.")
    code = (
        "CAST(json_array(" + ", ".join(expressions[field] for field in categories) + ") AS VARCHAR)"
        if len(categories) > 1
        else expressions[category]
        if category
        else "'overall'"
    )
    contribution = (
        "count(DISTINCT f.dest)"
        if interpretation.operation_id == "daily_distinct_mean"
        else "sum(p.seats)"
    )
    daily = (
        "SELECT make_date(f.year,f.month,f.day) AS day, "
        + code
        + " AS code, "
        + contribution
        + " AS contribution, count(*) AS scoped_count, "
        + (
            "count(f.dest)"
            if interpretation.operation_id == "daily_distinct_mean"
            else "count(p.seats)"
        )
        + " AS known_count"
        + source
        + " GROUP BY 1, 2"
    )
    from airport_analytics.data.coverage import calendar_eligibility

    observed = common["scope"].observed_period
    requested = interpretation.date_scope or observed
    start = requested.start or (observed.start if observed else None) if requested else None
    end = requested.end or (observed.end if observed else None) if requested else None
    eligible = []
    eligibility = None
    if start and end:
        eligibility = calendar_eligibility(
            executor.coverage,
            common["scope"].origins,
            start,
            end,
            set(),
            "verified_calendar_days",
        )
        eligible = eligibility["dates"]
    observed_basis = interpretation.denominator_basis == "observed_operating_days"
    dates_sql = (
        "SELECT DISTINCT day FROM daily" if observed_basis else "SELECT unnest(?::DATE[]) AS day"
    )
    params = [*parameters] if observed_basis else [*parameters, eligible]
    origin_specific = "origin" in categories
    origin_expression = (
        f"json_extract_string(c.code, '$[{categories.index('origin')}]')"
        if "origin" in categories and len(categories) > 1
        else "c.code"
    )
    if origin_specific and observed_basis:
        daily_origin = (
            f"json_extract_string(code, '$[{categories.index('origin')}]')"
            if len(categories) > 1
            else "code"
        )
        dates_sql = f"SELECT DISTINCT {daily_origin} AS origin_code, day FROM daily"
    elif origin_specific:
        origin_codes, origin_dates = [], []
        for origin in common["scope"].origins:
            if start and end:
                local = calendar_eligibility(
                    executor.coverage,
                    [origin],
                    start,
                    end,
                    set(),
                    "verified_calendar_days",
                )
                for day in local["dates"]:
                    origin_codes.append(origin)
                    origin_dates.append(day)
        dates_sql = "SELECT unnest(?::VARCHAR[]) AS origin_code, unnest(?::DATE[]) AS day"
        params = [*parameters, origin_codes, origin_dates]
    categories_sql = "SELECT DISTINCT code FROM daily" if category else "SELECT 'overall' AS code"
    # The date set is shared across airlines; absent airline/day rows contribute zero.
    cte = (
        "WITH daily AS (" + daily + "), dates AS (" + dates_sql + "), "
        "categories AS (" + categories_sql + "), "
        "grid AS (SELECT c.code, d.day, coalesce(x.contribution, 0) AS contribution, "
        "coalesce(x.scoped_count, 0) AS scoped_count, coalesce(x.known_count, 0) AS known_count "
        "FROM categories c "
        + (
            f"JOIN dates d ON {origin_expression}=d.origin_code"
            if origin_specific
            else "CROSS JOIN dates d"
        )
        + " LEFT JOIN daily x ON x.code IS NOT DISTINCT FROM c.code "
        "AND x.day=d.day), "
        "groups AS (SELECT c.code, "
        + (
            "w.weekday FROM categories c CROSS JOIN range(1,8) w(weekday)"
            if weekday
            else "0 AS weekday FROM categories c"
        )
        + "), totals AS (SELECT code, "
        + ("isodow(day)" if weekday else "0")
        + " AS weekday, "
        "sum(contribution) AS numerator, count(*) AS days, sum(scoped_count) AS scoped_count, "
        "sum(known_count) AS known_count, "
        "count(*) FILTER (WHERE scoped_count=known_count) AS complete_days "
        "FROM grid GROUP BY 1,2), combined AS (SELECT g.code, g.weekday, "
        "t.numerator, coalesce(t.days,0) AS days, coalesce(t.scoped_count,0) AS scoped_count, "
        "coalesce(t.known_count,0) AS known_count, coalesce(t.complete_days,0) AS complete_days "
        "FROM groups g LEFT JOIN totals t ON g.code IS NOT DISTINCT FROM t.code "
        "AND g.weekday=t.weekday) "
    )
    direction = interpretation.order[0].direction if interpretation.order else "asc"
    rank = (
        "numerator/nullif(days,0) " + direction.upper() + " NULLS LAST, code, weekday"
        if interpretation.family == "ranking"
        else "code, weekday"
    )
    grouped = query(
        executor,
        interpretation,
        cte + "SELECT *, count(*) OVER () AS available, count(*) OVER "
        "(PARTITION BY numerator/nullif(days,0)) AS equal_values FROM combined ORDER BY "
        + rank
        + " LIMIT ?",
        [*params, interpretation.selection],
        [
            "code",
            "weekday",
            "numerator",
            "days",
            "scoped_count",
            "known_count",
            "complete_days",
            "available",
            "equal_values",
        ],
    )
    values = []
    directory = executor.entity_directory()
    common["fields"] = [
        EvidenceField(
            field_id=field,
            label=field.replace("_", " "),
            role="category",
            unit=None,
            unit_provenance=None,
        )
        for field in interpretation.grouping
    ] + common["fields"]
    for row in grouped:
        days = row["days"]
        identities = []
        if category:
            codes = json.loads(row["code"]) if len(categories) > 1 else [row["code"]]
            for field, value in zip(categories, codes, strict=True):
                references = directory.airports if field == "origin" else directory.airlines
                name = references.get(value)
                identities.append(
                    CategoryIdentity(
                        field_id=field,
                        code=value,
                        label=name or value,
                        status="missing"
                        if value is None
                        else ("known" if value in references else "unmatched"),
                    )
                )
        if weekday:
            identities.append(
                CategoryIdentity(
                    field_id="weekday",
                    code=str(row["weekday"]),
                    label=[
                        "Monday",
                        "Tuesday",
                        "Wednesday",
                        "Thursday",
                        "Friday",
                        "Saturday",
                        "Sunday",
                    ][row["weekday"] - 1],
                    status="known",
                )
            )
        value = row["numerator"] / days if days and row["numerator"] is not None else None
        if (
            interpretation.operation_id == "daily_capacity_mean"
            and row["scoped_count"]
            and not row["known_count"]
        ):
            value = None
        numeric = number(
            value,
            ("no_matching_records" if observed_basis else "no_verified_days")
            if not days
            else "unknown_capacity",
        )
        values.append(
            DailyMeanEvidence(
                identity=identities,
                measures={interpretation.measure_ids[0]: numeric},
                scoped_count=row["scoped_count"],
                sample_size=row["known_count"],
                missing_count=row["scoped_count"] - row["known_count"],
                tied=row["equal_values"] > 1 and value is not None,
                value=numeric,
                numerator=row["numerator"] if days else None,
                eligible_days=days,
                known_contribution_count=row["known_count"],
                unknown_contribution_count=row["scoped_count"] - row["known_count"],
                complete_days=row["complete_days"],
                incomplete_days=days - row["complete_days"],
                provisional=observed_basis or row["scoped_count"] != row["known_count"],
            )
        )
    available = grouped[0]["available"] if grouped else 0
    ratios = [
        row["numerator"] / row["days"] if row["days"] and row["numerator"] is not None else None
        for row in grouped
    ]
    cutoff_tie = bool(
        grouped
        and available > len(grouped)
        and ratios[-1] is not None
        and grouped[-1]["equal_values"] > ratios.count(ratios[-1])
    )
    common["selection"] = EvidenceSelection(
        available=available,
        selected=len(values),
        omitted=available - len(values),
        cutoff_tie=cutoff_tie,
    )
    dates_count = query(
        executor,
        interpretation,
        cte + "SELECT count(DISTINCT day) AS n FROM dates",
        params,
        ["n"],
        "daily_support",
    )[0]["n"]
    support = query(
        executor,
        interpretation,
        cte + "SELECT CAST(day AS VARCHAR) AS day, code, contribution, scoped_count, known_count, "
        "count(*) OVER () AS available FROM grid ORDER BY day, code LIMIT 500",
        params,
        ["day", "code", "contribution", "scoped_count", "known_count", "available"],
        "daily_support",
    )
    common["daily_support"] = [
        {key: value for key, value in row.items() if key != "available"} for row in support
    ]
    common["missingness"].update(
        available_daily_support=support[0]["available"] if support else 0,
        selected_daily_support=len(support),
        omitted_daily_support=(support[0]["available"] if support else 0) - len(support),
    )
    updates = {
        "eligible_days": eligibility["eligible_days"]
        if eligibility and not observed_basis
        else dates_count,
    }
    if eligibility:
        updates.update(
            {
                key: eligibility[key]
                for key in (
                    "requested_days",
                    "verified_days",
                    "unknown_days",
                )
            }
        )
        updates["coverage_status"] = (
            "verified"
            if eligibility["unknown_days"] == 0
            else "partial"
            if eligibility["verified_days"]
            else "unknown"
        )
    common["scope"] = common["scope"].model_copy(update=updates)
    if executor.coverage.warning:
        common["limitations"].append(executor.coverage.warning)
    common["limitations"].append(
        "Daily means use the complete eligible date set, never the bounded supporting table. "
        "Unknown seat contributions make known-seat capacity a provisional lower-bound proxy."
    )
    return DailyMeanResult(**common, kind="daily_mean", values=values)


def execute_multi_stage(executor, interpretation, report_id, *, timed_out: Callable[[], bool]):
    common = common_evidence(executor, interpretation, report_id)
    if interpretation.operation_id == "distribution":
        return distribution(executor, interpretation, common, timed_out=timed_out)
    if interpretation.operation_id == "period_change":
        return period_change(executor, interpretation, common)
    if interpretation.operation_id in {"daily_distinct_mean", "daily_capacity_mean"}:
        return daily_mean(executor, interpretation, common)
    if interpretation.operation_id in {"flight_relationship", "weather_relationship"}:
        from airport_analytics.analytics.pair_metrics import build_pairing, build_weather
        from airport_analytics.models import RelationshipResult

        if interpretation.operation_id == "weather_relationship":
            return build_weather(executor, interpretation, common)
        return RelationshipResult(
            **common, kind="relationship", pairing=build_pairing(executor, interpretation)
        )
    raise InvalidPlanError("Unsupported multi-stage operation.")
