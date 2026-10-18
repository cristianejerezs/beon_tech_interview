from decimal import Decimal
from math import isclose
from pathlib import Path

import pytest

from airport_analytics.analytics import pair_metrics
from airport_analytics.analytics.execution import DuckDBExecutor
from airport_analytics.analytics.pair_metrics import build_pairing, build_weather
from airport_analytics.models import (
    AnalyticalDefinition,
    EvidenceFormat,
    EvidenceScope,
    EvidenceSelection,
    PairEvidence,
    ResolvedInterpretation,
    WeatherPanelResult,
)
from tests.exploration_oracles import number, pearson, read_rows, weather_pairs

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "exploration"


def interpretation(operation: str, *, grouping=None, filters=None) -> ResolvedInterpretation:
    weather = operation == "weather_relationship"
    return ResolvedInterpretation(
        request_id="pair-test",
        revision=1,
        section_id="section-pair",
        original_clause="Compare delays with weather." if weather else "Compare delays.",
        family="numeric_relationship",
        operation_id=operation,
        measure_ids=["mean_departure_delay"] if weather else ["departure_delay", "arrival_delay"],
        population="flights",
        filters=filters or [],
        grouping=grouping or [],
        definition=AnalyticalDefinition(
            unit="minutes" if weather else "paired_units",
            numerator=None,
            denominator=None,
            weighting="equal_origin_hour" if weather else "source_record",
            additivity="non_additive",
            match_rules=[],
            exclusions=[],
        ),
        grain="origin_hour" if weather else "flight_pair",
        pairing=None if weather else {"x": "departure_delay", "y": "arrival_delay"},
        snapshot_id="a" * 64,
        context_id="b" * 64,
    )


def common_evidence(interpretation: ResolvedInterpretation) -> dict:
    return {
        "result_version": 2,
        "evidence_version": 2,
        "report_id": "report-pair-test",
        "section_id": interpretation.section_id,
        "snapshot_id": interpretation.snapshot_id,
        "context_id": interpretation.context_id,
        "definition": interpretation.definition,
        "grain": interpretation.grain,
        "scope": EvidenceScope(
            filters=interpretation.filters,
            requested_period=None,
            observed_period=None,
            origins=[],
            coverage_status="unknown",
            denominator_basis="not_applicable",
            requested_days=None,
            verified_days=0,
            unknown_days=None,
            observed_days=0,
            eligible_days=None,
        ),
        "fields": [],
        "order": [],
        "missingness": {},
        "selection": EvidenceSelection(available=1, selected=1, omitted=0, cutoff_tie=False),
        "format": EvidenceFormat(locale="en", computed_places=2, rounding=None),
        "limitations": [],
        "daily_support": [],
        "route_support": [],
    }


def test_flight_pairing_matches_independent_rows_and_disjoint_missingness():
    rows = read_rows(FIXTURES / "nyc_flights_fixed.csv")
    known = [
        (row["column00"], number(row["dep_delay"]), number(row["arr_delay"]))
        for row in rows
        if number(row["dep_delay"]) is not None and number(row["arr_delay"]) is not None
    ]

    with DuckDBExecutor(str(FIXTURES)) as executor:
        result = build_pairing(executor, interpretation("flight_relationship"))

    assert isinstance(result, PairEvidence)
    assert [(pair.source_id, pair.x, pair.y) for pair in result.pairs] == known
    assert result.pair_count == len(known) == 8
    assert result.scoped_count == len(rows) == 9
    assert (result.x_missing_only, result.y_missing_only, result.both_missing) == (0, 0, 1)


def test_flight_pairing_uses_full_population_density_above_threshold():
    with DuckDBExecutor(str(FIXTURES)) as executor:
        executor._connection.execute(
            """
            CREATE TEMP TABLE expanded_flights AS
            SELECT CAST(row_number() OVER () AS VARCHAR) AS column00,
                   f.* EXCLUDE (column00)
            FROM flights f CROSS JOIN range(1000)
            """
        )
        executor._connection.execute(
            "CREATE OR REPLACE TEMP TABLE flights AS SELECT * FROM expanded_flights"
        )
        result = build_pairing(executor, interpretation("flight_relationship"))

    assert result.pair_count == 8000
    assert result.scoped_count == 9000
    assert result.both_missing == 1000
    assert result.pairs is None
    assert result.density is not None
    assert sum(cell.count for cell in result.density.cells) == result.pair_count
    assert len(result.density.x_edges) <= 21
    assert len(result.density.y_edges) <= 21


