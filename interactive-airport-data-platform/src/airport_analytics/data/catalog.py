"""Versioned, closed source and metric catalog used by plan validation and SQL compilation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SCHEMA_VERSION = "1.1"

EXPLORATION_CATALOG_VERSION = "2.7"
ExplorationOperation = Literal[
    "aggregate",
    "entity_list",
    "flight_records",
    "period_change",
    "distribution",
    "flight_relationship",
    "daily_distinct_mean",
    "departure_delay_total",
    "daily_capacity_mean",
    "aircraft_frequency",
    "weather_relationship",
]
ExplorationMeasure = Literal[
    "flight_count",
    "distinct_flight_number_count",
    "distinct_destination_count",
    "distinct_connected_airport_count",
    "mean_departure_delay",
    "mean_arrival_delay",
    "mean_distance",
    "distinct_aircraft_count",
    "mean_seats",
    "weather_context_departure_delay",
    "departure_delay",
    "arrival_delay",
    "distance",
    "positive_delay_minutes",
    "net_delay_minutes",
    "known_reference_seats",
    "distinct_tailnums",
    "explicit_flight_frequency",
]
ExplorationDimension = Literal[
    "airport",
    "origin",
    "destination",
    "carrier",
    "airline_name",
    "tailnum",
    "aircraft_manufacturer",
    "aircraft_model",
    "weather_precipitation_band",
    "flight_date",
    "flight_week",
    "flight_month",
    "month_of_year",
    "weekday",
]


@dataclass(frozen=True)
class ExplorationDefinition:
    unit: str
    weighting: str
    additivity: Literal["additive", "non_additive"]
    dimensions: frozenset[str]
    required_tables: frozenset[str] = frozenset()


_V2_DATES = frozenset({"flight_date", "flight_week", "flight_month", "month_of_year"})
_V2_COMMON = _V2_DATES | {
    "origin",
    "destination",
    "carrier",
    "airline_name",
    "tailnum",
    "aircraft_manufacturer",
    "aircraft_model",
    "weather_precipitation_band",
}
EXPLORATION_MEASURES: dict[str, ExplorationDefinition] = {
    "departure_delay": ExplorationDefinition(
        "minutes", "source_record", "non_additive", frozenset()
    ),
    "arrival_delay": ExplorationDefinition("minutes", "source_record", "non_additive", frozenset()),
    "distance": ExplorationDefinition("miles", "source_record", "non_additive", frozenset()),
    "flight_count": ExplorationDefinition(
        "flights", "source_record", "additive", _V2_COMMON | {"airport"}
    ),
    "distinct_flight_number_count": ExplorationDefinition(
        "distinct_flight_numbers", "distinct_carrier_flight_number", "non_additive", _V2_COMMON
    ),
    "distinct_destination_count": ExplorationDefinition(
        "destinations", "distinct_destination", "non_additive", _V2_DATES | {"origin"}
    ),
    "distinct_connected_airport_count": ExplorationDefinition(
        "connected_airports",
        "distinct_neighbour",
        "non_additive",
        _V2_DATES | {"airport", "carrier", "airline_name"},
    ),
    "mean_departure_delay": ExplorationDefinition("minutes", "flight", "non_additive", _V2_COMMON),
    "mean_arrival_delay": ExplorationDefinition("minutes", "flight", "non_additive", _V2_COMMON),
    "mean_distance": ExplorationDefinition(
        "miles", "flight", "non_additive", _V2_COMMON - {"aircraft_manufacturer", "aircraft_model"}
    ),
    "distinct_aircraft_count": ExplorationDefinition(
        "aircraft", "distinct_tailnum", "non_additive", _V2_COMMON
    ),
    "mean_seats": ExplorationDefinition(
        "seats", "flight", "non_additive", _V2_COMMON, frozenset({"planes"})
    ),
    "weather_context_departure_delay": ExplorationDefinition(
        "minutes",
        "flight",
        "non_additive",
        _V2_DATES | {"origin", "weather_precipitation_band"},
        frozenset({"weather"}),
    ),
    "positive_delay_minutes": ExplorationDefinition(
        "minutes", "source_record", "additive", _V2_COMMON
    ),
    "net_delay_minutes": ExplorationDefinition("minutes", "source_record", "additive", _V2_COMMON),
    "known_reference_seats": ExplorationDefinition(
        "seats_per_day",
        "equal_day",
        "non_additive",
        frozenset({"carrier", "airline_name", "origin"}),
        frozenset({"planes"}),
    ),
    "distinct_tailnums": ExplorationDefinition(
        "aircraft",
        "distinct_tailnum",
        "non_additive",
        _V2_DATES | {"origin", "aircraft_manufacturer", "aircraft_model"},
        frozenset({"planes"}),
    ),
    "explicit_flight_frequency": ExplorationDefinition(
        "flights",
        "source_record",
        "additive",
        _V2_DATES | {"origin", "aircraft_manufacturer", "aircraft_model"},
        frozenset({"planes"}),
    ),
}
_V2_AGGREGATES = frozenset(
    {
        "flight_count",
        "distinct_flight_number_count",
        "distinct_destination_count",
        "mean_departure_delay",
        "mean_arrival_delay",
        "mean_distance",
        "distinct_aircraft_count",
        "mean_seats",
        "weather_context_departure_delay",
    }
)
EXPLORATION_OPERATIONS: dict[str, frozenset[str]] = {
    "aggregate": _V2_AGGREGATES | {"distinct_connected_airport_count"},
    "period_change": _V2_AGGREGATES,
    "entity_list": frozenset(),
    "flight_records": frozenset(),
    "distribution": frozenset({"departure_delay", "arrival_delay", "distance"}),
    "flight_relationship": frozenset({"departure_delay", "arrival_delay", "distance"}),
    "daily_distinct_mean": frozenset({"distinct_destination_count"}),
    "departure_delay_total": frozenset({"positive_delay_minutes", "net_delay_minutes"}),
    "daily_capacity_mean": frozenset({"known_reference_seats"}),
    "aircraft_frequency": frozenset({"distinct_tailnums", "explicit_flight_frequency"}),
    "weather_relationship": frozenset({"mean_departure_delay"}),
}


def summary_metric(measure_id: str) -> MetricDefinition:
    extra = {
        "positive_delay_minutes": (
            "SUM(CASE WHEN f.dep_delay IS NOT NULL THEN greatest(f.dep_delay, 0) END)",
            "COUNT(f.dep_delay)",
            "minutes",
        ),
        "net_delay_minutes": ("SUM(f.dep_delay)", "COUNT(f.dep_delay)", "minutes"),
        "distinct_tailnums": (
            "COUNT(DISTINCT CASE WHEN p.tailnum IS NOT NULL THEN f.tailnum END)",
            "COUNT(CASE WHEN p.tailnum IS NOT NULL THEN f.tailnum END)",
            "aircraft",
        ),
        "explicit_flight_frequency": (
            "COUNT(CASE WHEN p.tailnum IS NOT NULL THEN f.column00 END)",
            "COUNT(CASE WHEN p.tailnum IS NOT NULL THEN f.column00 END)",
            "flights",
        ),
    }
    if measure_id in extra:
        expression, observations, unit = extra[measure_id]
        return MetricDefinition(
            measure_id,
            expression,
            observations,
            measure_id.replace("_", " "),
            unit,
            "filtered historical flights",
            None,
            None,
        )
    legacy_id = {
        "distinct_aircraft_count": "aircraft_activity_count",
        "mean_seats": "mean_aircraft_seats",
        "weather_context_departure_delay": "mean_delay_by_weather_context",
    }.get(measure_id, measure_id)
    if measure_id not in EXPLORATION_OPERATIONS["aggregate"]:
        raise ValueError("This measure is not an approved summary metric.")
    return METRICS[legacy_id]


CONNECTED_ENDPOINTS_OBSERVATION = (
    "COUNT(CASE WHEN f.origin IS NOT NULL AND f.dest IS NOT NULL AND f.origin <> f.dest THEN 1 END)"
)


def summary_observation_expression(measure_id: str) -> str:
    if measure_id == "distinct_destination_count":
        return "COUNT(f.dest)"
    if measure_id == "distinct_connected_airport_count":
        return CONNECTED_ENDPOINTS_OBSERVATION
    if measure_id == "distinct_aircraft_count":
        return "COUNT(f.tailnum)"
    if measure_id == "weather_context_departure_delay":
        return "COUNT(CASE WHEN w.origin IS NOT NULL THEN f.dep_delay END)"
    return summary_metric(measure_id).observation_expression


EXPLORATION_FAMILIES: dict[str, frozenset[str]] = {
    "aggregate": frozenset(
        {
            "overall_summary",
            "grouped_summary",
            "ranking",
            "category_comparison",
            "historical_trend",
        }
    ),
    "entity_list": frozenset({"unique_entity_list"}),
    "flight_records": frozenset({"individual_records"}),
    "period_change": frozenset({"period_change"}),
    "distribution": frozenset({"distribution"}),
    "flight_relationship": frozenset({"numeric_relationship"}),
    "daily_distinct_mean": frozenset(
        {
            "overall_summary",
            "grouped_summary",
            "category_comparison",
            "ranking",
        }
    ),
    "departure_delay_total": frozenset(
        {
            "overall_summary",
            "grouped_summary",
            "ranking",
            "category_comparison",
            "historical_trend",
        }
    ),
    "daily_capacity_mean": frozenset({"ranking", "grouped_summary", "category_comparison"}),
    "aircraft_frequency": frozenset({"ranking", "grouped_summary", "category_comparison"}),
    "weather_relationship": frozenset({"numeric_relationship"}),
}


def exploration_definition(
    operation: str,
    measures: list[str],
    population: str = "flights",
) -> ExplorationDefinition | None:
    if operation == "entity_list" and population == "airport_connections":
        return ExplorationDefinition(
            "connected airports",
            "distinct_neighbour",
            "non_additive",
            frozenset(),
        )
    if operation in {"entity_list", "flight_records"}:
        return ExplorationDefinition(
            "entities" if operation == "entity_list" else "records",
            "distinct_code" if operation == "entity_list" else "source_record",
            "non_additive",
            frozenset(),
        )
    if not measures:
        return None
    if operation == "daily_distinct_mean":
        return ExplorationDefinition(
            "destinations_per_day", "equal_day", "non_additive", frozenset({"origin", "weekday"})
        )
    if operation == "weather_relationship":
        return ExplorationDefinition(
            "minutes",
            "equal_origin_hour",
            "non_additive",
            frozenset({"origin"}),
            frozenset({"weather"}),
        )
    if operation == "flight_relationship":
        return ExplorationDefinition("paired_units", "source_record", "non_additive", frozenset())
    return EXPLORATION_MEASURES[measures[0]]


def validate_exploration_combination(
    operation: str, measures: list[str], grouping: list[str]
) -> None:
    if operation not in EXPLORATION_OPERATIONS:
        raise ValueError("Unknown exploration operation.")
    allowed = EXPLORATION_OPERATIONS[operation]
    required_count = 2 if operation == "flight_relationship" else (0 if not allowed else 1)
    if len(measures) != required_count or len(set(measures)) != len(measures):
        raise ValueError("Incorrect or repeated operation measures.")
    if not set(measures).issubset(allowed):
        raise ValueError("Unsupported operation and measure combination.")
    if len(grouping) > 2 or len(set(grouping)) != len(grouping):
        raise ValueError("Grouping requires at most two distinct roles.")
    if {"carrier", "airline_name"}.issubset(grouping) or len(set(grouping) & _V2_DATES) > 1:
        raise ValueError("Duplicate grouping roles.")
    if operation in {"entity_list", "flight_records", "distribution", "flight_relationship"}:
        compatible = not grouping
    elif operation != "aggregate" and (
        "airport" in grouping or "distinct_connected_airport_count" in measures
    ):
        compatible = False
    elif operation == "daily_distinct_mean":
        compatible = set(grouping).issubset({"origin", "weekday"})
    elif operation == "weather_relationship":
        compatible = set(grouping).issubset({"origin"})
    elif operation == "aircraft_frequency":
        identities = set(grouping) & {"aircraft_manufacturer", "aircraft_model"}
        compatible = len(identities) == 1
        compatible = compatible and set(grouping).issubset(
            _V2_DATES | {"origin", "aircraft_manufacturer", "aircraft_model"}
        )
    elif operation == "daily_capacity_mean":
        compatible = bool(set(grouping) & {"carrier", "airline_name"})
        compatible = compatible and set(grouping).issubset({"carrier", "airline_name", "origin"})
    else:
        compatible = all(
            set(grouping).issubset(EXPLORATION_MEASURES[measure].dimensions) for measure in measures
        )
    if not compatible:
        raise ValueError("Unsupported operation and grouping combination.")


def validate_exploration_population(operation: str, family: str, population: str) -> None:
    if family not in EXPLORATION_FAMILIES[operation]:
        raise ValueError("Request family is incompatible with the operation.")
    if (operation == "entity_list") != (population != "flights"):
        raise ValueError("Population is incompatible with the operation.")


SOURCE_TEXT_FIELDS = {
    "flights": frozenset({"carrier", "tailnum", "origin", "dest"}),
    "airports": frozenset({"faa", "name", "dst", "timezone_name"}),
    "airlines": frozenset({"carrier", "name"}),
    "planes": frozenset({"tailnum", "type", "manufacturer", "model", "engine"}),
    "weather": frozenset({"origin"}),
}
SOURCE_FRACTIONAL_FIELDS = {
    "flights": frozenset(),
    "airports": frozenset({"latitude", "longitude"}),
    "airlines": frozenset(),
    "planes": frozenset(),
    "weather": frozenset(
        {"temp", "dewp", "humid", "wind_speed", "wind_gust", "precip", "pressure", "visib"}
    ),
}
SOURCE_GRAINS = {
    "flights": ("column00",),
    "airports": ("faa",),
    "airlines": ("carrier",),
    "planes": ("tailnum",),
    "weather": ("origin", "time_hour"),
}


@dataclass(frozen=True)
class DatasetDefinition:
    dataset_id: str
    filename: str
    table_name: str
    columns: tuple[str, ...]


@dataclass(frozen=True)
class FieldDefinition:
    field_id: str
    expression: str
    data_type: Literal["string", "number", "date"]
    filterable: bool = True
    required_tables: frozenset[str] = frozenset()


@dataclass(frozen=True)
class DimensionDefinition:
    dimension_id: str
    expression: str
    required_tables: frozenset[str] = frozenset()


@dataclass(frozen=True)
class MetricDefinition:
    metric_id: str
    expression: str
    observation_expression: str
    description: str
    unit: str
    population: str
    numerator: str | None
    denominator: str | None
    required_tables: frozenset[str] = frozenset()
    allowed_dimensions: frozenset[str] | None = None
    caveats: tuple[str, ...] = ()


DATASETS: dict[str, DatasetDefinition] = {
    "flights": DatasetDefinition(
        dataset_id="flights",
        filename="nyc_flights_fixed.csv",
        table_name="flights",
        columns=(
            "column00",
            "year",
            "month",
            "day",
            "dep_time",
            "sched_dep_time",
            "dep_delay",
            "arr_time",
            "sched_arr_time",
            "arr_delay",
            "carrier",
            "flight",
            "tailnum",
            "origin",
            "dest",
            "air_time",
            "distance",
            "hour",
            "minute",
            "time_hour",
        ),
    ),
    "airports": DatasetDefinition(
        dataset_id="airports",
        filename="nyc_airports.csv",
        table_name="airports",
        columns=(
            "faa",
            "name",
            "latitude",
            "longitude",
            "altitude",
            "timezone",
            "dst",
            "timezone_name",
        ),
    ),
    "airlines": DatasetDefinition(
        dataset_id="airlines",
        filename="nyc_airlines.csv",
        table_name="airlines",
        columns=("carrier", "name"),
    ),
    "planes": DatasetDefinition(
        dataset_id="planes",
        filename="nyc_planes.csv",
        table_name="planes",
        columns=(
            "tailnum",
            "year",
            "type",
            "manufacturer",
            "model",
            "engines",
            "seats",
            "speed",
            "engine",
        ),
    ),
    "weather": DatasetDefinition(
        dataset_id="weather",
        filename="nyc_weather.csv",
        table_name="weather",
        columns=(
            "origin",
            "year",
            "month",
            "day",
            "hour",
            "temp",
            "dewp",
            "humid",
            "wind_dir",
            "wind_speed",
            "wind_gust",
            "precip",
            "pressure",
            "visib",
            "time_hour",
        ),
    ),
}

DIMENSIONS: dict[str, DimensionDefinition] = {
    "origin": DimensionDefinition("origin", "f.origin"),
    "destination": DimensionDefinition("destination", "f.dest"),
    "carrier": DimensionDefinition("carrier", "f.carrier"),
    "airline_name": DimensionDefinition("airline_name", "a.name", frozenset({"airlines"})),
    "tailnum": DimensionDefinition("tailnum", "f.tailnum"),
    "aircraft_manufacturer": DimensionDefinition(
        "aircraft_manufacturer", "p.manufacturer", frozenset({"planes"})
    ),
    "aircraft_model": DimensionDefinition("aircraft_model", "p.model", frozenset({"planes"})),
    "flight_month": DimensionDefinition(
        "flight_month", "DATE_TRUNC('month', make_date(f.year, f.month, f.day))"
    ),
    "weather_precipitation_band": DimensionDefinition(
        "weather_precipitation_band",
        """CASE
            WHEN w.precip IS NULL THEN 'unmatched'
            WHEN w.precip = 0 THEN 'none'
            WHEN w.precip < 0.1 THEN 'light'
            ELSE 'at_least_0_1_in'
        END""",
        frozenset({"weather"}),
    ),
}

FIELDS: dict[str, FieldDefinition] = {
    "origin": FieldDefinition("origin", "f.origin", "string"),
    "destination": FieldDefinition("destination", "f.dest", "string"),
    "carrier": FieldDefinition("carrier", "f.carrier", "string"),
    "tailnum": FieldDefinition("tailnum", "f.tailnum", "string"),
    "airline_name": FieldDefinition(
        "airline_name", "a.name", "string", required_tables=frozenset({"airlines"})
    ),
    "aircraft_model": FieldDefinition(
        "aircraft_model", "p.model", "string", required_tables=frozenset({"planes"})
    ),
    "flight_year": FieldDefinition("flight_year", "f.year", "number"),
    "flight_month_number": FieldDefinition("flight_month_number", "f.month", "number"),
    "departure_delay": FieldDefinition("departure_delay", "f.dep_delay", "number"),
    "arrival_delay": FieldDefinition("arrival_delay", "f.arr_delay", "number"),
    "distance": FieldDefinition("distance", "f.distance", "number"),
    "flight_date": FieldDefinition("flight_date", "make_date(f.year, f.month, f.day)", "date"),
}

_ALL_DIMENSIONS = frozenset(DIMENSIONS)
_FLIGHT_DIMENSIONS = _ALL_DIMENSIONS - {"aircraft_manufacturer", "aircraft_model"}

METRICS: dict[str, MetricDefinition] = {
    "distinct_flight_number_count": MetricDefinition(
        metric_id="distinct_flight_number_count",
        expression=(
            "COUNT(DISTINCT CASE WHEN f.carrier IS NOT NULL AND f.flight IS NOT NULL "
            "THEN (f.carrier, f.flight) END)"
        ),
        observation_expression=(
            "COUNT(CASE WHEN f.carrier IS NOT NULL AND f.flight IS NOT NULL THEN 1 END)"
        ),
        description="Unique flight numbers within each airline, counted once across scoped dates.",
        unit="distinct_flight_numbers",
        population="Distinct airline and flight-number pairs among matching flight records.",
        numerator="Distinct non-missing airline and flight-number pairs",
        denominator=None,
        allowed_dimensions=_ALL_DIMENSIONS,
        caveats=(
            "Repeated dates, origins and destinations do not create additional flight numbers.",
            "This counts flight numbers, not operated departures or source rows.",
            "Missing airline codes or flight numbers are excluded, not counted as a flight.",
        ),
    ),
    "flight_count": MetricDefinition(
        metric_id="flight_count",
        expression="COUNT(*)",
        observation_expression="COUNT(*)",
        description="Number of flight records in the selected scope.",
        unit="flights",
        population="All flight records matching the selected scope.",
        numerator="Matching flight records",
        denominator=None,
        allowed_dimensions=_ALL_DIMENSIONS,
    ),
    "distinct_destination_count": MetricDefinition(
        metric_id="distinct_destination_count",
        expression="COUNT(DISTINCT f.dest)",
        observation_expression="COUNT(*)",
        description="Number of distinct destination airport codes.",
        unit="destinations",
        population="Distinct destinations among matching flight records.",
        numerator="Distinct destination codes",
        denominator=None,
        allowed_dimensions=frozenset({"origin", "flight_month"}),
        caveats=("The reported destinations are available in the supporting result rows.",),
    ),
    "distinct_connected_airport_count": MetricDefinition(
        metric_id="distinct_connected_airport_count",
        expression="COUNT(DISTINCT f.neighbour_airport)",
        observation_expression="COUNT(DISTINCT f.column00)",
        description=(
            "Number of distinct other airports (FAA codes) connected by at least one flight "
            "in either direction."
        ),
        unit="connected_airports",
        population="Flight records with two different non-missing airport codes.",
        numerator="Distinct airport codes reached from or arriving at the airport",
        denominator=None,
        allowed_dimensions=frozenset({"flight_month", "carrier"}),
        caveats=(
            "Each flight connects its origin and destination; both airports count the other.",
            "Self-connections and flights with a missing airport code are excluded.",
        ),
    ),
    "mean_departure_delay": MetricDefinition(
        metric_id="mean_departure_delay",
        expression="AVG(f.dep_delay)",
        observation_expression="COUNT(f.dep_delay)",
        description="Mean recorded departure delay; negative values indicate early departures.",
        unit="minutes",
        population="Matching flight records with a non-missing departure delay.",
        numerator="Sum of non-missing departure-delay minutes",
        denominator="Count of matching records with a non-missing departure delay",
        allowed_dimensions=_ALL_DIMENSIONS,
        caveats=("Missing departure delays are excluded, not treated as zero.",),
    ),
    "mean_arrival_delay": MetricDefinition(
        metric_id="mean_arrival_delay",
        expression="AVG(f.arr_delay)",
        observation_expression="COUNT(f.arr_delay)",
        description="Mean recorded arrival delay; negative values indicate early arrivals.",
        unit="minutes",
        population="Matching flight records with a non-missing arrival delay.",
        numerator="Sum of non-missing arrival-delay minutes",
        denominator="Count of matching records with a non-missing arrival delay",
        allowed_dimensions=_ALL_DIMENSIONS,
        caveats=("Missing arrival delays are excluded, not treated as zero.",),
    ),
    "mean_distance": MetricDefinition(
        metric_id="mean_distance",
        expression="AVG(f.distance)",
        observation_expression="COUNT(f.distance)",
        description="Mean scheduled route distance.",
        unit="miles",
        population="Matching flight records with a recorded route distance.",
        numerator="Sum of recorded route miles",
        denominator="Count of matching records with a recorded distance",
        allowed_dimensions=_FLIGHT_DIMENSIONS,
    ),
    "aircraft_activity_count": MetricDefinition(
        metric_id="aircraft_activity_count",
        expression="COUNT(DISTINCT f.tailnum)",
        observation_expression="COUNT(DISTINCT f.tailnum)",
        description="Distinct aircraft tail numbers observed in matching flight records.",
        unit="aircraft",
        population="Distinct non-missing tail numbers in matching flight records.",
        numerator="Distinct observed tail numbers",
        denominator=None,
        allowed_dimensions=_ALL_DIMENSIONS,
    ),
    "mean_aircraft_seats": MetricDefinition(
        metric_id="mean_aircraft_seats",
        expression="AVG(p.seats)",
        observation_expression="COUNT(p.seats)",
        description="Mean listed seat count for matched aircraft records.",
        unit="seats",
        population=(
            "Matching flight records with a tail number and matched aircraft record "
            "with known seats."
        ),
        numerator="Sum of listed seats across matched flight records",
        denominator="Count of matched flight records with known seat count",
        required_tables=frozenset({"planes"}),
        allowed_dimensions=_ALL_DIMENSIONS,
        caveats=("Repeated aircraft observations are counted once per matching flight record.",),
    ),
    "mean_delay_by_weather_context": MetricDefinition(
        metric_id="mean_delay_by_weather_context",
        expression="AVG(f.dep_delay)",
        observation_expression="COUNT(f.dep_delay)",
        description="Mean departure delay grouped by the matched origin-hour precipitation band.",
        unit="minutes",
        population=(
            "Matching flight records with non-missing departure delay and an exact "
            "origin/time weather match."
        ),
        numerator="Sum of non-missing departure-delay minutes in matched records",
        denominator="Count of matched records with a non-missing departure delay",
        required_tables=frozenset({"weather"}),
        allowed_dimensions=frozenset({"weather_precipitation_band", "origin", "flight_month"}),
        caveats=(
            "Weather is joined by exact origin and time_hour; unmatched records are "
            "excluded from this metric.",
            "Associations are contextual and do not establish causation.",
        ),
    ),
}

JOIN_SQL: dict[str, str] = {
    "airports_origin": ("LEFT JOIN airports o ON f.origin = o.faa"),
    "airports_destination": ("LEFT JOIN airports d ON f.dest = d.faa"),
    "airlines": "LEFT JOIN airlines a ON f.carrier = a.carrier",
    "planes": "LEFT JOIN planes p ON f.tailnum = p.tailnum",
    "weather": ("LEFT JOIN weather w ON f.origin = w.origin AND f.time_hour = w.time_hour"),
}


def required_joins(
    metric_id: str, dimensions: list[str], filter_ids: list[str], sort_id: str | None
) -> set[str]:
    metric = METRICS[metric_id]
    required = set(metric.required_tables)
    for dimension_id in dimensions:
        required.update(DIMENSIONS[dimension_id].required_tables)
    for field_id in filter_ids:
        required.update(FIELDS[field_id].required_tables)
    if sort_id in DIMENSIONS:
        required.update(DIMENSIONS[sort_id].required_tables)
    if "airports" in required:
        raise ValueError("Use an explicit origin or destination airport join.")
    return required
