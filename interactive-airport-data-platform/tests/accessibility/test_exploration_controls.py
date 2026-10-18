from tests.browser.test_exploration_browsing_ui import listing_app


def test_listing_controls_are_labelled_and_population_status_is_text(monkeypatch, tmp_path):
    app, model, executor = listing_app(monkeypatch, tmp_path)
    try:
        for controls in (app.button, app.selectbox, app.number_input, app.checkbox, app.text_area):
            assert all(widget.label.strip() for widget in controls)
        assert any("exact total" in item.value for item in app.caption)
        assert any("Page 1" in item.value for item in app.caption)
        assert any("saved preview" in item.label.lower() for item in app.get("download_button"))
        assert model.calls == 1
    finally:
        executor.close()
