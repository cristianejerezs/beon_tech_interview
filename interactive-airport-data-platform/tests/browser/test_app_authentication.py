from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_unauthenticated_analyst_is_prompted_to_sign_in() -> None:
    app = AppTest.from_file(Path(__file__).resolve().parents[2] / "app.py").run()

    assert not app.exception
    assert [button.label for button in app.button] == ["Sign in"]
