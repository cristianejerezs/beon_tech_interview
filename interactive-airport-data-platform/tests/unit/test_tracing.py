from airport_analytics.observability.tracing import TracingConfig


def test_tracing_is_disabled_by_default(monkeypatch) -> None:
    for key in (
        "LANGSMITH_TRACING",
        "LANGSMITH_API_KEY",
        "AIRPORT_LANGSMITH_DISCLOSURE_ENABLED",
    ):
        monkeypatch.delenv(key, raising=False)
    assert not TracingConfig.from_env().enabled


def test_tracing_requires_explicit_operator_configuration_and_disclosure(monkeypatch) -> None:
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "test-only")
    monkeypatch.setenv("AIRPORT_LANGSMITH_MAX_TRACE_CHARGE_USD", "0.01")
    monkeypatch.delenv("AIRPORT_LANGSMITH_DISCLOSURE_ENABLED", raising=False)
    assert not TracingConfig.from_env().enabled

    monkeypatch.setenv("AIRPORT_LANGSMITH_DISCLOSURE_ENABLED", "true")
    assert TracingConfig.from_env().enabled


def test_tracing_cannot_start_without_credentials(monkeypatch) -> None:
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("AIRPORT_LANGSMITH_DISCLOSURE_ENABLED", "true")
    monkeypatch.setenv("AIRPORT_LANGSMITH_MAX_TRACE_CHARGE_USD", "0.01")
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    try:
        TracingConfig.from_env()
    except ValueError as error:
        assert "LANGSMITH_API_KEY" in str(error)
    else:
        raise AssertionError("Expected explicit missing-key error.")
