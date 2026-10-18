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
    monkeypatch.setenv("AIRPORT_HOSTED_PRODUCT_IMPROVEMENT_TERMS", "unknown")
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

    grant = next(toggle for toggle in app.toggle if toggle.label == "Enable FAQ examples reuse")
    assert not grant.disabled
    assert grant.value is True
    assert not app.error
    assert all(toggle.value for toggle in app.toggle if toggle.label.startswith("Enable "))
    assert next(
        toggle for toggle in app.toggle if toggle.label == "Use V2 summary exploration"
    ).value
    next(toggle for toggle in app.toggle if toggle.label == "Use V2 summary exploration").set_value(
        False
    ).run()

    identity = resolve_development_identity(production=False, server_address="127.0.0.1")
    report = make_report(
        "development-faq", identity.analyst_id, app.session_state["airport_session_id"]
    )
    repository = ReportRepository(Storage(tmp_path / "development.sqlite3"))
    repository.save_report(report, identity)
    app.session_state["active_report_id"] = report.report_id
    monkeypatch.setattr(product_app, "render_report", lambda *args, **kwargs: None)
    app.run()
    next(button for button in app.button if button.label == "Create shared copy").click().run()
    assert not app.error
    assert len(repository.list_shared_artifacts("faq")) == 1

    app.run()
    assert any(report.narrative == text.value for text in app.markdown)
    next(button for button in app.button if button.label == "Use this FAQ question").click().run()
    assert app.text_area[0].value == report.question
    generator = Mock()
    generator.generate.return_value = SimpleNamespace(
        status="needs_clarification", report=None, message="Which airport?"
    )
    monkeypatch.setattr(product_app, "ReportGenerator", lambda *args: generator)
    next(button for button in app.button if button.label == "Generate report").click().run()
    assert not app.error
    assert generator.generate.call_args.args[0] == report.question
    assert app.text_area[0].value == report.question
    app.text_area[0].input("How many flights departed from JFK in 2013?")
    next(button for button in app.button if button.label == "Generate report").click().run()
    assert generator.generate.call_args.args[0] == "How many flights departed from JFK in 2013?"
    next(button for button in app.button if button.label == "Use this FAQ question").click().run()
    next(button for button in app.button if button.label == "Generate report").click().run()
    assert generator.generate.call_args.args[0] == report.question

    next(toggle for toggle in app.toggle if toggle.label == "Enable FAQ examples reuse").set_value(
        False
    ).run()
    assert not app.error
    assert len(repository.list_shared_artifacts("faq")) == 1
    app.run()
    assert not next(
        toggle for toggle in app.toggle if toggle.label == "Enable FAQ examples reuse"
    ).value


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
    assert not next(button for button in app.button if button.label == "Generate report").disabled
    acknowledgement = next(
        toggle
        for toggle in app.toggle
        if toggle.label == "I understand and acknowledge hosted processing"
    )
    assert acknowledgement.value is True
    acknowledgement.set_value(False).run()
    assert next(button for button in app.button if button.label == "Generate report").disabled
    app.radio[0].set_value("ollama").run()
    app.radio[0].set_value("openai").run()
    assert next(button for button in app.button if button.label == "Generate report").disabled


def test_groq_is_explicitly_selectable_in_development(monkeypatch, tmp_path) -> None:
    from airport_analytics.analytics.provider_policy import ProviderDescriptor

    _configure_development(monkeypatch, tmp_path, "127.0.0.1")
    monkeypatch.setenv("AIRPORT_OPENAI_API_KEY", "test-only")
    monkeypatch.setenv("AIRPORT_OPENAI_MODEL_NAME", "openai/gpt-oss-20b")
    monkeypatch.setenv("AIRPORT_OPENAI_BASE_URL", "https://api.groq.com/openai/v1")
    monkeypatch.setenv("AIRPORT_HOSTED_FREE_PLAN", "true")
    monkeypatch.setattr(product_app, "_executor", lambda *args: SimpleNamespace())
    selected_settings = []

    def client(settings, **kwargs):
        selected_settings.append(settings)
        return SimpleNamespace(
            provider=ProviderDescriptor(settings.model_provider, settings.model_name, "unknown")
        )

    monkeypatch.setattr(product_app, "LangChainPlanClient", client)
    app = AppTest.from_function(_development_app).run()
    app.button[0].click().run()
    app.radio[0].set_value("groq").run()
    assert not app.error
    assert any("api.groq.com" in warning.value for warning in app.warning)
    assert any("provider limits only" in caption.value for caption in app.caption)
    assert not next(button for button in app.button if button.label == "Generate report").disabled
    selector = next(item for item in app.selectbox if item.label == "Groq model")
    assert selector.value == "openai/gpt-oss-20b"
    assert selector.options == ["openai/gpt-oss-20b", "openai/gpt-oss-120b"]
    selector.set_value("openai/gpt-oss-120b").run()
    assert not app.exception
    assert not app.error
    assert selected_settings[-1].model_name == "openai/gpt-oss-120b"
    assert selected_settings[-1].hosted_free_plan is True
    assert any(
        "openai/gpt-oss-120b" in warning.value and "api.groq.com" in warning.value
        for warning in app.warning
    )
    next(
        toggle
        for toggle in app.toggle
        if toggle.label == "I understand and acknowledge hosted processing"
    ).set_value(False).run()
    assert next(button for button in app.button if button.label == "Generate report").disabled
    app.radio[0].set_value("ollama").run()
    app.radio[0].set_value("groq").run()
    assert next(item for item in app.selectbox if item.label == "Groq model").value == (
        "openai/gpt-oss-120b"
    )


