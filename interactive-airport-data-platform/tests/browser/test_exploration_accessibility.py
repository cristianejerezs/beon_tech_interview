from tests.browser.test_exploration_summary_ui import open_app


def test_separate_app_sessions_do_not_share_pending_or_export_state(monkeypatch, tmp_path):
    from tests.integration.test_exploration_clarification import ClarificationClient

    first, first_model, executor = open_app(monkeypatch, tmp_path)
    try:
        first_model.payload = ClarificationClient().proposal.model_dump(mode="json")
        first.text_area[0].input("Clarify this airport")
        next(button for button in first.button if button.label == "Generate report").click().run()
        assert any(item.value == "Pending analysis" for item in first.subheader)
        assert "exploration_request" in first.session_state
        second, _, second_executor = open_app(monkeypatch, tmp_path)
        try:
            assert "exploration_request" not in second.session_state
            assert not any(item.value == "Pending analysis" for item in second.subheader)
        finally:
            second_executor.close()
    finally:
        executor.close()
