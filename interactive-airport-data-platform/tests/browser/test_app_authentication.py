from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from streamlit.testing.v1 import AppTest

import app as product_app


def test_unauthenticated_analyst_is_prompted_to_sign_in() -> None:
    app = AppTest.from_file(Path(__file__).resolve().parents[2] / "app.py").run()

    assert not app.exception
    assert [button.label for button in app.button] == ["Sign in"]


def _development_app():
    from app import main

    main()


def _configure_development(monkeypatch, tmp_path, address: str) -> None:
    monkeypatch.setenv("AIRPORT_DEV_SIGN_IN_ENABLED", "true")
    monkeypatch.setenv("AIRPORT_PRODUCTION", "false")
    monkeypatch.setenv("AIRPORT_MODEL_PROVIDER", "ollama")
    monkeypatch.setenv("AIRPORT_DATABASE_PATH", str(tmp_path / "development.sqlite3"))
    monkeypatch.setenv("AIRPORT_SHARED_REUSE_ENABLED", "false")
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    original_get_option = product_app.st.get_option
    monkeypatch.setattr(
        product_app.st,
        "get_option",
        lambda name: address if name == "server.address" else original_get_option(name),
    )


def test_local_developer_can_sign_in_and_out_without_oidc(monkeypatch, tmp_path) -> None:
    _configure_development(monkeypatch, tmp_path, "127.0.0.1")
    monkeypatch.setattr(product_app, "_executor", lambda *args: SimpleNamespace())
    monkeypatch.setattr(product_app, "LangChainPlanClient", lambda *args, **kwargs: Mock())
    oidc_login = Mock(side_effect=AssertionError("OIDC must not run during development sign-in"))
    oidc_logout = Mock(side_effect=AssertionError("OIDC must not run during development sign-out"))
    monkeypatch.setattr(product_app.st, "login", oidc_login)
    monkeypatch.setattr(product_app.st, "logout", oidc_logout)

    app = AppTest.from_function(_development_app).run()
    assert not app.exception
    assert any("not real authentication" in warning.value for warning in app.warning)
    app.button[0].click().run()
    assert not app.exception
    assert [area.label for area in app.text_area] == ["Question"]
    assert app.session_state["airport_development_signed_in"] is True
    app.session_state["airport_provider_disclosures"] = {"test": ("model", "terms")}
    next(button for button in app.button if button.label == "Sign out").click().run()
    assert not app.exception
    assert [button.label for button in app.button] == ["Sign in as local developer"]
    assert "airport_provider_disclosures" not in app.session_state
    oidc_login.assert_not_called()
    oidc_logout.assert_not_called()


@pytest.mark.parametrize("address", ["", "0.0.0.0", "::", "192.168.1.10"])
def test_development_ui_blocks_non_loopback_servers(monkeypatch, tmp_path, address) -> None:
    _configure_development(monkeypatch, tmp_path, address)
    app = AppTest.from_function(_development_app).run()
    assert not app.exception
    assert not app.button
    assert not app.text_area
    assert "requires AIRPORT_PRODUCTION=false" in app.error[0].value


def test_development_reuse_opt_in_shared_faq_and_question_selection(monkeypatch, tmp_path) -> None:
    from airport_analytics.auth import resolve_development_identity
    from airport_analytics.history.repository import ReportRepository
    from airport_analytics.storage import Storage
    from tests.factories import make_report

    _configure_development(monkeypatch, tmp_path, "127.0.0.1")
    monkeypatch.setattr(product_app, "_executor", lambda *args: SimpleNamespace())
    monkeypatch.setattr(product_app, "LangChainPlanClient", lambda *args, **kwargs: Mock())
    app = AppTest.from_function(_development_app).run()
    app.button[0].click().run()

    grant = next(button for button in app.button if button.label == "Enable FAQ examples reuse")
    assert not grant.disabled
    grant.click().run()
    assert not app.error
    assert any(button.label == "Withdraw FAQ examples consent" for button in app.button)

    identity = resolve_development_identity(production=False, server_address="127.0.0.1")
    report = make_report(
        "development-faq", identity.analyst_id, app.session_state["airport_session_id"]
    )
    repository = ReportRepository(Storage(tmp_path / "development.sqlite3"))
    repository.save_report(report, identity)
    app.session_state["active_report_id"] = report.report_id
    monkeypatch.setattr(product_app, "render_report", lambda *args: None)
    app.run()
    next(button for button in app.button if button.label == "Create shared copy").click().run()
    assert not app.error
    assert len(repository.list_shared_artifacts("faq")) == 1

    app.run()
    assert any(report.narrative == text.value for text in app.markdown)
    next(button for button in app.button if button.label == "Use this FAQ question").click().run()
    assert app.text_area[0].value == report.question

    next(
        button for button in app.button if button.label == "Withdraw FAQ examples consent"
    ).click().run()
    assert not app.error
    assert len(repository.list_shared_artifacts("faq")) == 1


def test_configured_remote_model_available_with_disclosure_in_development(
    monkeypatch, tmp_path
) -> None:
    from airport_analytics.analytics.provider_policy import ProviderDescriptor

    _configure_development(monkeypatch, tmp_path, "127.0.0.1")
    monkeypatch.setenv("AIRPORT_OPENAI_API_KEY", "test-only")
    monkeypatch.setenv("AIRPORT_OPENAI_MODEL_NAME", "test-hosted-model")
    monkeypatch.setenv("AIRPORT_OPENAI_BASE_URL", "https://provider.example/v1")
    monkeypatch.setattr(product_app, "_executor", lambda *args: SimpleNamespace())
    monkeypatch.setattr(
        product_app,
        "LangChainPlanClient",
        lambda *args, **kwargs: SimpleNamespace(
            provider=ProviderDescriptor("openai", "test-hosted-model", "unknown")
        ),
    )
    app = AppTest.from_function(_development_app).run()
    app.button[0].click().run()
    app.radio[0].set_value("openai").run()
    assert not app.error
    assert any("https://provider.example/v1" in notice.value for notice in app.warning)
    assert next(button for button in app.button if button.label == "Generate report").disabled
    next(
        button
        for button in app.button
        if button.label == "I understand and acknowledge hosted processing"
    ).click().run()
    assert not next(button for button in app.button if button.label == "Generate report").disabled