def test_weather_panel_matches_independent_hourly_oracle_with_unverified_units():
    rows = read_rows(FIXTURES / "nyc_flights_fixed.csv")
    rows = [row for row in rows if row["origin"] == "JFK"]
    weather = read_rows(FIXTURES / "nyc_weather.csv")
    expected_temp = weather_pairs(rows, weather, "temp")
    selected = [(delay, value) for _, delay, value in expected_temp]
    expected_correlation = pearson(selected)
    analysis = interpretation(
        "weather_relationship",
        filters=[{"field_id": "origin", "operator": "eq", "value": "JFK"}],
    )

    with DuckDBExecutor(str(FIXTURES)) as executor:
        result = build_weather(executor, analysis, common_evidence(analysis))

    assert isinstance(result, WeatherPanelResult)
    by_variable = {item.variable: item for item in result.variables}
    assert set(by_variable) == {"temp", "wind_speed", "precip", "visib"}
    assert by_variable["temp"].pairing.pair_count == len(expected_temp) == 4
    assert isclose(by_variable["temp"].coefficient.value, float(expected_correlation))
    assert by_variable["temp"].pairing.scoped_count == 7
    assert by_variable["temp"].pairing.x_missing_only == 2
    assert result.missingness["weather_scope_flights"] == len(rows)
    assert result.missingness["weather_scope_origin_hours"] == 7
    assert result.missingness["weather_unmatched_origin_hours"] == 2
    assert result.weather_units_status == "unverified"
    assert not result.precipitation_comparison
    assert all(item.pairing.x_unit == "recorded units (unverified)" for item in result.variables)
    assert any("Provisional Pearson" in warning for warning in result.limitations)


def test_weather_precipitation_comparison_keeps_matched_missing_category(monkeypatch):
    analysis = interpretation(
        "weather_relationship",
        filters=[{"field_id": "origin", "operator": "eq", "value": "JFK"}],
    )

    with DuckDBExecutor(str(FIXTURES)) as executor:
        monkeypatch.setattr(pair_metrics, "_weather_units_verified", lambda _executor: True)
        result = build_weather(executor, analysis, common_evidence(analysis))

    by_code = {group.identity[-1].code: group for group in result.precipitation_comparison}
    assert {"none", "light", "at_least_0_1_in", "missing_precipitation"}.issubset(by_code)
    missing = by_code["missing_precipitation"]
    assert missing.scoped_count == 2
    assert missing.sample_size == 1
    assert missing.measures["weather_context_departure_delay"].value == 10


def test_weather_hourly_means_pair_equal_hour_weighted_values(monkeypatch):
    rows = read_rows(FIXTURES / "nyc_flights_fixed.csv")
    oracle = weather_pairs(
        [row for row in rows if row["origin"] == "JFK"],
        read_rows(FIXTURES / "nyc_weather.csv"),
        "temp",
    )
    key, delay_mean, temperature = oracle[0]
    assert key == ("JFK", "2013-01-01T10:00:00Z")
    assert delay_mean == Decimal("7.5")
    assert temperature == Decimal("30")

    analysis = interpretation(
        "weather_relationship",
        filters=[{"field_id": "origin", "operator": "eq", "value": "JFK"}],
    )
    with DuckDBExecutor(str(FIXTURES)) as executor:
        monkeypatch.setattr(pair_metrics, "_weather_units_verified", lambda _executor: True)
        pairing = build_pairing(executor, analysis, weather_variable="temp", origin="JFK")

    assert pairing.pair_count == len(oracle) == 4
    assert pairing.pairs[0].source_id == "JFK|2013-01-01T10:00:00Z"
    assert pairing.pairs[0].x == 30
    assert pairing.pairs[0].y == 7.5


