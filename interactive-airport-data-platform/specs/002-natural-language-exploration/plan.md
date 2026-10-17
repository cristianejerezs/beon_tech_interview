# Implementation Plan: Natural-Language Exploration and Grouped Analysis

**Branch**: Actual Git branch `main`; feature identifier `002-natural-language-exploration` (the setup script's feature label is not evidence of a checked-out branch).
**Date**: 2026-10-17
**Spec**: [spec.md](spec.md)
**Status**: Phase 0 research and Phase 1 design complete; implementation and acceptance not performed.

## Summary

Extend the existing single-host application with reusable ordinary-language interpretation across ten request families, one to four independently scoped sections per report, bounded clarification/correction, listing pages, two-stage calculations and the ten AQ analyses. Models remain untrusted intent translators; local code resolves entities, validates catalog combinations, computes results and produces all numbers.

Use a versioned V2 interpretation envelope, application-owned section plans and evidence contracts rather than hardcoded question matching. Extend existing modules and add only focused interpretation/state, entity-resolution, coverage and multi-stage compilation helpers. Keep V1 saved reports readable. Feature 002 supplies verified, versioned evidence to [003](../003-visual-reporting/spec.md); actual automatic chart selection, tagged PDF rendering and visual accessibility implementation remain 003 work. Integrated release requires both specifications' gates, all nine E2E cases and ten AQ cases.

## Technical Context

**Language/Version**: Python 3.12; existing manifest requires `>=3.12,<3.13`.
**Primary Dependencies**: Existing Streamlit, DuckDB, Pydantic, jsonschema, LangChain/OpenAI-compatible and Ollama integrations, Plotly and ReportLab. No new runtime dependency planned for 002. Provider SDK schema subsets remain compatibility-tested projections of an authoritative local contract.
**Observed environment**: DuckDB 1.5.6, Streamlit 1.66.0, Pydantic 2.14.1, langchain-openai 1.7.2, langchain-ollama 1.1.0, ReportLab 5.0.1, jsonschema 4.26.0. These are observations, not a new lockfile.
**Storage**: Existing SQLite report JSON, consent audit and usage ledger; V2 payload discriminator, not a parallel report database. Session-only request drafts/clarifications. Immutable loaded DuckDB snapshot tables. Optional local validated snapshot coverage declaration.
**Testing**: pytest, Streamlit AppTest, Ruff, jsonschema; independent Python standard-library CSV/set/Decimal/statistics/math oracles, real browser/screen-reader evidence where applicable. Mocked provider tests are necessary but never substitute for live model acceptance.
**Target Platform**: Existing single-host Streamlit deployment; development on Windows. Preserve approved loopback-only developer access and production OIDC/resource checks.
**Project Type**: Existing Python package plus Streamlit entry point; no new service, queue, autonomous agent or public HTTP API.
**Performance Goals**: Measure source validation, interpretation, analytical execution, browser/chart-ready and exports separately with cold/warm conditions. No new numerical latency SLA. Preserve configured query timeouts and bounded evidence; never fetch a complete population to Python merely to truncate it.
**Constraints**: USD 10 shared UTC-month paid inference/tracing cap, free quotas, uncertainty reconciliation, no retries/fallback without explicit authorized action; max 2,000 trimmed Unicode code points per submitted question/clarification; one to four sections; three answered clarification turns/section; at most two grouping roles; 500 result groups/section; 25/50/100/500 page sizes; 10,000 listing export rows/file across selected sections; 100 bins; 5,000 scatter pairs or full density evidence. Existing 500-route evidence bound remains disclosed.
**Scale/Scope**: Supplied snapshot baseline: 277,977 flight records, 1,458 airport references, 16 airline references, 3,322 plane references and 26,112 weather records; NYC origins and 2013 historical flight dates. Revalidate counts/hash at run time; these are not completeness assertions.

## Constitution Check

Gates apply before research and again after design.

| Principle / constraint | Pre-research | Post-design evidence |
|------------------------|--------------|----------------------|
| I: Defensible correctness | Pass by design | Typed definitions preserve units, weighting, denominator basis, missingness, period and per-section grain; two-stage metrics operate before limits |
| II: Grain and integrity | Pass by design | Validated flight IDs/reference keys; origin-hour collapse before weather correlation; coverage declaration cannot be inferred from observed rows |
| III: Reproducibility | Pass by design | Snapshot/coverage/catalog/alias/rule versions, parameterized owned queries, immutable saved evidence, independent oracle and frozen corpus |
| IV: Honest communication | Pass by design | Unknown/partial/zero distinct; provisional seat rankings; association not causation; 003 consumes explicit evidence, no fabricated charts or partial PDF success |
| V: Question-driven explainability | Pass by design | Ten reusable families and AQ definitions; names, paraphrases, clarification and corrections rather than sentence whitelist |
| Privacy, ownership, budget | Pass by design | Existing owner repository/consent/usage gates retained; no source rows or private report content in model prompts or telemetry; safe incomplete-report flow |
| Workflow/evidence gates | Pass by design | No code/test/provider/analyst success claimed; phase-specific contracts and release prerequisites documented below |

No constitutional exception is introduced. The previously approved default-on session choices and guarded development identity remain unchanged; they do not establish retention approval or legal consent.

## Project Structure

### Documentation (this feature)

```text
specs\002-natural-language-exploration\
  spec.md
  plan.md
  research.md
  data-model.md
  quickstart.md
  contracts\
    interpretation.md
    evidence-and-persistence.md
    coverage.schema.json
  checklists\requirements.md
```

`tasks.md` is a subsequent `/speckit-tasks` deliverable, not generated in this phase. A custom reviewer checklist is also still pending; its earlier command stopped before generation because this plan did not exist.

### Source Code (existing paths and proposed additions)

```text
app.py                                      # Session state, section clarification/correction and report UI
src\airport_analytics\
  models.py                                 # V1 compatibility + typed V2 domain/evidence
  storage.py                                # Existing owner report rows; atomic preference updates if needed
  analytics\
    model_client.py                         # Versioned output schema and bounded intent-only context
    plan_schema.py                          # Authoritative V2 schema/catalog validation
    interpretation.py                       # NEW: resolve defaults, corrections and section plans
    request_state.py                        # NEW: pure session/request/section transitions
    entity_resolution.py                    # NEW: versioned names/aliases and candidate policy
    follow_up.py                            # Explicit typed scope edits; preserve V1 behavior
    query_compiler.py                       # Existing application-owned predicates/joins and aggregates
    multi_stage.py                          # NEW: owned date/bin/pair/multi-stage compilation
    execution.py                            # Snapshot-pinned section execution, pages, bounds and timeout
    metrics.py                              # Definitions, coverage, exact counts and completeness
    evaluation.py                           # V2 suites alongside original 12-question regression
  data\
    catalog.py                              # Versioned operations/dimensions/units/additivity
    coverage.py                             # NEW: declaration validation and day eligibility
    loader.py                               # Snapshot/materialized views + declaration association
    validation.py                           # Existing structure/join checks; needed new measurement guards
  reports\
    generation.py                           # V2 section orchestration, deterministic narratives
    rendering.py                            # V1/V2 table/interpretation adapter; visuals implemented in 003
    export.py                               # Scoped section CSV/table document adapter; chart PDF in 003
  history\repository.py                     # V1/V2 payload dispatch; one composite = one retention slot
tests\                                      # Extend existing unit/integration/browser/accessibility suites
  fixtures\exploration\                     # Future development/frozen corpus and expected evidence
```

**Structure Decision**: Keep one package and the existing storage/provider abstractions. Add helpers only for independently testable boundaries; do not build a generic arbitrary query language, separate backend, multi-agent runtime, durable conversation store or export job service.

## Phase 0: Research Decisions

Resolved in [research.md](research.md): V2 intents and provider projection, pure request state, deterministic entity matching, application-owned query stages, honest coverage, hour-weighted weather correlation, bounded evidence, V1/V2 persistence and evaluation. All implementation design choices are selected; source coverage and transformed weather-unit provenance are operational/data prerequisites, not silently presumed facts.

## Phase 1: Design and Contracts

- [data-model.md](data-model.md) defines domain fields, invariants and state transitions.
- [interpretation contract](contracts/interpretation.md) defines model/app boundaries, canonical operation IDs, clarification and section planning.
- [evidence/persistence contract](contracts/evidence-and-persistence.md) defines typed numerical evidence, pages, export allocation, legacy compatibility, FAQ reuse and the 003 handoff.
- [coverage schema](contracts/coverage.schema.json) specifies declaration structure; semantic provenance checks remain mandatory and cannot be replaced by schema validity.
- [quickstart.md](quickstart.md) distinguishes current runnable baseline checks from future validation interfaces and external release evidence.

### Implementation sequencing for task generation

1. Establish red tests for V2 structural/semantic contracts, state transitions, legacy report reads and coverage failure behavior.
2. Add catalog/types/provider schema projections and deterministic entity/default resolution; preserve existing no-retry and budget adapters.
3. Implement coverage/calendar eligibility, query stages and independent numeric oracle cases for each new operation before UI wiring.
4. Add stable snapshot-bound listing/count/export operations and compound evidence bounds.
5. Orchestrate all-section readiness, sequential snapshot-pinned execution, safe partial outcomes and acknowledged persistence.
6. Wire native labelled UI controls, FAQs/refinement/history/CSV adapters and legacy compatibility across every report surface.
7. Add held-out evaluation and actual acceptance protocols; hand 003 the common evidence contract. Do not claim integrated release until its visual/PDF/accessibility gates pass too.

These are design workstreams, not completed tasks. Shared files must be changed serially; operations may have independent tests, but all sections in a submitted composite use one validated snapshot.

## Release Readiness and Dependencies

| Dependency | Current evidence / gate |
|------------|------------------------|
| Existing app baseline | Repository inspected; earlier suite results are historical, not rerun as part of this documentation phase |
| Coverage declaration | None accompanies the five source CSVs; unknown-day/calendar-average behavior is mandatory until supported declaration exists |
| Weather units | Upstream documents F, mph, inches, miles; validate local transformed-source provenance before AQ-06 coefficient labels/acceptance |
| Provider V2 structured output | Design only; real local/hosted candidates require explicit authorized live testing |
| Human gold review | Two independent reviewers/adjudication required before frozen corpus acceptance; not supplied by generated examples |
| 003 visual reporting | Separate feature plan/implementation required for automatic graphs, tagged PDF, screen-reader and visual review |
| Retention/analyst/live gates | Existing 001 owner approval and real external evidence gates remain open |

After Phase 1, all constitution gates pass as design requirements. No production approval, numerical runtime result or integrated acceptance is asserted.

## Complexity Tracking

No constitutional violations requiring justification. Multi-stage queries, V2 envelopes and composite reports are necessary for the approved requirements; simpler single-plan/table-only behavior cannot meet them.
