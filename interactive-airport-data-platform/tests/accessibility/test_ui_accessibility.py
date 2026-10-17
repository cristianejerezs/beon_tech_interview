from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from streamlit.testing.v1 import AppTest

import app as product_app
from tests.browser.test_app_authentication import _configure_development, _development_app


def test_sign_in_control_is_text_labeled_and_app_has_no_accessibility_errors() -> None:
    app = AppTest.from_file(Path(__file__).resolve().parents[2] / "app.py").run()

    assert not app.exception
    assert [button.label for button in app.button] == ["Sign in"]
    assert [title.value for title in app.title] == ["Interactive Airport Data Platform"]


def test_signed_in_controls_have_labels_and_status_has_text(monkeypatch, tmp_path):
    _configure_development(monkeypatch, tmp_path, "127.0.0.1")
    monkeypatch.setattr(product_app, "_executor", lambda *args: SimpleNamespace())
    monkeypatch.setattr(product_app, "LangChainPlanClient", lambda *args, **kwargs: Mock())
    app = AppTest.from_function(_development_app).run()
    app.button[0].click().run()
    assert not app.exception
    for controls in (app.button, app.toggle, app.text_area, app.selectbox, app.radio, app.checkbox):
        assert all(control.label.strip() for control in controls)
    assert any("Session reuse choices default to on" in text.value for text in app.markdown)
    assert any("Refinement becomes available" in text.value for text in app.caption)