def test_provisional_pearson_is_invariant_to_positive_linear_unit_conversions(tmp_path):
    import csv
    import shutil

    source = tmp_path / "converted"
    shutil.copytree(FIXTURES, source)
    path = source / "nyc_weather.csv"
    rows = read_rows(path)
    conversions = {
        "temp": (1.8, 32),
        "wind_speed": (1.609344, 0),
        "precip": (25.4, 0),
        "visib": (1.609344, 0),
    }
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            for variable, (scale, offset) in conversions.items():
                if row[variable] != "NA":
                    row[variable] = str(float(row[variable]) * scale + offset)
            writer.writerow(row)
    analysis = interpretation("weather_relationship")
    results = []
    for folder in [FIXTURES, source]:
        with DuckDBExecutor(str(folder)) as executor:
            results.append(build_weather(executor, analysis, common_evidence(analysis)))
    for original, converted in zip(results[0].variables, results[1].variables, strict=True):
        assert original.coefficient.value == pytest.approx(converted.coefficient.value)
        assert original.pairing.pair_count == converted.pairing.pair_count
        assert converted.pairing.x_unit == "recorded units (unverified)"


def test_real_unit_declaration_enables_bands_but_stale_declaration_is_provisional(tmp_path):
    import hashlib
    import json

    document = tmp_path / "test-unit-evidence.txt"
    document.write_text("Synthetic test fixture: F, mph, inches, miles.", encoding="utf-8")
    declaration = tmp_path / "test-units.json"
    payload = {
        "schema_version": 1,
        "weather_sha256": hashlib.sha256((FIXTURES / "nyc_weather.csv").read_bytes()).hexdigest(),
        "units": {"temp": "F", "wind_speed": "mph", "precip": "inches", "visib": "miles"},
        "reviewed_by": "synthetic-test-reviewer",
        "evidence_reference": document.name,
        "evidence_sha256": hashlib.sha256(document.read_bytes()).hexdigest(),
    }
    declaration.write_text(json.dumps(payload), encoding="utf-8")
    analysis = interpretation("weather_relationship")
    with DuckDBExecutor(str(FIXTURES), weather_units_path=declaration) as executor:
        verified = build_weather(executor, analysis, common_evidence(analysis))
    assert verified.weather_units_status == "verified"
    assert verified.precipitation_comparison
    assert [item.pairing.x_unit for item in verified.variables] == ["F", "mph", "inches", "miles"]
    payload["weather_sha256"] = "0" * 64
    declaration.write_text(json.dumps(payload), encoding="utf-8")
    with DuckDBExecutor(str(FIXTURES), weather_units_path=declaration) as executor:
        stale = build_weather(executor, analysis, common_evidence(analysis))
    assert stale.weather_units_status == "unverified"
    assert not stale.precipitation_comparison


