"""Independent source-row oracles; deliberately imports no application calculations."""

from __future__ import annotations

import csv
from collections import defaultdict
from datetime import date, timedelta
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal, localcontext
from pathlib import Path

Row = dict[str, str]


def read_rows(path: Path) -> list[Row]:
    with path.open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def number(value: str) -> Decimal | None:
    if value in {"", "NA"}:
        return None
    parsed = Decimal(value)
    if not parsed.is_finite():
        raise ValueError("Nonfinite fixture measurement.")
    return parsed


def recorded_date(row: Row) -> date:
    return date(int(row["year"]), int(row["month"]), int(row["day"]))


def calendar_dates(start: date, end: date) -> tuple[date, ...]:
    if start > end:
        raise ValueError("Inverted calendar interval.")
    return tuple(start + timedelta(days=index) for index in range((end - start).days + 1))


def daily_destinations(rows: list[Row], dates: tuple[date, ...]) -> dict[date, int]:
    if len(dates) != len(set(dates)):
        raise ValueError("Repeated denominator date.")
    destinations: dict[date, set[str]] = {day: set() for day in dates}
    for row in rows:
        day = recorded_date(row)
        if day in destinations and row["dest"] not in {"", "NA"}:
            destinations[day].add(row["dest"])
    return {day: len(values) for day, values in destinations.items()}


def equal_day_mean(values: dict[date, int]) -> Decimal | None:
    if not values:
        return None
    with localcontext() as context:
        context.prec = 50
        return Decimal(sum(values.values())) / Decimal(len(values))


def weekday_means(values: dict[date, int]) -> dict[int, tuple[Decimal | None, int]]:
    result = {}
    for weekday in range(1, 8):
        selected = {day: count for day, count in values.items() if day.isoweekday() == weekday}
        result[weekday] = equal_day_mean(selected), len(selected)
    return result


def half_up(value: Decimal, places: int = 0) -> Decimal:
    if not 0 <= places <= 12 or not value.is_finite():
        raise ValueError("Invalid display rounding.")
    with localcontext() as context:
        context.prec = max(50, len(value.as_tuple().digits) + abs(value.adjusted()) + places + 2)
        return value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def delay_totals(rows: list[Row]) -> tuple[Decimal | None, Decimal | None, int, int]:
    known = [value for row in rows if (value := number(row["dep_delay"])) is not None]
    if not known:
        return None, None, 0, len(rows)
    return (
        sum((max(value, Decimal(0)) for value in known), Decimal(0)),
        sum(known, Decimal(0)),
        len(known),
        len(rows) - len(known),
    )


def capacity_days(
    rows: list[Row], planes: list[Row], dates: tuple[date, ...], carriers: tuple[str, ...]
) -> dict[tuple[str, date], tuple[Decimal, int, int]]:
    references = {row["tailnum"]: row for row in planes}
    if len(references) != len(planes):
        raise ValueError("Duplicate plane reference.")
    if len(set(dates)) != len(dates) or len(set(carriers)) != len(carriers):
        raise ValueError("Repeated denominator date or carrier.")
    totals = {(carrier, day): (Decimal(0), 0, 0) for carrier in carriers for day in dates}
    for row in rows:
        key = row["carrier"], recorded_date(row)
        if key not in totals:
            continue
        reference = references.get(row["tailnum"])
        seats = number(reference["seats"]) if reference else None
        if seats is not None and seats < 0:
            raise ValueError("Negative reference seats.")
        total, known, unknown = totals[key]
        totals[key] = (
            total + (seats if seats is not None else Decimal(0)),
            known + int(seats is not None),
            unknown + int(seats is None),
        )
    return totals


def aircraft_counts(
    rows: list[Row], planes: list[Row], *, by_model: bool, flight_activity: bool = False
) -> dict[tuple[str, ...], int]:
    references = {row["tailnum"]: row for row in planes}
    if len(references) != len(planes):
        raise ValueError("Duplicate plane reference.")
    grouped: dict[tuple[str, ...], set[str]] = defaultdict(set)
    flights: dict[tuple[str, ...], int] = defaultdict(int)
    for row in rows:
        plane = references.get(row["tailnum"])
        if plane is None or plane["manufacturer"] in {"", "NA"}:
            continue
        if by_model and plane["model"] in {"", "NA"}:
            continue
        key = (plane["manufacturer"], plane["model"]) if by_model else (plane["manufacturer"],)
        grouped[key].add(row["tailnum"])
        flights[key] += 1
    return dict(flights) if flight_activity else {key: len(tails) for key, tails in grouped.items()}


def bins(
    values: list[Decimal | None], width: Decimal
) -> tuple[list[tuple[Decimal, Decimal, int]], int]:
    if not width.is_finite() or width <= 0:
        raise ValueError("Invalid interval width.")
    known = [value for value in values if value is not None]
    if any(not value.is_finite() for value in known):
        raise ValueError("Nonfinite fixture measurement.")
    if not known:
        return [], len(values)
    lower = (min(known) / width).to_integral_value(rounding=ROUND_FLOOR) * width
    count = int(((max(known) - lower) / width).to_integral_value(rounding=ROUND_FLOOR)) + 1
    result = []
    for index in range(count):
        left = lower + index * width
        right = left + width
        result.append((left, right, sum(left <= value < right for value in known)))
    return result, len(values) - len(known)


def weather_pairs(
    rows: list[Row], weather: list[Row], variable: str
) -> list[tuple[tuple[str, str], Decimal, Decimal]]:
    references = {(row["origin"], row["time_hour"]): row for row in weather}
    if len(references) != len(weather):
        raise ValueError("Duplicate weather key.")
    delays: dict[tuple[str, str], list[Decimal]] = defaultdict(list)
    for row in rows:
        delay = number(row["dep_delay"])
        if delay is not None:
            delays[row["origin"], row["time_hour"]].append(delay)
    pairs = []
    with localcontext() as context:
        context.prec = 50
        for key, values in sorted(delays.items()):
            match = references.get(key)
            value = number(match[variable]) if match is not None else None
            if value is not None:
                pairs.append((key, sum(values, Decimal(0)) / len(values), value))
    return pairs


def pearson(pairs: list[tuple[Decimal, Decimal]]) -> Decimal | None:
    if any(not x.is_finite() or not y.is_finite() for x, y in pairs):
        raise ValueError("Nonfinite pair.")
    if len(pairs) < 3:
        return None
    with localcontext() as context:
        context.prec = 50
        mean_x = sum((x for x, _ in pairs), Decimal(0)) / len(pairs)
        mean_y = sum((y for _, y in pairs), Decimal(0)) / len(pairs)
        xx = sum(((x - mean_x) ** 2 for x, _ in pairs), Decimal(0))
        yy = sum(((y - mean_y) ** 2 for _, y in pairs), Decimal(0))
        if xx == 0 or yy == 0:
            return None
        xy = sum(((x - mean_x) * (y - mean_y) for x, y in pairs), Decimal(0))
        return xy / (xx * yy).sqrt()
