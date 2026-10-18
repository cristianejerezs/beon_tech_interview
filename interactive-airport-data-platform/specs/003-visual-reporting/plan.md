# Implementation Plan: Automatic Visual Reporting

**Feature**: `003-visual-reporting` | **Date**: 2026-10-18  
**Git branch**: `main` (unchanged; no feature branch created)  
**Spec**: [spec.md](./spec.md)  
**Status**: Research/design and implementation tasks T001..T012 complete.
Charts/UI/exports and release acceptance remain pending; see [execution record](./acceptance-results.md).

## Planning Refresh: 2026-10-18

This rerun incorporates the latest clarified specification and the comprehensive
[reviewer checklist](./checklists/visual-reporting.md). Reuse the completed research:
the refinements introduce no new technology choice requiring duplicate external research.
The existing setup script preserved this plan. `003-visual-reporting` in setup JSON is the
feature resolver identity; the actual Git branch remains `main`.

At planning refresh the built-in checklist was 16/16 and all 35 custom criteria were pending.
The owner subsequently explicitly delegated review and checkbox updates to the assistant.
That review is now recorded as 35/35 satisfied requirements-quality criteria in the
[execution record](./acceptance-results.md#requirements-quality-review); it is not runtime,
accessibility, renderer or release acceptance.

## Summary

**Owner scope amendment (2026-10-18)**: Prioritize generated-report accuracy,
explanations, chart appropriateness, readable layout and complete evidence. Manual PDF
screen-reader review is excluded from implementation/release prerequisites and must be
reported as NOT ASSESSED. Automated PDF tagging/header/description checks and actual
page inspection remain required; browser keyboard/reader requirements are unchanged.
This supersedes references below to mandatory manual PDF reader assessment. It does
not establish feasibility, close unchecked tasks or authorize accessibility claims.

Add deterministic, report-owned visual presentations to the existing Streamlit application.
Consume the stored 002 interpretations and typed evidence rather than asking a model to
choose charts or querying current sources. A single validated Visual Evidence adapter feeds
classification, subset controls, explanations, chart specifications, chart-evidence CSV and
local tagged PDF output. Preserve the original analytical evidence and all ownership,
incomplete-report acknowledgement, quota and retention safeguards.

Use application-generated Vega-Lite specifications, displayed through native Streamlit
chart controls, with `vl-convert-python` producing local SVG graphics. Use semantic HTML
and WeasyPrint for new visual PDFs, subject to an early Windows/tagging feasibility gate.
Keep the old ReportLab exporter for explicitly identified legacy exports during rollout;
never use it as a hidden fallback for a failed visual PDF. See [research.md](./research.md).

## Technical Context

**Language/Version**: Python 3.12, preserving the project's `>=3.12,<3.13` requirement.  
**Existing stack**: Streamlit, Pydantic 2, DuckDB, SQLite, Plotly and ReportLab.
Observed in the supplied interpreter: Streamlit 1.66.0, Altair 6.3.0, Plotly 6.9.0,
ReportLab 5.0.1 and pypdf 5.9.0. WeasyPrint and vl-convert are not installed.

**Planned dependencies**: Declare Altair directly rather than depending on Streamlit's
transitive installation; declare and install candidate vl-convert-python and WeasyPrint
dependencies before the synthetic feasibility spike, restoring only after manifest edits.
Finalize tested version bounds only after the feasibility gate passes. Add fontTools for explicit glyph coverage checks if not
provided through a directly declared rendering dependency. Raise the Streamlit floor to
the installed/reference-tested 1.66 line when introducing `alt=` and chosen controls.
Keep existing dependencies while their V1/export callers remain. No dependency changes
or installations are part of this planning command.

**Storage**: Existing SQLite `reports.payload_json`; extend typed section preferences
inside `CompositeReportV2` and add default-empty preferences/version to V1 `ReportContent`
for compatible owned historical views. Reuse report-level `preference_version` and transactional
compare-and-swap. No new report store, cache database or retention lifetime.

**Testing**: pytest and independent 002 numerical fixtures/oracles; Streamlit AppTest
for state/UI behavior; real-browser keyboard/focus/accessible-name checks; pypdf structural
inspection; local PDF raster inspection and actual NVDA/document-viewer assessment.
Structural validation is not an accessibility certification.

**Target Platform**: Current Windows development deployment, Python 3.12; deployment-local
rendering with an explicitly provisioned Pango runtime and packaged redistributable fonts.
Other operating systems need their own recorded dependency checks before support is claimed.

**Project Type**: Single Python Streamlit application, not a separate chart service.

**Performance Goals**: Record chart preparation, actual browser chart-ready and complete
PDF durations separately from model/query time. No numerical product SLA is invented.
Use bounded rendering jobs with a cancellable local child process for PDF conversion;
the implementation spike chooses and records a technical watchdog, not a product latency
promise. No job queue or detached renderer service.

**Constraints**: Zero new inference calls or source queries on view/subset/export actions;
no remote rendering, network-loaded chart data/fonts/scripts or user-authored HTML/CSS;
finite numeric evidence only; no reaggregation, rebinning, sampling, regression or synthetic
"Other". PDF text and labels at least 10 points, readable A4 portrait/landscape/pagination,
selectable text, genuine structure tags and descriptions, no partial-file success.

**Scale/Scope**: Up to four analytical sections per report; 500 returned analytical groups
per section; 20-category single-dimension charts; 8-series lines/grouped-bar rules and
20-series small-multiple ceiling; 100 distribution bins; all pairs through 5,000,
otherwise existing complete at-most-20-by-20 density evidence. Listing pages remain at
most 500 and listing exports at most 10,000 combined rows under 002. Weather adds a
four-coefficient overview and one selected variable/airport plot, not a fifth report section.

## Constitution Check

Pre-research and post-design evaluation against constitution 2.0.0:

| Principle/gate | Design evidence | Result |
|----------------|-----------------|--------|
| I. Defensible analytical correctness | Visual Evidence retains units, population, scope, weighting, numerator/denominator and exclusions; explanations use unrounded saved evidence | PASS by design |
| II. Explicit grain/data integrity | No joins or analytical SQL in visualization; typed identities, same-row/hour pairs, absent/null/zero separation and population reconciliation | PASS by design |
| III. Reproducibility | Snapshot/context/evidence/rule versions bound to preferences and exports; legacy adapters never consult current source data | PASS by design |
| IV. Honest communication | Linear axes, zero baseline for bars, tie/subset/coverage notices, provisional weather labels, no causal/significance claims | PASS by design |
| V. Question-driven explainability | Generic shape rules, ordinary-language acceptance and findings; no fixed-question whitelist | PASS by design |
| Privacy, ownership and cost | Reuse owner reads/CAS saves and report pruning; local-only assets/conversion; zero provider calls for presentation | PASS by design |
| Test/release honesty | Windows/tagged-PDF spike before full exporter, separate numerical/visual/manual gates and pending external 002 gates | PASS by design; release unverified |

No constitutional exception is requested. Ratification-date TODO in the constitution is
pre-existing and is not resolved or altered by this feature. Passing design gates does not
mean tagged PDF, WCAG, live interpretation or usability acceptance has passed.

## Existing Integration Facts

- V2 rendering currently returns tables; `build_figure` returns no figure for a composite.
- `SectionPresentationPreference` exists but lacks orientation, dot/grouped-bar views,
  weather selections and evidence/rule bindings. `ReportRepository.update_preferences`
  already performs ownership/version/CAS checks but deliberately permits only default/table.
  Extend this path instead of creating competing persistence logic; its V2-only guard
  must also support the conservative V1 adapter and additive preference defaults.
- Existing CSV/PDF dispatch supports V1 and V2. The V2 PDF is a table-oriented ReportLab
  document, not the required tagged visual export.
- 002 stores `ScalarResult`, `GroupedResult`, `DailyMeanResult`, `PeriodChangeResult`,
  `DistributionResult`, `RelationshipResult`, `WeatherPanelResult` and `ListingResult`.
  Their specialized denominators/supporting evidence must survive adaptation.
- Scope coverage is often unknown; do not derive complete calendars from observed min/max.
  A saved time result lacking bucket-coverage evidence must disclose unknown coverage.
- Existing stage timing measures server-side stages only. It is not a browser chart-ready
  measurement; instrument actual browser observation in the acceptance harness separately.

## Project Structure

### Documentation

```text
specs\003-visual-reporting\
  spec.md
  plan.md
  research.md
  data-model.md
  quickstart.md
  contracts\
    visual-evidence.md
    presentation-and-export.md
  checklists\
    requirements.md             # Built-in specification quality
    visual-reporting.md         # 35 reviewer-owned criteria; pending evaluation
  tasks.md                      # Next workflow; not produced by planning
```

### Implementation surfaces (planned, not created)

```text
app.py                         # Explicit controls, state and owned downloads
pyproject.toml                 # Tested dependency floors/renderer extras
src\airport_analytics\
  models.py                    # Typed preference extension, backward-compatible decoding
  reports\
    visual_evidence.py         # V2 and conservative V1 adapters; shape/selection validation
    charts.py                  # Pure Vega-Lite construction and accessible explanations
    visual_pdf.py              # Local tagged-document assembly and output checks
    rendering.py               # Native Streamlit report composition; retain table helpers
    export.py                  # Explicit dispatch; chart-evidence CSV and composite bundles
    assets\fonts\              # Approved redistributable fonts and licenses
  history\repository.py        # Extend existing owner/CAS preference update
  observability\timing.py      # Content-free chart/PDF stage measurements
tests\
  fixtures\visual_reporting\  # Frozen independent evidence and expected visual contracts
  unit\test_visual_*.py
  integration\test_visual_*.py
  browser\test_visual_*.py
  accessibility\test_visual_*.py
  performance\test_visual_*.py
```

**Structure decision**: Add three focused report modules, reuse the existing repository,
models, rendering/export boundaries and test folders. Do not create a frontend framework,
provider adapter, generalized plugin registry or separate rendering API.

## Phase 0: Research Decisions

See [research.md](./research.md) for source verification, alternatives and risks.

1. Pure evidence adapters and application-owned chart grammar; no model chart planner.
2. Native Streamlit/Vega-Lite browser views and matching local SVG export from the same
   chart specification. No browser-export dependency on Chrome.
3. WeasyPrint semantic HTML for tagged PDF; Windows Pango and actual tag/header/figure
   behavior must pass a bounded feasibility spike before exporter integration.
4. Existing SQLite optimistic concurrency; normalize legacy preferences in memory only.
5. Local packaged fonts with coverage checks and explicit unsupported-glyph failures.
6. Privacy-safe timings and failures; no question/label/value/HTML/spec payload logging.

All product choices are resolved. Technical feasibility checks below are implementation
gates with explicit failure outcomes, not unanswered permission requests.
The prior source-verified renderer research remains applicable. No new provider requests,
research-agent reruns, package installations or runtime feasibility claims were made in
this planning refresh; see research R8 for the clarification-to-design reconciliation.

## Phase 1: Design and Contracts

Artifacts:

- [data-model.md](./data-model.md): typed Visual Evidence, preferences, lifecycle and invariants.
- [contracts/visual-evidence.md](./contracts/visual-evidence.md): deterministic classification,
  selection and shape-specific browser/export handoff.
- [contracts/presentation-and-export.md](./contracts/presentation-and-export.md):
  control, concurrency, accessibility, CSV/PDF and failure contracts.
- [quickstart.md](./quickstart.md): proposed commands, manual review matrix and release gates.

### Requirement-to-design coverage

| Requirements | Design handoff | Required independent acceptance |
|--------------|----------------|---------------------------------|
| FR-001..004, FR-024..025 | Immutable shape adapters, explicit identities/coverage and saved-source-unavailable states | SC-001/002/009/010; malformed and historical fixtures |
| FR-005..010, FR-012..014, FR-026 | Fixed selection/compatibility rules, exact bins/pairs/density and shared chart grammar | All inclusive thresholds, null/zero gaps, constant axes, no provider/query calls |
| FR-011 | Visible text/value change summary retained across bars/dots/table/PDF | Zero/negative/unavailable baseline and consistent units |
| FR-015, FR-019, FR-031 | V1 additive defaults and V2 preferences through existing owner/CAS path | Reopen, stale save, retained drafts, deletion/pruning and shared-copy restrictions |
| FR-016..018, FR-020, FR-022 | Selected-resolution PDF/CSV, common formatting and dual visible/figure descriptions | Twelve actual PDFs, full plotted appendices, keyboard/reader review, exact values |
| FR-021, FR-027..029 | Authoritative 002 E2E/AQ inputs, complete composite dispatch, supporting evidence | Nine E2Es, ten AQs, incomplete acknowledgement and pending independent/live gates |
| FR-030 | Centered Pearson, weather x/delay y, retained unavailable temperature and verified-only precipitation bands | Separate coefficient/plot eligibility, all coefficient ties/counts, selected airport/variable round trips |
| FR-023 and SC-007/008 | Browser/PDF timing boundaries, explicit failures and real mixed-background participants | Content-free metrics, cold/warm records; five new participants with aviation/non-aviation experience per round |

All FR-001..031 are covered above. Schema version, rule version, evidence fingerprint,
analytical revision and preference counter remain distinct as defined in the data model.
The 500-group analytical selection is not a chart allowance; preserve the spec's bounds-at-
a-glance table without duplicating new ceilings in task generation.

### Delivery sequence for task generation

1. Freeze representative independent fixtures and boundary contract tests. Complete the
   Windows renderer/tagging/font spike with synthetic content only. A failed spike blocks
   the visual PDF work and integrated release; retain the browser/table report and report
   the failure, not an untagged substitute.
2. Implement typed adapters, evidence fingerprints, classification and default/subset rules.
   Cover all analytical kinds and conservative V1 fallback before UI wiring.
3. Implement shared Vega-Lite builders and deterministic explanations, then native chart
   controls with apply/reset, preserved selections and zero analytical reruns.
4. Extend owned preference persistence, stale-save conflict UX, version migration/reopen,
   shared-copy sanitization and pruning/deletion tests.
5. Add local tagged PDFs, chart-evidence CSV/manifest metadata and full composite assembly.
   Make downloads explicit, snapshot-bound and complete before exposing bytes.
6. Run automated numerical/round-trip/fault/privacy tests and actual browser/PDF assessment.
   Execute nine shared E2Es and ten AQ cases; obtain independent/live/real-participant
   acceptance separately. Keep not-run/blocked records visible.

### High-risk design details

- Temporal dimension roles come from interpretation/evidence, never regexes on labels.
  Rankings remain ranked categories even with YYYY-MM labels. `weekday` and
  `month_of_year` are ordered categories.
- Time lines break at null/absent calendar buckets. Unknown coverage does not establish
  zeroes or a complete time domain. A known point with no consecutive known neighbour
  is a marker, not a line segment. Requested-boundary partiality and missingness are distinct.
- Persisted 002 density may list only occupied cells. Expand zero cells only within the
  stored complete grid and only after population/boundary reconciliation; never recompute
  from current flights or a truncated sample.
- Density's constant-axis display interval may have positive width while the actual extent
  is a single value. Keep actual extent and sole-value inclusion metadata in exact evidence.
- For two categorical dimensions, first grouping role is primary and second is series.
  Grouped bars require both inclusive thresholds; otherwise a sparse labelled heatmap.
  Its display grid is not an authorization to create more analytical records or infer zero.
- For unverified weather units use the saved recorded-unit label, preserve all coefficients
  and their counts/reasons, and omit precipitation bands. Airport/variable selection never
  combines populations. Default temperature and stable first airport only for presentation.
  Keep unavailable temperature selected with a specific reason and explicit alternatives;
  unavailable Pearson alone does not suppress valid paired plots. Use weather x and delay y.
- Period changes retain a visible text/value change summary across views/PDF. PDF charts
  include both a visible evidence-derived description and its associated figure alternative.
- If historical source files are unavailable, sufficient saved evidence still renders with
  a notice; disable paging/recalculation instead of substituting current source rows.
- No-data, selection-required and technical-failure states are different. A table can remain
  available in all three without implying a chart succeeded.
- PDF must include every plotted pair (up to 5,000) or exact density cell/bin; potentially
  long appendices paginate rather than truncate or reduce text below 10 points.

## Validation and Release Gates

| Gate | Required evidence | Planning status |
|------|-------------------|-----------------|
| Requirements-quality review | Reviewer disposition of the 35 custom checklist criteria; no automatic checkbox changes | REVIEWED 35/35 under explicit owner delegation; not runtime acceptance |
| Renderer feasibility | Windows local SVG and tagged PDF, embedded fonts, selectable text, heading/table/figure tree, missing-resource and timeout failures | NOT RUN |
| Shape/number correctness | All ten presentation rows with >=3 independent examples each; all threshold/degenerate cases; full-precision reconciliation | NOT RUN |
| Preference lifecycle | Compatible switches, stable IDs, CAS conflicts/reapply, owner isolation, retention, legacy reopen; zero provider/query calls | NOT RUN |
| Export agreement | At least 12 fully inspected PDFs, all plotted CSV rows, matching selection and incomplete-composite notices | NOT RUN |
| Accessibility | Actual browser keyboard/focus/screen-reader and PDF tag/header/navigation review with recorded versions | NOT RUN |
| Performance/privacy | Cold/warm browser-ready/PDF timings; resource/timeout fault tests and content-free telemetry | NOT RUN |
| Integrated release | 002 E2E-01..09 and AQ-01..10 plus pending independent/live 002 gates | BLOCKED until executed |
| Formative usability | Five new representative analysts per scored round, including aviation/non-aviation backgrounds; >=4/5 correct on both components of each task separately | NOT RUN; human participation required |

Implementation may proceed after task generation and the early feasibility gate. Release
cannot be declared complete solely from automated tests or installed renderer support.
The implementation workflow's pending-checklist decision also remains required. The early
feasibility spike is itself implementation work; only dependent exporter integration is
blocked until its successful result, not the spike that establishes that result.

Post-refresh constitution evaluation: all design gates above remain PASS by design.
No constitutional exception or unresolved product clarification was introduced. Actual
renderer, accessibility, independent/live and usability release gates remain unverified.

## Complexity Tracking

No constitutional violations. The extra local renderer and Pango runtime are necessary
because the current untagged PDF path cannot satisfy tagged headings/tables, reading order
and chart descriptions. A second analytical pipeline or hosted renderer is rejected.
