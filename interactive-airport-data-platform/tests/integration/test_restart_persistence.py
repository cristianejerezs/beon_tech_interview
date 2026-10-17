from decimal import Decimal
from pathlib import Path

from airport_analytics.analytics.budget import BudgetLedger
from airport_analytics.auth import resolve_analyst_identity
from airport_analytics.consent.repository import ConsentRepository
from airport_analytics.history.repository import ReportRepository
from airport_analytics.storage import Storage
from tests.factories import make_report


def test_reports_consent_and_budget_survive_storage_reinitialization(
    tmp_path: Path,
) -> None:
    database = tmp_path / "restart.sqlite3"
    identity = resolve_analyst_identity("issuer", "restart-test")
    storage = Storage(database)
    report_repository = ReportRepository(storage)
    consent_repository = ConsentRepository(storage)
    budget = BudgetLedger(storage, monthly_cap_usd=Decimal("0.10"))
    report = make_report("persisted-report", identity.analyst_id, "persisted-session")
    report_repository.save_report(report, identity)
    event = consent_repository.record_event(
        identity,
        report.session_id,
        "faq",
        "grant",
        "v1",
    )
    reservation = budget.reserve(
        provider_id="test-provider",
        model_id="test-model",
        max_input_tokens=1,
        max_output_tokens=1,
        input_usd_per_million=Decimal("1000"),
        output_usd_per_million=Decimal("1000"),
        fee_fx_multiplier=Decimal("1"),
        maximum_extra_fee_usd=Decimal("0"),
    )

    reopened = Storage(database)
    assert ReportRepository(reopened).get_report(identity, report.report_id) == report
    assert ConsentRepository(reopened).latest_event(identity, report.session_id, "faq") == event
    assert (
        BudgetLedger(reopened, monthly_cap_usd=Decimal("0.10"))
        .get_reservation(reservation.reservation_id)
        .status
        == "reserved"
    )