def test_selecting_saved_report_immediately_enables_correct_follow_up(
    monkeypatch, tmp_path
) -> None:
    from airport_analytics.auth import resolve_development_identity
    from airport_analytics.history.repository import ReportRepository
    from airport_analytics.storage import Storage
    from tests.factories import make_report

    _configure_development(monkeypatch, tmp_path, "127.0.0.1")
    monkeypatch.setattr(product_app, "_executor", lambda *args: SimpleNamespace())
    monkeypatch.setattr(product_app, "LangChainPlanClient", lambda *args, **kwargs: Mock())
    monkeypatch.setattr(product_app, "render_report", lambda *args, **kwargs: None)
    identity = resolve_development_identity(production=False, server_address="127.0.0.1")
    repository = ReportRepository(Storage(tmp_path / "development.sqlite3"))
    first = make_report("first", identity.analyst_id, "past-session")
    second = make_report("second", identity.analyst_id, "past-session")
    repository.save_report(first, identity)
    repository.save_report(second, identity)
    app = AppTest.from_function(_development_app).run()
    app.button[0].click().run()
    next(toggle for toggle in app.toggle if toggle.label == "Use V2 summary exploration").set_value(
        False
    ).run()
    assert app.checkbox[0].disabled
    history = next(
        select for select in app.selectbox if select.label == "Open one of your saved reports"
    )
    history.set_value(first.report_id).run()
    assert not app.checkbox[0].disabled
    next(
        select for select in app.selectbox if select.label == "Open one of your saved reports"
    ).set_value(second.report_id).run()
    assert not app.checkbox[0].disabled
    generator = Mock()
    generator.generate.return_value = SimpleNamespace(
        status="needs_clarification", report=None, message="Which airport?"
    )
    monkeypatch.setattr(product_app, "ReportGenerator", lambda *args: generator)
    app.checkbox[0].check()
    app.text_area[0].input("Only EWR")
    next(button for button in app.button if button.label == "Generate report").click().run()
    assert not app.error
    assert (
        generator.generate.call_args.kwargs["follow_up_context"].previous_question
        == second.question
    )
    assert (
        generator.generate.call_args.kwargs["follow_up_context"].previous_plan
        == second.analysis_plan
    )


@pytest.mark.parametrize(
    ("reuse_enabled", "production", "retention_approved", "expected"),
    [
        (True, False, False, True),
        (False, False, False, False),
        (True, True, False, False),
        (True, True, True, True),
    ],
)
def test_normal_sign_in_defaults_respect_deployment_reuse_policy(
    monkeypatch, tmp_path, reuse_enabled, production, retention_approved, expected
) -> None:
    from airport_analytics.auth import resolve_development_identity
    from airport_analytics.consent.repository import ConsentRepository
    from airport_analytics.storage import Storage

    _configure_development(monkeypatch, tmp_path, "127.0.0.1")
    monkeypatch.setenv("AIRPORT_DEV_SIGN_IN_ENABLED", "false")
    monkeypatch.setenv("AIRPORT_PRODUCTION", str(production).lower())
    monkeypatch.setenv("AIRPORT_SHARED_REUSE_ENABLED", str(reuse_enabled).lower())
    monkeypatch.setenv("AIRPORT_RETENTION_POLICY_APPROVED", str(retention_approved).lower())
    identity = resolve_development_identity(production=False, server_address="127.0.0.1")
    monkeypatch.setattr(product_app, "_identity", lambda: identity)
    monkeypatch.setattr(product_app, "_executor", lambda *args: SimpleNamespace())
    monkeypatch.setattr(product_app, "LangChainPlanClient", lambda *args, **kwargs: Mock())
    app = AppTest.from_function(_development_app).run()
    assert not app.exception
    assert not app.error
    reuse_toggles = [toggle for toggle in app.toggle if toggle.label.startswith("Enable ")]
    assert len(reuse_toggles) == 2
    assert all(toggle.value is expected for toggle in reuse_toggles)
    assert all(toggle.disabled is not expected for toggle in reuse_toggles)
    events = ConsentRepository(Storage(tmp_path / "development.sqlite3"))
    session_id = app.session_state["airport_session_id"]
    grant = events.latest_event(identity, session_id, "faq")
    assert (grant is not None) is expected
    if grant is not None:
        assert grant.notice_version == "v2-default-on"
    app.run()
    assert not app.exception
    assert events.latest_event(identity, session_id, "faq") == grant


def _tracing_test_app():
    from airport_analytics.observability.tracing import TracingConfig
    from app import _tracing_disclosure

    _tracing_disclosure(TracingConfig(enabled=True, maximum_charge_per_trace_usd=None))


def test_tracing_acknowledgement_defaults_on_and_can_be_disabled() -> None:
    app = AppTest.from_function(_tracing_test_app).run()
    assert not app.exception
    assert app.toggle[0].value is True
    assert app.session_state[product_app.TRACING_ACK_KEY] is True
    app.toggle[0].set_value(False).run()
    app.run()
    assert app.session_state[product_app.TRACING_ACK_KEY] is False
