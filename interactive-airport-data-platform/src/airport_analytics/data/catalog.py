"""Versioned, closed source and metric catalog used by plan validation and SQL compilation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SCHEMA_VERSION = "1.0"


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
