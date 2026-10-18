# Tasks: Automatic Visual Reporting

**Input**: [Specification](./spec.md), [plan](./plan.md), [research](./research.md), [data model](./data-model.md), [contracts](./contracts/), [validation guide](./quickstart.md).
**Feature**: `003-visual-reporting`; actual Git branch remains `main`.
**Status**: Implementation started; only checked tasks have recorded completion. Renderer feasibility and release acceptance remain pending.

**Owner scope amendment, 2026-10-18**: Manual PDF screen-reader/header-navigation review is excluded and recorded as NOT ASSESSED, not passed. It no longer blocks implementation or release. Retain automated PDF structure checks, actual page-quality inspection, and all browser accessibility requirements. Prioritize generated-report accuracy, explanations, graphics, legibility and complete evidence. Historical execution records are not rewritten as passes.
**Tests**: Required by FR-020 and SC-001..011; write targeted tests before their implementations and demonstrate the relevant failure before fixing it. Do not treat missing imports or zero collected tests as adequate behavioral coverage.
**Organization**: Setup, shared foundation, US1 (P1), US4 (P1), US2 (P2), US3 (P2), then integrated release gates.

## Format and Execution Rules

- Every task uses `- [ ] T### [P?] [US#?] Description with exact paths`.
- Paths are relative to this application workspace, not the parent Git root.
- `[P]` means eligible for parallel work only after the prerequisites listed below; it is not permission to race edits to a shared file. Unmarked tasks are serial within their phase.
- Tasks generate implementation work, not new product permissions. Preserve existing dirty changes, model policy, ownership, ten-report pruning and analytical behavior.
- Use `..\beon\Scripts\python.exe` and the existing project tooling. Change dependency manifests before restoring declared packages; native runtime installation requires operator approval.
- The 35-item [reviewer checklist](./checklists/visual-reporting.md) was reviewed under explicit owner authorization; [disposition](./acceptance-results.md#requirements-quality-review) records 35/35 satisfied requirements-quality criteria, not runtime acceptance. Do not change reviewer criteria automatically.
- No live provider calls are authorized. Human/independent/live gates remain pending until genuine authorized execution. A blocked external task remains unchecked with its reason.
- The early renderer spike is implementation work; its failure blocks dependent visual-PDF integration and release, not unrelated browser/table work. Never substitute an untagged/table-only success.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish review disposition, independent evidence and declared local dependencies without changing analytics.

- [X] T001 Record reviewer disposition or explicit implementation-workflow approval to proceed with pending criteria in `specs\003-visual-reporting\acceptance-results.md`, referencing `specs\003-visual-reporting\checklists\visual-reporting.md`; retain all unreviewed markers and list unresolved blockers rather than asserting approval.
- [X] T002 Freeze synthetic independently calculated examples and an oracle manifest in `tests\fixtures\visual_reporting\manifest.json` with bounded evidence fixtures in `tests\fixtures\visual_reporting\`; assign at least three examples per ten default presentation rows, weather populations, all threshold/degenerate cases and historical V1/V2 payloads; record expected values, independent derivation, source version and requirement IDs without reusing production calculations as the oracle.
- [X] T003 Declare direct Altair, candidate vl-convert-python, WeasyPrint and any directly used fontTools dependencies and the reference-tested Streamlit floor in `pyproject.toml`; preserve Python `>=3.12,<3.13` and existing Plotly/ReportLab callers, restore only after manifest edits, and record candidate versions/native Pango prerequisites in `specs\003-visual-reporting\research.md`; pin final tested compatibility after T027 rather than claiming the packages already work.
- [X] T004 Package only reviewed redistributable static fonts and per-asset licenses in `src\airport_analytics\reports\assets\fonts\` and document approved Windows Pango/DLL setup in `specs\003-visual-reporting\quickstart.md`; cover actual synthetic/source-name scripts and do not copy commercial workstation fonts or install native tools without approval.

**Checkpoint**: Review disposition recorded; independent fixtures and local candidate resources available. No renderer pass is implied.

## Phase 2: Foundational (Shared Blocking Prerequisites)

**Purpose**: One immutable evidence contract and one safe presentation boundary for all stories. Finish T005..T012 before story implementation.

- [X] T005 [P] Add contract tests in `tests\unit\test_visual_evidence.py` for closed versions/roles/states, canonical identity collisions, exact integers, rejected boolean/nonfinite values, immutable fingerprints and source-free adaptation; assert the data-model field constraints quoted in T007/T008 and keep fixture expectations independent.
- [X] T006 [P] Add compatibility/coverage tests in `tests\integration\test_visual_historical_evidence.py` for legacy V1, old V2, missing optional metadata, original-snapshot loss, unknown coverage and future unsupported versions; assert no source reload, no write on read and no fabricated provenance.
- [X] T007 Define the immutable VisualEvidence/VisualDimension common types in `src\airport_analytics\reports\visual_evidence.py`: `visual_evidence_version` is "Literal 1", `selection_rule_version` is "Fixed version string, initially `003.1`", `dimensions` has "At most two aggregate roles; no inferred temporal labels", `role` is "`category`, `ordered_category`, `time`", `coverage` is "Known bucket intervals/gaps or explicit unavailable reason", and `payload` requires "Finite numbers; explicit unavailable values and reasons"; match saved report/section/revision/provenance, preserve unknown scope and reject booleans/infinities/invalid numeric text.
- [X] T008 Define VisualSelection and PresentationResolution in `src\airport_analytics\reports\visual_evidence.py`: `available_groups` is "nullable when unknown", "All selected identities must exist in stored evidence", single-category charts "cap at 20 identities", time series "cap at 20 selected series", grouped bars use "8-series/20-primary thresholds", heatmaps retain "at-most-500 returned analytical cells"; states are exactly "`ready`", "`table_selected`", "`selection_required`", "`no_plottable_data`", "`missing_evidence`", "`invalid_evidence`", "`render_failed`", with explicit reasons, compatible choices and no shape fabricated from missing values.
- [X] T009 Implement canonical `(field_id, code, reference_status)` JSON identities and SHA-256 analytical evidence fingerprints in `src\airport_analytics\reports\visual_evidence.py`; honor "Stable across preferences; excludes narrative/presentation timestamps", fixed canonical serialization and NaN/Infinity rejection; preserve duplicate-name codes, literal versus missing/unmatched identities and full numeric precision.
- [X] T010 Implement pure shape adapters/classification in `src\airport_analytics\reports\visual_evidence.py` over every existing typed result and a versioned conservative V1 definition mapping; apply listing/distribution/relationship/period/scalar/time/ranking/category precedence, preserve definitions/grain/denominators, give unsupported/conflicting shapes explicit states, and expose no provider, SQL executor or current-catalogue lookup.
- [X] T011 Persist only any missing bounded verified bucket-coverage handoff for NEW reports in `src\airport_analytics\models.py` and `src\airport_analytics\reports\generation.py`, with snapshot/declaration identity and backward-compatible unknown defaults; prove old reports are not backfilled in `tests\integration\test_visual_historical_evidence.py`; if existing metadata suffices, record the evidence in `specs\003-visual-reporting\acceptance-results.md` instead of adding redundant fields.
- [X] T012 Add repository-standard typed presentation/render/export errors in `src\airport_analytics\errors.py` and an explicit 003 rollout capability in `src\airport_analytics\config.py`; disabled mode must identify existing legacy/table behavior, enabled visual failures must remain errors, and imports must not make legacy browsing depend on an available native PDF runtime.

**Checkpoint**: Immutable adapters pass contract/historical tests; all stories share the same evidence and error semantics. No new analytics or migrations on read.

## Phase 3: US1 - Receive an Appropriate Visual Automatically (Priority: P1) - MVP

**Goal**: Useful default cards, bars, ordered categories, trends, series panels and tables from existing evidence.
**Independent test**: Open frozen scalar/category/time/listing reports without interpretation or source access; reconcile every selected value/identity/order, verify required defaults and honest empty/limit messages. Richer shape graphics are delivered in US3, not claimed as a finished US1 matrix yet.

### Tests First

- [X] T013 [P] [US1] Add shape/default/threshold tests in `tests\unit\test_visual_defaults.py` for scalar versus one grouped row, ranked first-20/ties, unranked 21 requiring selection, 8/9 and 20/21 series, two-category grouped bars/heatmap, negative/null/zero eligibility, pooled month/weekday order and ranked YYYY-MM precedence.
- [X] T014 [P] [US1] Add chart-spec/explanation tests in `tests\unit\test_visual_charts.py` for embedded values, exact numeric agreement, canonical order, zero-baseline bars, linear/shared scales, non-color cues, no data URLs/reaggregation and descriptions limited to the shown evidence.
- [X] T015 [P] [US1] Add AppTest integration in `tests\browser\test_visual_default_ui.py` for default section composition, table-only listings, failed/valid-empty sections, missing source/evidence, loading/failure messages and zero provider/query calls using patched call counters rather than live requests.

### Implementation

- [X] T016 [US1] Implement default and subset resolution in `src\airport_analytics\reports\visual_evidence.py` using the spec's inclusive limits: default first-20 only for rankings, require explicit unranked/over-20-series selection, preserve selected/returned/available counts, tie notices and canonical ordering; do not combine categories or expand the analytical selection.
- [X] T017 [US1] Implement scalar/card, single-category bars/dots, two-category grouped-bar/heatmap and listing-table chart payloads in `src\airport_analytics\reports\charts.py`; heatmap holes are unavailable, not zeros; all chart data are embedded and application owned, with no arbitrary analyst grammar or implicit aggregation.
- [X] T018 [US1] Implement temporal lines/markers and small multiples in `src\airport_analytics\reports\charts.py` with chronological recorded dates, Monday weeks, shared comparable scales and gaps across missing/nonconsecutive buckets; distinguish isolated points and unknown versus partial coverage, never connect pooled months as a trend.
- [X] T019 [US1] Implement shared names, descriptions and display formatting in `src\airport_analytics\reports\charts.py`, preserving English/source Unicode, exact evidence, explicit requested precision over approved AQ defaults over two decimals, unrounded ties and subset-only extrema; retain units, counts, provenance and all unavailable reasons without model-written findings.
- [X] T020 [US1] Compose default charts/cards, explanations and labelled exact/broader evidence tables per successful/empty section in `src\airport_analytics\reports\rendering.py`; use native named chart controls, source-unavailable notices and explicit unsupported/no-data/selection-required states; preserve failed-section notices and existing weather findings.
- [X] T021 [US1] Wire the 003 capability, initial report/reopened report defaults and safe error/status handling in `app.py`; keep V1/V2 analytical submission, disclosure, ledger, browsing and consent paths unchanged and identify legacy mode clearly.
- [X] T022 [US1] Add content-free visual-preparation timing in `src\airport_analytics\observability\timing.py` and instrument `src\airport_analytics\reports\rendering.py`; record only duration/environment/family/evidence size/failure category and never call server timing browser-ready.
- [X] T023 [US1] Run T005/T006/T013..T015 suites plus related exploration summary regressions and inspect diagnostics for touched Python files; record exact commands/counts and remaining richer-shape obligations in `specs\003-visual-reporting\acceptance-results.md` without a full-feature pass claim.
- [X] T024 [US1] Document the delivered browser-only MVP, bounded defaults, unavailable-source states and explicit remaining visual/PDF gates in `README.md` and `specs\003-visual-reporting\acceptance-results.md`; do not describe the incomplete US3 shape matrix as accepted.

**Checkpoint**: US1 browser MVP is usable and independently checkable; no promise of a validated visual PDF yet.

## Phase 4: US4 - Export and Access the Same Evidence (Priority: P1)

**Goal**: Accessible local visual PDF and exact chart CSV for currently available families; generic contracts support later US2/US3 additions without changing evidence.
**Independent test**: A saved default graphical selection produces a real matching chart, complete exact appendix and tagged document; explicit table view stays a table, while technical failures produce no partial bytes. Full family/selected-preference acceptance is repeated after US2/US3.

### Tests and Early Feasibility First

- [X] T025 [P] [US4] Add synthetic Windows renderer/tag/font feasibility checks in `tests\integration\test_visual_pdf_spike.py` with a real SVG, selectable Unicode, long labels, document language, headings, Figure alternative, Table/TR/TH/TD header relationships, multi-page 10-point tables and missing-resource/timeout cases; use only synthetic evidence and temporary job assets.
- [X] T026 [P] [US4] Add export agreement/failure contract tests in `tests\integration\test_visual_exports.py` for owner/selection/fingerprint binding, chart versus analytical CSV, exact raw precision/nulls/formula-safe text, complete composite acknowledgement and no partial PDF; add automated accessibility structure assertions in `tests\accessibility\test_visual_pdf_accessibility.py` without treating them as human-reader acceptance; assign these initial scenarios the `export_defaults` test-name token under the checkpoint selection rules below.
- [ ] T027 [US4] Execute and record the local SVG/WeasyPrint feasibility spike from `tests\integration\test_visual_pdf_spike.py` in `specs\003-visual-reporting\acceptance-results.md`, including actual page inspection, automated structural checks, native/package versions, fonts and a technical watchdog; finalize supported Vega-Lite/package versions in `pyproject.toml` and `specs\003-visual-reporting\research.md` only from evidence. Manual PDF reader review is NOT ASSESSED and does not block this task. Unresolved technical or page-quality failures still block T028..T032 and their PDF-dependent validation, never browser-only T033 or a legacy fallback.

### Implementation After Feasibility Pass

- [ ] T028 [US4] Implement job-scoped spawned PDF worker and deny-by-default asset resolution in `src\airport_analytics\reports\visual_pdf.py`; allow only generated job graphics/approved fonts, escape source text, reject remote/arbitrary-file/SVG references and attachments, enforce bounded technical timeout, terminate only owned work and clean exact temporary resources on all paths.
- [ ] T029 [US4] Implement shared-spec local SVG conversion and font/glyph preflight in `src\airport_analytics\reports\visual_pdf.py` using the T027-compatible version; retain exact selected values/scales/order and selectable accessible labels or their complete semantic equivalent; missing dependency/glyph/font must raise safe typed errors without silent replacement.
- [ ] T030 [US4] Assemble and validate complete tagged PDF documents in `src\airport_analytics\reports\visual_pdf.py`: actual chart graphics, visible evidence descriptions AND associated figure alternatives, tagged headings/tables/header relationships, language, selectable Unicode and all plotted evidence; use A4 portrait/landscape/pagination with minimum 10-point text, repeated headers, full-name keys, grayscale cues and no appendix truncation.
- [ ] T031 [US4] Extend `src\airport_analytics\reports\export.py` with distinct chart-evidence CSV/bundle output using existing escaping/UTF-8/null conventions; include snapshot/revision/rule/fingerprint/preference bindings, selection and omissions, precise edges/inclusivity/counts and provisional/denominator flags; preserve existing analytical/listing export semantics and combined listing cap.
- [ ] T032 [US4] Wire explicit visual versus legacy PDF dispatch and owner/current-effective-selection validation in `src\airport_analytics\reports\export.py` and `app.py`; compose all successful/valid-empty sections plus acknowledged failure notices, expose complete validated bytes only, invalidate observed stale downloads and preserve browser report on failure with explicit zero-model-call retry.
- [ ] T033 [US4] Complete native accessible web evidence alternatives and focus/name/disabled-reason handling in `src\airport_analytics\reports\rendering.py` and `app.py`, retaining exact pair-table paging without forcing mark-by-mark navigation; add real-browser checks in `tests\browser\test_visual_accessibility.py` and record actual keyboard/reader findings in `specs\003-visual-reporting\acceptance-results.md`; browser-only work depends on T020/T021, not T027, and interactive-selection coverage is repeated after T044 in T046.
- [ ] T034 [US4] Add complete PDF-build timing and controlled missing-library/font/glyph/resource/timeout fault coverage in `src\airport_analytics\observability\timing.py` and `tests\integration\test_visual_export_failures.py`; prove no contents in telemetry, partial/stale downloads, network access or provider/query calls.
- [ ] T035 [US4] Run the mandatory US4 default-export checkpoint selectors below plus spike/browser/fault tests and inspect actual current-family browser/PDF pages, tags, fonts and structural reading order; record scoped results and outstanding US2/US3 integration in `specs\003-visual-reporting\acceptance-results.md`. Manual PDF reader review is NOT ASSESSED; actual browser reader review remains required.
- [ ] T036 [US4] Document approved native/font setup, capability/legacy dispatch, complete-only download semantics and actionable safe failures in `README.md` and `specs\003-visual-reporting\quickstart.md`, replacing proposed commands with actual collected test selectors where implemented.

**Checkpoint**: Current-family browser/CSV/PDF agreement established only to recorded scope; release still awaits richer views, lifecycle and integrated human gates.

## Phase 5: US2 - Explore Compatible Views Without Changing the Answer (Priority: P2)

**Goal**: Compatible switches and owned stable saves, including explicit stale-save recovery.
**Independent test**: Change view/subset on a saved report, reopen it and compare unrounded evidence/scope/revision; stale tabs never overwrite newer preferences; provider/query counts stay zero.

### Tests First

- [X] T037 [P] [US2] Add typed preference/compatibility tests in `tests\unit\test_visual_preferences.py` for all family enums, field relevance, duplicate/unknown IDs, saved evidence/rule bindings, over-limit drafts and schema-version normalization; assert T040's quoted constraints and the full compatibility matrix.
- [ ] T038 [P] [US2] Add owner/CAS lifecycle tests in `tests\integration\test_visual_preferences.py` for V1/V2 saves, stale version/transaction races, unchanged analytical fields/retention order, missing/deleted/pruned reports, unsupported versions and shared-copy payload restrictions.
- [ ] T039 [P] [US2] Add AppTest preference-control tests in `tests\browser\test_visual_preferences_ui.py` for draft/apply/reset/table, labelled counts and disabled reasons, invalid-input preservation, two-tab reload/reapply and zero provider/query calls; add PDF/CSV selection changes and stale-download invalidation scenarios with `export_preferences` names in `tests\integration\test_visual_exports.py` and corresponding structure cases in `tests\accessibility\test_visual_pdf_accessibility.py`; coordinate edits to those T026-owned files rather than treating that portion as parallel.

### Implementation

- [ ] T040 [US2] Extend `SectionPresentationPreference` in `src\airport_analytics\models.py` with "`preference_schema_version`" as "New version 1; missing in old reports means legacy normalization", `chart_family` where "Existing names retained; add `dot` and `grouped_bar`", `orientation` as "`horizontal` or `vertical` for bar views, null elsewhere", `category_ids`, `series_ids` as "Stable identity tokens; canonical order comes from evidence", weather fields "valid only for weather", evidence/rule versions "Bound to known adapter/rule versions" and fingerprint to "Bind selections to this saved analytical evidence"; "Reject irrelevant orientation/selection fields and duplicate/unknown tokens", retaining the old "max-length 500 list bound" without treating it as chart permission.
- [ ] T041 [US2] Add V1 `ReportContent` defaults "default-empty typed `presentation_preferences` and `preference_version=1`" with "reserved presentation section ID `legacy`" in `src\airport_analytics\models.py`; preserve the existing positive V2 transaction counter, distinguish it from schema/rule/evidence/revision and keep decoding read-only with no invented V2 sections.
- [ ] T042 [US2] Extend `ReportRepository.update_preferences` in `src\airport_analytics\history\repository.py` through the existing owner/full-map/version/CAS transaction for both saved types; validate against original saved evidence, reject stale/incompatible maps atomically, increment only the preference counter and preserve other section selections, analytic revision, creation time, report order and acknowledgement.
- [ ] T043 [US2] Implement bound-preference normalization/compatibility and explicit reset/selection validation in `src\airport_analytics\reports\visual_evidence.py`, preserving saved versions or explaining incompatible history without auto-writes; update derived export bindings without duplicating analytical evidence or relaxing shape limits.
- [ ] T044 [US2] Wire native compatible controls and owner/report/section-keyed draft versus applied state in `src\airport_analytics\reports\rendering.py` and `app.py`; separate local Apply from explicit Save, preserve invalid drafts/prior valid view, expose accessible disabled reasons and conflict reload/review/reapply without automatic merge/retry.
- [ ] T045 [US2] Integrate selected-preference downloads and lifecycle invalidation in `app.py` and `src\airport_analytics\reports\export.py`; recheck ownership/current versions, export applied not draft state, drop only derived assets for deleted/pruned reports and avoid adding raw graphics/pairs/tokens to existing consented shared projections in `src\airport_analytics\history\repository.py`.
- [ ] T046 [US2] Run T037..T039 and the mandatory US2 default-plus-preference export checkpoint selectors below; repeat `tests\browser\test_visual_accessibility.py` after T044 and perform actual two-tab keyboard/focus checks; record exact lifecycle, zero-call and selection-agreement outcomes in `specs\003-visual-reporting\acceptance-results.md` and update compatible-view/save instructions in `README.md`.

**Checkpoint**: Compatible views and subsets survive owned reopening; conflict recovery never changes analytical evidence.

## Phase 6: US3 - Understand Distributions, Changes and Relationships (Priority: P2)

**Goal**: Exact bins, paired values/density and origin-hour weather graphics with honest findings and changes.
**Independent test**: Independently frozen bins/periods/pairs produce identical browser/table/CSV/PDF meanings, including missing/constant/zero cases and full 5,000-pair appendices.

### Tests First

- [ ] T047 [P] [US3] Add exact distribution/period tests in `tests\unit\test_visual_distributions_changes.py` for original interval inclusion/counts/zero bins, no re-binning, missingness and both base values plus unchanged absolute/relative text summaries, including zero/negative/unavailable baselines.
- [ ] T048 [P] [US3] Add pair/density/weather tests in `tests\unit\test_visual_relationships_weather.py` for 5,000/5,001, all pairs, full grids/extents/edges, partition reconciliation, 20x20/1x20/20x1/1x1, coefficient versus plot eligibility, exact Pearson ties, weather x/delay y, unavailable temperature and per-airport selection/provisional units.
- [ ] T049 [P] [US3] Add rich-view AppTest and export regression coverage in `tests\browser\test_visual_analytical_ui.py` and `tests\integration\test_visual_analytical_exports.py` for all AQ evidence forms, selected weather variable/airport, saved reopen, verified-only bands, denominators/provisional capacity/model labels, complete paired appendices and zero provider/query calls; place rich-family export scenarios in `test_visual_analytical_exports.py` and reserve rich structure cases in `tests\accessibility\test_visual_pdf_accessibility.py` for coordinated additions after T039, not parallel shared-file edits.

### Implementation

- [ ] T050 [US3] Complete exact distribution/period payload validation in `src\airport_analytics\reports\visual_evidence.py` and graphics/summaries in `src\airport_analytics\reports\charts.py`; use saved bins/periods/changes only, no percentage on base-unit axis and no new change chart or analytical calculation.
- [ ] T051 [US3] Complete relationship/density adaptation in `src\airport_analytics\reports\visual_evidence.py` preserving "`pair_count + x_missing_only + y_missing_only + both_missing = scoped_count`", all source IDs/x/y and exact extents; expand absent occupied cells to zero ONLY from reconciled complete saved grids, with full stored boundaries/inclusion and no sample or current-source density reconstruction.
- [ ] T052 [US3] Implement full scatter/density builders in `src\airport_analytics\reports\charts.py`: at most 5,000 all-pair points, otherwise at most 20x20 cells with 20 equal-width intervals on varying axes and sole-value intervals on constant axes; retain actual versus display extents, cell count legends, paired/excluded captions and no regression/scatter-density switch requiring missing evidence.
- [ ] T053 [US3] Implement weather selection/overview/findings in `src\airport_analytics\reports\visual_evidence.py` and `src\airport_analytics\reports\charts.py` retaining "`temp`, `wind_speed`, `precip`, `visib`", "`weather_units_status=unverified`" recorded labels and no bands, centered untransformed Pearson, unrounded absolute ties, weather x/delay-minutes y, default temperature/stable first airport and "Airport `null` in an ungrouped panel means combined scope, not a missing airport category"; unavailable plot keeps its explicit selection/reason, unavailable coefficient alone never suppresses valid pairs.
- [ ] T054 [US3] Wire rich selected plots, weather-first coefficient overview, separate visible period summaries and exact/supporting evidence in `src\airport_analytics\reports\rendering.py` and `app.py`; preserve all returned airport coefficients while plotting only one airport/variable, persist selectors via US2 and retain AQ rounding/daily denominators/provisional and qualified-aircraft labels.
- [ ] T055 [US3] Complete rich-family PDF/CSV assembly in `src\airport_analytics\reports\visual_pdf.py` and `src\airport_analytics\reports\export.py`, including every plotted pair/bin/cell, selected weather plot plus all coefficient evidence, visible/figure descriptions and complete composite disclosures; supporting 500-row pools never replace a 5,000-pair exact appendix or expand listing limits.
- [ ] T056 [US3] Run T047..T049 and the mandatory US3 all-export checkpoint selectors below against independent fixtures, inspect rich-family pages and reconcile all ten presentation rows plus weather; record actual errors under `max(1e-9, 1e-12 * abs(expected))`, exact discrete agreement and unavailable reasons in `specs\003-visual-reporting\acceptance-results.md`.

**Checkpoint**: All default families and weather have exact evidence-preserving graphics and selected exports; integrated release still depends on the final gates.

## Phase 7: Polish and Cross-Cutting Release Gates

**Purpose**: Full acceptance, honest external gate reporting, documentation and final compatibility.

- [ ] T057 [P] Add actual-browser chart-ready measurements in `tests\performance\test_visual_timings.py` and cold/warm complete-PDF baselines for all twelve examples and boundary sizes; record environment/versions/family/size/duration and technical fault results, not server timings relabelled as browser-ready or invented SLA thresholds.
- [ ] T058 [P] Extend `tests\integration\test_exploration_shared_e2e.py` with all authoritative 002 E2E-01..09 through current visual/save/export paths and add AQ-01..10 agreement in `tests\integration\test_visual_airport_questions.py`; use controlled offline interpretation fixtures for regressions and label them separately from live interpretation acceptance.
- [ ] T059 Complete automated threshold/privacy/ownership/fault review across `tests\unit\test_visual_*.py`, `tests\integration\test_visual_*.py`, `tests\browser\test_visual_*.py`, `tests\accessibility\test_visual_*.py` and `tests\performance\test_visual_*.py`; run related 002 baseline selectors from `specs\003-visual-reporting\quickstart.md`, existing Ruff lint/format and Pylance checks for changed files, recording real commands/counts/failures in `specs\003-visual-reporting\acceptance-results.md`.
- [ ] T060 Inspect at least twelve complete PDFs spanning every family, negative/null/constant/long-label/limit cases, full 5,000-pair evidence and acknowledged composite failure using `specs\003-visual-reporting\quickstart.md`; retain safe evidence references and actual page/glyph/legend/grayscale/10-point/selectability findings in `specs\003-visual-reporting\acceptance-results.md`, not just text extraction.
- [ ] T061 Obtain actual WCAG 2.2 AA web keyboard/reader assessment and automated PDF structure/header-relationship checks plus visual page inspection per `specs\003-visual-reporting\contracts\presentation-and-export.md`; document tested versions, visible AND figure descriptions, focus/disabled reasons and outstanding failures in `specs\003-visual-reporting\acceptance-results.md`. Record manual PDF reader review as NOT ASSESSED; no AppTest-only web acceptance, verified PDF reader compatibility or PDF/UA certification claim.
- [ ] T062 Request separate authorization and independent reviewers for pending 002 corpus/live and shared integrated gates, following `specs\002-natural-language-exploration\spec.md`; record actual frozen corpus/model/snapshot/outcomes in `specs\002-natural-language-exploration\acceptance-results.md` and cross-reference `specs\003-visual-reporting\acceptance-results.md`; without authorization or reviewers retain BLOCKED/NOT RUN, never dispatch automatically or stitch retry successes.
- [ ] T063 Recruit five real non-implementer report/analysis users including at least one with and one without aviation experience for the fixed SC-007 tasks in `specs\003-visual-reporting\quickstart.md`; record de-identified backgrounds and first unassisted observation-plus-limitation results per task in `specs\003-visual-reporting\acceptance-results.md`, requiring four of five on BOTH components per task and five new people after material fixes/failure; no simulated participants.
- [ ] T064 Resolve defects caused by this feature in `src\airport_analytics\reports\`, `src\airport_analytics\history\repository.py`, `src\airport_analytics\models.py` or `app.py` with focused regression coverage, and repeat affected automated/manual/participant gates in `specs\003-visual-reporting\acceptance-results.md`; preserve previous failures and leave unrelated pre-existing issues untouched.
- [ ] T065 Finalize setup/limits/error/legacy/selection/export documentation in `README.md` and `specs\003-visual-reporting\quickstart.md`, checking that declared package/font/native versions match actual supported output and proposed test selectors now map to collected tests; remove only named task-owned temporary artifacts, not shared services/files.
- [ ] T066 Reconcile FR-001..031, SC-001..011 and every shape/bound/compatibility row with completed evidence in `specs\003-visual-reporting\acceptance-results.md`; re-evaluate constitution/release gates in `specs\003-visual-reporting\plan.md`, retain reviewer-owned `specs\003-visual-reporting\checklists\visual-reporting.md` markers unless explicitly authorized to evaluate them, and declare integrated completion only when both 002/003 external and human gates genuinely pass.

## Dependencies and Execution Order

### Phase and Story Graph

```text
Reviewer disposition (T001)
  -> setup resources/fixtures (T002..T004)
  -> foundation tests/types/adapters/handoff/errors (T005..T012)
  -> US1 defaults (T013..T024)
       -> US4 exports/accessibility (T025..T036; T027 blocks PDF T028..T032, not browser T033)
       -> US2 compatible selection/persistence (T037..T046)
       -> US3 richer shapes (T047..T056; T054/T055 require US2/US4)
  -> integrated automated/manual acceptance (T057..T061)
       -> independent/live authorization and acceptance (T062)
       -> fixed-report participant study (T063; independent of T062)
  -> corrections/documentation/final reconciliation (T064..T066; both T062/T063 required)
```

Phase headings are priority order, not a claim that the P1 exporter already supports
families added later. US4 is independently validated with US1 fixtures; its full rich-
family and selected-view acceptance is completed by T045/T055 and final gates.

### Explicit Prerequisites and Shared-File Constraints

| Task/group | Required prerequisites |
|------------|------------------------|
| T002..T004 | T001; serial order is safe and preferred |
| T005 and T006 | T002..T004; independent test files can be authored concurrently |
| T007 -> T008 -> T009 -> T010 -> T011 -> T012 | Both foundation tests authored first; execute this chain serially; T011 tests reuse T006's file |
| T013, T014, T015 | T005..T012; independent test files can be authored concurrently |
| T016..T024 | T013..T015, then serial in listed order; shared evidence/chart/UI files must not race |
| T025 and T026 | T005..T012; independently authored test files, safe alongside US1 only if no fixture/shared-file edits |
| T027 | T003/T004/T025; synthetic-only feasibility independent of finished US1; actual reader/operator availability may block |
| T028..T032 | T013..T024, T026/T027; serial in listed order |
| T033 | T020/T021; browser-only, no T027 prerequisite; coordinate shared UI edits with T032/T044, repeat selection checks in T046 |
| T034 | T022/T028..T032; PDF timing/fault checks require the exporter |
| T035 -> T036 | T033/T034 and T026/T027; actual review availability required |
| T037, T038, T039 | T013..T024; tests independently authored, may overlap US4 in distinct files |
| T040..T046 | T037..T039, then serial; T045 also requires T031/T032; coordinate shared `app.py`/export/rendering edits with US4 |
| T047, T048, T049 | T005..T012 and T002 fixtures; independent test authoring, no shared fixture rewrites |
| T050..T056 | T047..T049 then serial; T054 requires T040..T044, T055 requires T028..T032 and T045, T056 requires all story implementations |
| T057 | T022/T034 and T056; distinct performance file |
| T058 | T046/T056; distinct integrated test files, may run in parallel with T057 |
| T059 | T057/T058 and all story checkpoints |
| T060 -> T061 | T059 then serial; actual assessment availability required |
| T062 | T060/T061; independent/live authorization gate; no dependency on T063 |
| T063 | T056/T060/T061 establish validated fixed reports and accessible study materials; no dependency on T062 or provider authorization; serialize shared acceptance-record writes |
| T064 -> T065 -> T066 | T059..T063; perform correction cycles as necessary, no final pass while a gate is blocked |

Code changes can continue on independent browser tasks if T027 is blocked, but no dependent
PDF integration or complete feature-release claim is permitted. Pending human gates do
not justify marking tasks done. T064 correction work can begin as soon as a relevant defect
is found; the table's prerequisites apply to closing the final correction cycle.

## Parallel Execution Examples Per Story

- **US1**: After foundation, author T013 default rules, T014 chart grammar and T015 UI tests
  in parallel. Implement T016..T022 serially because their modules are shared.
- **US4**: Author T025 synthetic feasibility and T026 export/structural contracts in parallel;
  T027 can establish feasibility while US1 browser implementation proceeds in other files.
  Do not start PDF integration T028..T032 without its pass. Browser-only T033 can proceed
  after T020/T021 in a separate shared-file editing window.
- **US2**: Author T037 typed preference, T038 repository lifecycle and T039 UI-state tests
  in parallel; no production schema/UI edits overlap US4 work on the same files.
- **US3**: Author T047 distribution/period, T048 pair/weather and T049 rich UI/export tests
  in parallel. Shared builder/adapter integration T050..T055 remains serial.
- **Final**: T057 timing harness and T058 integrated offline scenarios can proceed in parallel
  after their prerequisites. T062 live/independent acceptance and T063 fixed-report study
  are independent branches after their respective material-readiness gates. They must not
  write the acceptance record concurrently; T066 requires genuine completion of both.

## Mandatory Export Checkpoint Selection

Use test-name tokens rather than adding pytest marker configuration. T026 names initial
export/structure scenarios `test_export_defaults_*`; T039 names preference scenarios
`test_export_preferences_*`. T049 puts rich-family export cases in its dedicated module
and names rich structure scenarios `test_export_rich_*`. Shared safety invariants remain
in the default group and are exercised again at every later checkpoint.

With `..\beon\Scripts\python.exe -m pytest`, use these exact path/selection arguments:

| Checkpoint | Mandatory export/structure selection |
|------------|--------------------------------------|
| T035 / US4 | `tests\integration\test_visual_exports.py tests\accessibility\test_visual_pdf_accessibility.py -k export_defaults` |
| T046 / US2 | `tests\integration\test_visual_exports.py tests\accessibility\test_visual_pdf_accessibility.py -k "export_defaults or export_preferences"` |
| T056 / US3 | `tests\integration\test_visual_exports.py tests\integration\test_visual_analytical_exports.py tests\accessibility\test_visual_pdf_accessibility.py` (no selection filter) |
| T059 / final | All collected `test_visual_*.py` modules listed in T059, without phase filters |

These selections supplement, not replace, each task's other required suites and actual
reader/visual assessments. Record collected, selected, deselected, skipped and passed/
failed counts. Zero selected tests or skipped required scenarios cannot pass a checkpoint.
Earlier checkpoints defer only explicitly named later-story groups; the final gate permits
no deferred or skipped mandatory scenario and must include all three export/structure groups.

## Requirement and Contract Allocation

| Source | Implementing tasks | Acceptance tasks |
|--------|--------------------|------------------|
| FR-001..004, FR-024..025 | T007..T011, T016..T020 | T005/T006, T013..T015, T023, T056/T059 |
| FR-005..009, FR-013..014, FR-026 | T016..T021, T040..T044 | T013/T014, T037..T039, T046/T059 |
| FR-010..012 | T050..T052, T054/T055 | T047..T049, T056/T060 |
| FR-015, FR-019, FR-031 | T012, T028/T032, T040..T045 | T006/T026, T038/T039, T046/T059 |
| FR-016..018, FR-020, FR-022 | T019, T027..T034, T045/T055 | T014/T026, T035, T056, T059..T061 |
| FR-021, FR-027..029 | T020/T032/T054/T055 | T049/T056, T058..T063/T066 |
| FR-023 | T022/T028/T034 | T025/T035, T057/T059 |
| FR-030 | T053..T055 | T048/T049, T056/T058/T060 |
| Visual Evidence contract | T007..T011, T016..T019, T043, T050..T053 | T005/T006/T013/T014/T037/T047/T048 |
| Presentation/export contract | T020..T022, T028..T034, T040..T045, T054/T055 | T015/T025/T026/T038/T039/T049/T057/T060/T061 |
| SC-001/002/009/010 | Exact shape/identity/precision/gap/threshold handling above | T002/T005/T013/T014/T047/T048/T056/T059 |
| SC-003/011 | Authoritative shared E2E/AQ inputs, no local redefinitions | T049/T058/T062 |
| SC-004/006 | Actual charts, complete PDF and web accessibility | T027/T033/T035/T060/T061 |
| SC-005 | Compatible saved views without analytical reruns | T037..T039/T046 |
| SC-007/008 | Real participants and separate measured baseline/fault evidence | T057/T063 |

## Implementation Strategy

1. Establish reviewer disposition and shared evidence contracts without widening analytics.
2. Deliver **US1 browser MVP** first: useful cards/categories/time/series/tables with exact
   evidence and explicit scope/limits. This is an incremental demonstration, not full 003.
3. Establish local tagged-PDF feasibility early with synthetic content; keep it independent
   of analytical/provider runs. Stop the exporter route if it cannot meet the contract.
4. Deliver US4 basic accessible exports, then US2 saved compatible selections and US3 rich
   evidence graphics, rerunning prior export/lifecycle contracts after each integration.
5. Complete independent numerical, actual visual/accessibility, integrated/live and real-
   participant gates separately. Document pending gates honestly; no configuration switch,
   mock interpretation, dependency install or checklist approval substitutes for them.

**Counts**: 66 tasks; setup 4, foundation 8, US1 12, US4 12, US2 10, US3 10,
cross-cutting 10. Story task IDs retain original spec numbering despite priority reordering.
