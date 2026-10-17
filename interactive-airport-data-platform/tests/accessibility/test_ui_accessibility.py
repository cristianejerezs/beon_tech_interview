from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_sign_in_control_is_text_labeled_and_app_has_no_accessibility_errors() -> None:
    app = AppTest.from_file(Path(__file__).resolve().parents[2] / "app.py").run()

    assert not app.exception
    assert [button.label for button in app.button] == ["Sign in"]
    assert [title.value for title in app.title] == ["Interactive Airport Data Platform"]
