from types import SimpleNamespace
from unittest.mock import Mock

from streamlit.testing.v1 import AppTest

import app as product_app
from airport_analytics.auth import resolve_development_identity
from airport_analytics.history.repository import ReportRepository
from airport_analytics.models import CompositeReportV2
from airport_analytics.storage import Storage
from tests.browser.test_app_authentication import _configure_development, _development_app
from tests.unit.test_exploration_results import scalar_report_payload


def test_saved_v2_history_is_readable_with_summary_exports_but_no_v1_refinement(
    monkeypatch,
    tmp_path,
):
    _configure_development(monkeypatch, tmp_path, "127.0.0.1")
    monkeypatch.setattr(product_app, "_executor", lambda *args: SimpleNamespace())
    monkeypatch.setattr(product_app, "LangChainPlanClient", lambda *args, **kwargs: Mock())
    app = AppTest.from_function(_development_app).run()
    app.button[0].click().run()
    next(toggle for toggle in app.toggle if toggle.label == "Use V2 summary exploration").set_value(
        False
    ).run()
    identity = resolve_development_identity(production=False, server_address="127.0.0.1")
    payload = scalar_report_payload() | {
        "analyst_id": identity.analyst_id,
        "session_id": app.session_state["airport_session_id"],
    }
    report = CompositeReportV2.model_validate(payload)
    repository = ReportRepository(Storage(tmp_path / "development.sqlite3"))
    repository.save_report(report, identity)
    app.session_state["active_report_id"] = report.report_id
    app.run()
    assert not app.exception
    assert not app.error
    assert any(heading.value == "1. Count flights" for heading in app.subheader)
    assert len(app.get("download_button")) >= 2
    assert next(checkbox for checkbox in app.checkbox if "Refine" in checkbox.label).disabled
    next(button for button in app.button if button.label == "Delete private report").click().run()
    assert not app.exception
    assert repository.list_reports(identity) == []
