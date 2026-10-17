import subprocess
import sys
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


def test_committed_state_survives_separate_processes(tmp_path):
    database = tmp_path / "process-restart.sqlite3"
    script = r"""
import sys
from decimal import Decimal
from airport_analytics.storage import Storage
from airport_analytics.auth import resolve_analyst_identity
from airport_analytics.history.repository import ReportRepository
from airport_analytics.consent.repository import ConsentRepository
from airport_analytics.analytics.budget import BudgetLedger
from airport_analytics.errors import AuthorizationError
from tests.factories import make_report
storage = Storage(sys.argv[1])
owner = resolve_analyst_identity('issuer', 'owner')
reports = ReportRepository(storage)
events = ConsentRepository(storage)
ledger = BudgetLedger(storage)
if sys.argv[2] == 'write':
    reports.save_report(make_report('restart', owner.analyst_id, 'session'), owner)
    events.record_event(owner, 'session', 'faq', 'grant', 'v2-default-on')
    for index in range(2):
        reservation = ledger.reserve_cost(
            provider_id='synthetic', model_id='synthetic', maximum_charge_usd=Decimal('0.1')
        )
        if index == 0:
            ledger.settle(reservation.reservation_id, actual_usd=Decimal('0.05'))
        else:
            ledger.mark_uncertain(reservation.reservation_id, 'unknown acceptance')
else:
    assert reports.get_report(owner, 'restart').report_id == 'restart'
    assert events.latest_event(owner, 'session', 'faq').action == 'grant'
    from airport_analytics.consent.service import ConsentService
    assert not ConsentService(reports, events).is_active(owner, 'new-session', 'faq', {})
    assert ledger.remaining_usd() == Decimal('9.85')
    with storage.read() as connection:
        assert connection.execute(
            'SELECT acceptance_uncertain FROM usage_reservations WHERE status = ?',
            ('reserved',)
        ).fetchone()[0] == 1
    try:
        reports.get_report(resolve_analyst_identity('issuer', 'other'), 'restart')
    except AuthorizationError:
        pass
    else:
        raise AssertionError('ownership bypass')
"""
    for stage in ("write", "read"):
        completed = subprocess.run(
            [sys.executable, "-c", script, str(database), stage],
            cwd=Path(__file__).resolve().parents[2],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert completed.returncode == 0, completed.stderr