def test_provisional_weather_survives_storage_csv_pdf_and_bundle(tmp_path):
    import csv
    import io
    import json
    import zipfile

    from pydantic import ValidationError
    from pypdf import PdfReader

    from airport_analytics.auth import AnalystIdentity
    from airport_analytics.history.repository import ReportRepository
    from airport_analytics.reports.export import (
        export_report_bundle,
        export_report_csv,
        export_report_pdf,
    )
    from airport_analytics.storage import Storage
    from tests.integration.test_exploration_summaries import evidence, generate

    with DuckDBExecutor(str(FIXTURES)) as executor:
        outcome = generate(
            executor,
            family="numeric_relationship",
            operation_id="weather_relationship",
            measure_ids=["mean_departure_delay"],
        )
    result = evidence(outcome)
    assert "Temperature: r =" in outcome.report.sections[0].narrative
    assert "valid origin-hours" in outcome.report.sections[0].narrative
    identity = AnalystIdentity("owner", "synthetic", "owner")
    repository = ReportRepository(Storage(tmp_path / "weather.sqlite3"))
    repository.save_report(outcome.report, identity)
    saved = repository.get_report(identity, outcome.report.report_id)
    assert saved == outcome.report
    rows = list(csv.DictReader(io.StringIO(export_report_csv(saved).decode("utf-8-sig"))))
    assert json.loads(rows[0]["_meta_evidence_details"])["weather_units_status"] == "unverified"
    assert "Provisional Pearson" in rows[0]["_meta_limitations"]
    with zipfile.ZipFile(
        io.BytesIO(
            export_report_bundle(
                saved,
                analyst_id="owner",
                session_id="session",
            )
        )
    ) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["sections"][0]["weather_units_status"] == "unverified"
        for variable in manifest["sections"][0]["auxiliary_files"]:
            exported = list(
                csv.DictReader(
                    io.StringIO(
                        archive.read(variable["file"]).decode("utf-8-sig"),
                    )
                )
            )
            assert exported[0]["_meta_weather_units_status"] == "unverified"
            context = json.loads(exported[0]["_meta_auxiliary_context"])
            assert context["pair_population"]["x_unit"] == "recorded units (unverified)"
    text = "\n".join(
        page.extract_text()
        for page in PdfReader(
            io.BytesIO(
                export_report_pdf(saved),
            )
        ).pages
    )
    assert "Provisional Pearson" in text
    assert "Temperature: r =" in text
    assert text.index("Weather correlations") < text.index("Known, missing and unmatched")
    assert "Precipitation descriptive comparison: []" not in text
    old_section = saved.sections[0].model_copy(
        update={"narrative": "Weather Relationship: scoped historical records."}
    )
    old_report = saved.model_copy(update={"sections": [old_section]})
    old_text = "\n".join(
        page.extract_text() for page in PdfReader(io.BytesIO(export_report_pdf(old_report))).pages
    )
    assert "Temperature: r =" in old_text
    assert "Weather Relationship: scoped historical records." not in old_text
    payload = result.model_dump(mode="json")
    payload["variables"][0]["pairing"]["x_unit"] = "F"
    with pytest.raises(ValidationError):
        WeatherPanelResult.model_validate(payload)


def test_weather_findings_explain_user_coefficients_and_ties():
    from airport_analytics.reports.rendering import weather_findings

    analysis = interpretation("weather_relationship")
    with DuckDBExecutor(str(FIXTURES)) as executor:
        payload = build_weather(executor, analysis, common_evidence(analysis)).model_dump()
    for item, value in zip(
        payload["variables"],
        [0.1155002444, 0.0793510024, 0.1587857922, -0.1681366402],
        strict=True,
    ):
        item["coefficient"] = {"value": value, "absence": None}
    result = WeatherPanelResult.model_validate(payload)
    text = weather_findings(result)
    assert "Temperature: r = 0.116" in text
    assert "Wind speed: r = 0.079" in text
    assert "Precipitation: r = 0.159" in text
    assert "Visibility: r = -0.168" in text
    assert "higher mean departure delays" in text
    assert "lower mean departure delays" in text
    assert "available variables: visibility (|r| = 0.168)" in text
    assert "statistical significance" in text
    payload["variables"][2]["coefficient"]["value"] = 0.1681366402
    tied = weather_findings(WeatherPanelResult.model_validate(payload))
    assert "precipitation, visibility (|r| = 0.168)" in tied


def test_weather_findings_handle_zero_unavailable_and_airport_breakdowns():
    from airport_analytics.models import NumericEvidence
    from airport_analytics.reports.rendering import weather_findings

    analysis = interpretation("weather_relationship", grouping=["origin"])
    with DuckDBExecutor(str(FIXTURES)) as executor:
        result = build_weather(executor, analysis, common_evidence(analysis))
    text = weather_findings(result)
    assert "JFK:" in text
    assert "LGA:" in text
    assert "correlation unavailable" in text
    assert "All scoped origins combined:" not in text
    # Isolate wording from the numerical calculation, which has independent oracle tests.
    variables = [
        item.model_copy(update={"coefficient": NumericEvidence(value=0, absence=None)})
        for item in result.variables
    ]
    zero = weather_findings(result.model_copy(update={"variables": variables}))
    assert "no observed linear association" in zero
    assert "Largest absolute correlation" not in zero
