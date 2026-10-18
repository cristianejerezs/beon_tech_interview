import os

import pytest

from airport_analytics import config
from airport_analytics.errors import PdfRuntimeUnavailableError


@pytest.hookimpl(wrapper=True)
def pytest_runtest_call(item):
    """Report missing native PDF libraries as an explicit skip, not a product failure."""
    try:
        return (yield)
    except PdfRuntimeUnavailableError as exc:
        pytest.skip(f"Tagged PDF runtime (Pango/WeasyPrint) unavailable: {exc}")


@pytest.fixture(autouse=True)
def isolate_from_local_environment(monkeypatch):
    """Keep a developer's .env and AIRPORT_* shell settings out of tests.

    Settings.from_env() calls load_dotenv, which copies .env into os.environ for the whole
    process; tests must only see the variables they set themselves.
    """
    for key in list(os.environ):
        if key.startswith("AIRPORT_"):
            monkeypatch.delenv(key)
    monkeypatch.setattr(config, "load_dotenv", lambda *args, **kwargs: False)
