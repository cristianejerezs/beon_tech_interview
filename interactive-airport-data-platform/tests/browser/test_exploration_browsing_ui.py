from airport_analytics.errors import DatasetUnavailableError
from tests.browser.test_exploration_summary_ui import open_app


def listing_app(monkeypatch, tmp_path):
    app, model, executor = open_app(monkeypatch, tmp_path)
    model.payload["sections"][0].update(
        family="individual_records",
        operation_id="flight_records",
        measure_ids=[],
        population="flights",
    )
    app.text_area[0].input("List flights")
    next(button for button in app.button if button.label == "Generate report").click().run()
    assert not app.exception
    assert not app.error
    return app, model, executor


def test_listing_pages_exports_and_v1_history_never_call_model(monkeypatch, tmp_path):
    app, model, executor = listing_app(monkeypatch, tmp_path)
    try:
        assert any("9" in caption.value and "total" in caption.value for caption in app.caption)
        next(widget for widget in app.selectbox if widget.label == "Rows per page").select(25)
        next(widget for widget in app.number_input if widget.label == "Page number").set_value(99)
        next(button for button in app.button if button.label == "Load listing page").click().run()
        assert not app.error
        assert any("page one" in info.value for info in app.info)
        next(
            widget for widget in app.number_input if widget.label == "Listing export rows"
        ).set_value(2)
        app.run()
        prepare = next(button for button in app.button if button.label == "Prepare listing CSV")
        assert prepare.disabled
        next(widget for widget in app.checkbox if "confirm a partial" in widget.label).check().run()
        next(button for button in app.button if button.label == "Prepare listing CSV").click().run()
        assert not app.error
        assert any("2 of 9" in button.label for button in app.get("download_button"))
        assert model.calls == 1
        import app as product_app
        from airport_analytics.errors import QueryExecutionError

        def export_failure(*args, **kwargs):
            raise QueryExecutionError()

        with monkeypatch.context() as export_patch:
            export_patch.setattr(product_app, "export_listing_csv", export_failure)
            next(
                button for button in app.button if button.label == "Prepare listing CSV"
            ).click().run()
            assert app.error
            assert not any("2 of 9" in button.label for button in app.get("download_button"))
        next(
            widget for widget in app.toggle if widget.label == "Use V2 summary exploration"
        ).set_value(False).run()
        assert any(button.label == "Load listing page" for button in app.button)
        assert model.calls == 1

        def unavailable(*args):
            raise DatasetUnavailableError()

        monkeypatch.setattr(executor, "require_current_binding", unavailable)
        app.run()
        assert not any(button.label == "Load listing page" for button in app.button)
        assert any("saved preview" in button.label.lower() for button in app.get("download_button"))
        next(
            button for button in app.button if button.label == "Restart listing on current source"
        ).click().run()
        assert app.text_area[0].value == "List flights"
        assert model.calls == 1
    finally:
        executor.close()


def test_missing_current_sources_still_open_saved_listing_preview(monkeypatch, tmp_path):
    app, model, executor = listing_app(monkeypatch, tmp_path)
    try:
        import app as product_app

        def unavailable(*args):
            raise DatasetUnavailableError()

        monkeypatch.setattr(product_app, "_executor", unavailable)
        app.run()
        assert not app.exception
        assert app.error
        assert any("saved preview" in button.label.lower() for button in app.get("download_button"))
        assert not any(button.label == "Prepare listing CSV" for button in app.button)
        assert model.calls == 1
    finally:
        executor.close()
