import shutil
from pathlib import Path

import pytest

from airport_analytics.analytics.execution import DuckDBExecutor
from airport_analytics.data.loader import DatasetLoader
from airport_analytics.errors import DatasetUnavailableError

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "exploration"


def test_semantic_identity_includes_missing_declaration_and_definition_versions(tmp_path):
    declaration = tmp_path / "coverage.json"
    with DuckDBExecutor(str(FIXTURES), coverage_path=declaration) as executor:
        loader = DatasetLoader(FIXTURES)
        initial = executor.context
        assert initial.coverage_status == "missing"
        assert initial.coverage_sha256 is None
        assert loader.semantic_context(executor.manifest, coverage_path=declaration) == initial
        for changes in [
            {"catalog_version": "next"},
            {"alias_version": "next"},
            {"rules_version": "next"},
            {"unit_provenance": {"weather": "reviewed-v2"}},
        ]:
            assert (
                loader.semantic_context(
                    executor.manifest, coverage_path=declaration, **changes
                ).context_id
                != initial.context_id
            )
        executor.require_current_binding(executor.manifest.snapshot_id, initial.context_id)
        declaration.write_text('{"asserted": "complete"}', encoding="utf-8")
        changed = loader.semantic_context(executor.manifest, coverage_path=declaration)
        assert changed.coverage_status == "unverified"
        assert changed.context_id != initial.context_id
        with pytest.raises(DatasetUnavailableError, match="context"):
            executor.require_current_binding(executor.manifest.snapshot_id, initial.context_id)
        assert executor.context == initial


def test_source_change_invalidates_continuation_without_replacing_saved_manifest(tmp_path):
    copied = tmp_path / "source"
    shutil.copytree(FIXTURES, copied)
    with DuckDBExecutor(str(copied)) as executor:
        snapshot = executor.manifest.snapshot_id
        context = executor.context.context_id
        source = copied / "nyc_flights_fixed.csv"
        source.write_text(
            source.read_text(encoding="utf-8").replace("BOS", "XXX"), encoding="utf-8"
        )
        with pytest.raises(DatasetUnavailableError, match="source"):
            executor.require_current_binding(snapshot, context)
        assert executor.manifest.snapshot_id == snapshot
        assert executor.context.context_id == context


def test_stale_binding_cannot_restart_against_cached_tables():
    with DuckDBExecutor(str(FIXTURES)) as executor:
        for snapshot, context in [
            ("c" * 64, executor.context.context_id),
            (executor.manifest.snapshot_id, "d" * 64),
        ]:
            with pytest.raises(DatasetUnavailableError):
                executor.require_current_binding(snapshot, context)
