# Tasks: Natural-Language Exploration and Grouped Analysis

**Input**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md), [data-model.md](data-model.md), [contracts](contracts/), [quickstart.md](quickstart.md).
**Prerequisites**: Approved design, reviewer disposition of [exploration checklist](checklists/exploration.md), existing Python 3.12 application and source fixtures.
**Tests**: Required by FR-021/022/025/028 and SC-001 through SC-011. Write targeted failing assertions before corresponding implementation; retain existing V1 regression coverage.
**Organization**: Five user-story increments in specification priority order. Setup, foundation and US1-US3 T001-T035 are complete; T036-T070 remain pending. External evidence gates remain pending until actual evidence exists.

## Format and Path Conventions

`- [ ] T### [P?] [US#?] Description with exact workspace-relative paths`.
Paths below are relative to `interactive-airport-data-platform`, not its parent Git root. `[P]` permits only the explicitly independent tasks within a ready phase; it never overrides prerequisites. Shared production files must be changed serially.

This is task generation, not checklist evaluation. Do not mark reviewer-owned checklist items or implementation tasks complete merely because this document exists. Unresolved reviewer findings that materially affect requirements must be settled before affected implementation. Do not treat this task list as approval of new product decisions.

## Phase 1: Setup (Existing-Project Baseline)

**Purpose**: Establish isolated fixtures and reproducible baseline without replacing the existing package, identity, database or dependency stack.

- [X] T001 Record the targeted baseline commands, installed runtime/source identities and actual results in specs/002-natural-language-exploration/quickstart.md; use existing pyproject.toml tooling, run the documented smallest V1 suites, and do not install packages without a missing-dependency failure or manifest change.
- [X] T002 [P] Add synthetic immutable CSV fixtures for dates, joins, repeated destinations, missing measures, aircraft identity and source mutations under tests/fixtures/exploration/, with provenance explicitly distinguishing them from production coverage evidence.
- [X] T003 [P] Add independent CSV/set/date/Decimal/centered-sums oracle helpers in tests/exploration_oracles.py without importing production compiler, execution, catalog-calculation or metrics functions; preserve exact row identity and unrounded expectations.

**Checkpoint**: T001-T003 complete. Fixtures and oracle helpers are available; no feature capability is claimed.

## Phase 2: Foundational (Blocking Shared Contracts)

**Purpose**: Establish trusted types, bounded provider interpretation, snapshot context and report compatibility required by every story.

- [X] T004 [P] Add structural contract tests in tests/unit/test_exploration_contracts.py for the strict request, interpretation, result/report and provider types delivered by T006-T010, invalid finite values, unknown properties/IDs and provider projection equivalence; cover malicious executable-looking input as data, never instructions. Defer BrowsePage/ExportSelection constraints to T029-T031, detailed declaration semantics to T036/T039 and evaluation-record constraints to T060-T062; these later assertions are not part of the foundation pass gate.
- [X] T005 [P] Add legacy payload, foreign-owner, corrupt-version, no-first-section-proxy and content-creation/consent timing regressions in tests/integration/test_exploration_compatibility.py using existing V1 fixtures and isolated SQLite storage.
- [X] T006 Add strict request/section types in src/airport_analytics/models.py with "Application-generated random IDs; session binding never placed in prompts", revision "Positive integer; increments for new submitted interpretation/correction, never reused", question "Trimmed string, 1..2,000 Unicode code points; original submitted wording retained", sections "1..4 stable requested identities in original order after valid decomposition", snapshot_binding "Validated data hash and semantic context hash, or null before binding", and last_failure "Safe category/code; no provider body or credential content".
- [X] T007 Add trusted interpretation types in src/airport_analytics/models.py with interpretation_version "Literal `2`", family "overall_summary / grouped_summary / unique_entity_list / individual_records / ranking / category_comparison / historical_trend / period_change / distribution / numeric_relationship", population "flights / observed_origins / observed_destinations / observed_airlines / airport_reference", filters "Typed catalog filters; max 12, no contradictions; normalized values validated by field", grouping "Ordered distinct roles, max two; no redundant carrier/name or simultaneous date grains", denominator_basis "not_applicable / verified_calendar_days / observed_operating_days; alternative requires explicit selected choice", and display_rounding "null or explicit decimal places 0..12 and half_up; unspecified rounded daily mean means 0; no effect on stored calculation".
- [X] T008 Add result/section/report types in src/airport_analytics/models.py: "Every variant has `result_version=2`"; grain "scalar / flight / entity / category / date / week / month / weekday / bin / flight_pair / origin_hour; recorded-date calendar, Monday week start"; absence "no_matching_records / no_known_values / no_verified_days / insufficient_pairs / constant_axis / unknown_capacity"; SectionOutcome "completed(result) / valid_empty(evidence) / failed(safe category/message)"; report_version "Literal `2`; absent discriminator means legacy V1, never guessed from rows"; parent_report_id "Optional previous report ID; link only, never ownership inheritance"; completeness "complete / incomplete; empty valid sections count as completed"; sections "1..4 ordered requested section identities, saved interpretations, definitions, bounded evidence and outcomes"; acknowledgement "Required for incomplete save/export; analyst/session, report revision, exact failed-section IDs and acknowledgement UTC time".
- [X] T009 Define the closed operation/measure/dimension/unit/additivity compatibility catalog in src/airport_analytics/data/catalog.py from contracts/interpretation.md section 2 and the spec analytical table; retain reference grain requirements, typed comparison/bin/pair options, field provenance enums and source/code ordering.
- [X] T010 Add the authoritative provider IntentProposalV2 JSON schema in specs/002-natural-language-exploration/contracts/intent.schema.json and enforce it in src/airport_analytics/analytics/plan_schema.py; implement intent_version2, status proposed/needs_clarification/unsupported/requires_selection, 0..4 proposal sections with status-specific cardinality, at most12 final predicates, max100 filter-list items, 2..8 offered choices or explicitly open ambiguity, and additionalProperties:false everywhere.
- [X] T011 Update src/airport_analytics/analytics/model_client.py with versioned provider schema projections and minimal approved interpretation context; one initial call per composite, no hidden repair/fallback/per-section calls, no result rows/private-history context, and existing disclosure/reservation/settlement/tracing/free-quota gates on every actual dispatch.
- [X] T012 Add typed compiled-purpose query objects and SELECT/owned-CTE support in src/airport_analytics/analytics/query_compiler.py and src/airport_analytics/analytics/execution.py; replace last-LIMIT-parameter rewriting/prefix-only assumptions with application-owned query kinds, bound parameters, declared output schemas, shared snapshot lock and configured timeout.
- [X] T013 Add versioned report dispatch/common section adapters in src/airport_analytics/history/repository.py and src/airport_analytics/reports/rendering.py; preserve V1 reads, no destructive payload migration, owner-scoped SQLite operations, one parent retention slot, explicit corrupt/unknown-version errors and no fabricated first-section proxy.
- [X] T014 Add semantic context hashing in src/airport_analytics/data/loader.py and src/airport_analytics/analytics/execution.py over snapshot, declaration status/content, unit/catalog/alias/rule versions; preserve original snapshot evidence and invalidate continuation/recomputation when either source or context changes.

**Checkpoint**: T004-T014 complete and targeted regression tests pass. Production UI remains gated until a usable story is integrated.

**Executed foundation checkpoint**: Full suite `python -m pytest -q`: **242 passed, 1 skipped** (live-provider acceptance/latency requires operator authorization). Ruff and patch whitespace checks passed. V2 history is readable without a legacy first-section proxy; V2 generation, exports, sharing and refinement remain gated pending their story integrations. Provider results above are mocked, not live acceptance. Coverage files are hashed as unverified until T039 supplies semantic validation.

## Phase 3: US1 - Ask Ordinary Summary and Grouped Questions (Priority: P1, MVP)

**Goal**: Ordinary unambiguous wording produces correct scalar/grouped answers and visible editable interpretations without requiring internal IDs.
**Independent test**: Independent paraphrases resolve expected measure, population and grouping; grouped distinct counts reconcile to source sets, and an explicit all-origin follow-up removes only origin scope.

### Tests

- [X] T015 [P] [US1] Add paraphrase/default/compatible-grouping contract cases in tests/unit/test_exploration_interpretation.py, including global versus per-origin distinct counts, fresh scope, explicit all-origin follow-up, unsupported dimension pairs and invalid entities; assert unresolved proposals cause no analytical query.
- [X] T016 [P] [US1] Add independently calculated scalar/grouped/route coverage cases in tests/integration/test_exploration_summaries.py and basic V2 question-form/history AppTest cases in tests/browser/test_exploration_summary_ui.py; include empty/unavailable distinctions, unknown reference names and one-section V2 shared-summary/FAQ compatibility with owner, original-session consent, pre-grant exclusion and withdrawal regressions.

### Implementation

- [X] T017 [US1] Implement deterministic code/name/approved-alias resolution in src/airport_analytics/analytics/entity_resolution.py and versioned alias data in src/airport_analytics/data/entity_aliases.json; exact codes precede normalized names, spelling candidates require confirmation, preserve code identity and observed/reference-only status, and restrict the NYC region alias to explicit origin-region wording.
- [X] T018 [US1] Implement V2 proposal-to-interpretation resolution in src/airport_analytics/analytics/interpretation.py with fresh all-observed-origin/all-recorded-date defaults, compatible one/two-role grouping, app-owned definitions/IDs, requested versus observed scope and provenance "explicit / correction / clarification / inherited / default"; never resolve an invalid entity by broadening scope.
- [X] T019 [US1] Replace phrase-only inheritance in src/airport_analytics/analytics/follow_up.py with validated typed add/replace/remove edits for explicit target sections, preserving compatible fields and dropping incompatible family fields; retain V1 behavior through the compatibility adapter and reset listing position.
- [X] T020 [US1] Compile and reconcile scalar/grouped measures, exact available/selected groups and bounded route evidence in src/airport_analytics/analytics/query_compiler.py and src/airport_analytics/analytics/metrics.py; recompute distinct sets at requested grain and preserve unmatched reference categories, known/missing counts and source populations before output limits.
- [X] T021 [US1] Produce one-section V2 outcomes and deterministic narratives in src/airport_analytics/reports/generation.py; reject invalid/ambiguous/unsupported proposals before main queries, retain valid-empty/unavailable evidence, and keep every number application-derived.
- [X] T022 [US1] Wire labelled interpretation summary/edit Apply/Cancel, fresh versus explicit follow-up submission, safe result/empty/status views, one-section persistence/history/reopen and existing per-section CSV/table-PDF adapters in app.py, src/airport_analytics/reports/rendering.py and src/airport_analytics/reports/export.py; preserve V1 UI/export and FAQ callback behavior, and create a new analytical revision only on Apply.

T022 also includes one-section V2 shared-summary production through the version-aware adapter in src/airport_analytics/history/repository.py and src/airport_analytics/consent/service.py: preserve original creation/session consent eligibility, pre-grant exclusions, withdrawal and existing shared-artifact retention. This compatibility is part of the US1 completion gate, not deferred to US5. T016 covers its regressions.

**Checkpoint**: US1 is a local unambiguous-summary MVP, not full 002 or integrated 003 release. Ambiguous inputs stay safely unresolved until US2.

Verified: full regression **275 passed, 1 skipped**; see the [executed US1 checkpoint](quickstart.md#executed-us1-summary-checkpoint). The summary workflow is enabled by default; V1 remains available by turning off the V2 toggle. Mock interpretation tests are not live paraphrase-accuracy acceptance.

## Phase 4: US2 - Resolve Ambiguity Without Rewriting (Priority: P1)

**Goal**: Focused choices/free text preserve resolved scope, with bounded, isolated correction and truthful provider errors.
**Independent test**: An ambiguous request remains nonexecuting until a valid answer; cancelled/stale/cross-session answers cannot change it; the third unresolved answered turn leads to guided correction.

### Tests

- [X] T023 [P] [US2] Add pure state-transition and stale-event tests in tests/unit/test_exploration_state.py covering every state, request/revision/section/question binding, answered_turns "0..3", source/provider faults, corrected revisions and no unintended execution.
- [X] T024 [P] [US2] Add labelled-choice/free-text/structured-correction/cancel/sign-out AppTest cases in tests/browser/test_exploration_clarification_ui.py, including retained FAQ wording and provider failure without consuming a clarification turn.

### Implementation

- [X] T025 [US2] Implement pure session-only transitions in src/airport_analytics/analytics/request_state.py for state "unresolved / clarification_pending / guided_correction / resolved / executing / completed / incomplete / failed / cancelled / superseded", field-preserving semantic choices, answered_turns "0..3", stale binding rejection before call/turn consumption, and cancellation/supersession without a permanent transcript.
- [X] T026 [US2] Resolve locally selected choices and typed corrections without model calls in src/airport_analytics/analytics/interpretation.py; send free-text clarification only through the gated client when necessary, retain resolved fields and classify ambiguity/unsupported/invalid scope separately from operational failures.
- [X] T027 [US2] Integrate pending clarification and guided correction in app.py and src/airport_analytics/reports/generation.py; one focused ambiguity in request order, free text "Trimmed string, 1..2,000 Unicode code points; original submitted wording retained", third-turn correction/restart/cancel, current widget values, accessible notices and no automatic retry/provider switch.
- [X] T028 [US2] Extend tests/integration/test_model_failure_modes.py, tests/unit/test_budget.py and tests/integration/test_tracing_privacy.py for every clarification dispatch, invalid provider output, uncertain paid acceptance across restart/month, explicit permitted retry and content-free diagnostics; preserve existing authorization and cost uncertainty blocks.

**Checkpoint**: P1 analyst journey supports both unambiguous summaries and assisted resolution. Flight-browsing choices become complete when US3 is available.

Verified offline: **307 passed, 1 skipped** overall; **78 passed** in the focused US2/provider/budget/tracing suite. See the [US2 checkpoint](quickstart.md#executed-us2-clarification-checkpoint). Multi-section requests can retain focused clarification state, but composite execution remains explicitly blocked until US5. Invalid provider output offers explicit retry/typed correction instead of inventing ambiguity or a hidden repair call.

T028 must also distinguish content-free operational telemetry from optional content-bearing LangSmith traces under evidence-and-persistence.md section 6: assert that disabled tracing emits no content-bearing trace, enabled tracing retains its accurate disclosure/acknowledgement/budget gates, and ordinary diagnostics remain redacted regardless of tracing configuration.

## Phase 5: US3 - Explore Entities and Individual Records (Priority: P2)

**Goal**: Distinguish unique entity populations from records and aggregates, with exact totals, stable pages and honest bounded downloads.
**Independent test**: Unique lists match independent sets; three consecutive pages equal source-ordered slices without duplicate/missing IDs; exports disclose exact selected/total counts at 9,999/10,000/10,001 rows.

### Tests

- [X] T029 [P] [US3] Add independent entity-list/flight-page/count/order/source-change cases in tests/integration/test_exploration_browsing.py for default100 and sizes25/50/100/500, supported sort tie IDs, empty/out-of-range pages, resets and reference-only populations; assert the BrowsePage field constraints and binding rules from data-model.md section 6 before T031 implementation.
- [X] T030 [P] [US3] Add single-section CSV null/escaping/metadata, listing allocation/confirmation and missing-historical-source regressions in tests/integration/test_exploration_listing_exports.py; reconcile source identities, not only download byte counts, and assert ExportSelection field constraints, allocation limits and confirmation invalidation from data-model.md section 6 before T031 implementation.

### Implementation

- [X] T031 [US3] Add BrowsePage/ExportSelection types in src/airport_analytics/models.py with "page_size in {25,50,100,500}", "page_index (1-based)", "total_pages (0 when empty)", owner/session/request/section/scope/order/snapshot/context binding, exact totals and "Combined listing rows<=10,000; aggregate selected rows<=500/section independently"; scope changes invalidate confirmations.
- [X] T032 [US3] Compile exact entity lists, flight matching counts and bounded deterministic pages in src/airport_analytics/analytics/query_compiler.py; distinguish observed origins/destinations/airlines from explicit airport-reference scope, enrich without fan-out, append unique source ID tie-breakers and share identical count/page predicates.
- [X] T033 [US3] Implement snapshot/context-checked continuation and explicit restart in src/airport_analytics/analytics/execution.py; page-size/filter/sort changes reset page1, out-of-range requests notify/reset and historical-row unavailability disables browsing rather than substituting current rows.
- [X] T034 [US3] Implement explicit bounded listing exports in src/airport_analytics/reports/export.py with <=10,000 rows/file, full precision, stable ordering, UTF-8 BOM, reversible text-formula escaping, reserved metadata columns/null markers and empty/failure metadata; require partial confirmation and build complete bytes before download.
- [X] T035 [US3] Wire entity/flight views, population labels, exact page positions/totals, paging reset/restart and listing export confirmation in app.py and src/airport_analytics/reports/rendering.py; no model call on paging/download, no one-page full population and no arbitrary numeric chart for listings.

**Checkpoint**: US3 is independently numerically verifiable on synthetic/validated snapshots and does not depend on automatic charts.

Verified offline: **327 passed, 1 skipped** overall; **20 passed** in the focused browsing/export/UI suites. Listing identities reconcile to independent source sets/slices, including three pages at each supported size and export boundaries 9,999/10,000/10,001. Saved-preview downloads remain separate from explicitly prepared bounded exports. Missing/changed sources disable continuation without removing saved evidence. Restart copies the question into the normal form and does not dispatch until Generate report is explicitly selected. Single-section valid-empty CSVs carry metadata only; mixed failed-section bundles remain T058 (all-failed reports are never persistable). Catalog 2.1 fingerprints the new listing definitions; historical evidence stays readable, while stale-context recomputation is blocked.

## Phase 6: US4 - Compare, Rank, Explore Time and Distributions (Priority: P2)

**Goal**: Complete the ten analytical families plus AQ-01 through AQ-10 using defensible grain, coverage, weighting and evidence bounds.
**Independent test**: Each supported definition/dimension and every AQ numeric fixture matches the independent oracle before presentation, including unknown dates, nulls, ties, bins and origin-hour weather evidence.

### Tests

- [X] T036 [P] [US4] Add coverage/date/calendar/daily-distinct/capacity contract and numerical cases in tests/integration/test_exploration_daily_metrics.py using tests/exploration_oracles.py; include applicable/missing/stale/conflicting/gap declarations, per-origin/all-origin scope, verified zero versus observed-only dates, weekday denominators, half-up boundaries and unknown seat contributions.
- [X] T037 [P] [US4] Add rank/trend/period/bin/pair boundary cases in tests/integration/test_exploration_analytical_forms.py; include499/500/501 groups, top501 rejection, tied maxima, month-end/leap dates, negative/zero baseline,99/100/101 bins and5,000/5,001 pairs.
- [X] T038 [P] [US4] Add weather/capacity/aircraft independent identity and arithmetic cases in tests/integration/test_exploration_airport_questions.py, with repeated weather hours, n<3/constant variables, four missing partitions, unmatched references, reused model labels and distinct-aircraft versus flight-frequency contrasts.

### Implementation

- [X] T039 [US4] Validate configured local declarations in src/airport_analytics/data/coverage.py against contracts/coverage.schema.json plus exact snapshot/provenance/reviewer/check evidence, known origins, valid nonoverlapping inclusive intervals and contained gaps; add optional local-path configuration in src/airport_analytics/config.py and .env.example, with no network fetch or fabricated default declaration.
- [X] T040 [US4] Derive CalendarEligibility in src/airport_analytics/data/coverage.py and src/airport_analytics/data/loader.py with requested/verified/unknown/observed/eligible/per-weekday counts, combined-origin completeness and common airline date sets; surface stale/malformed declarations as safe unknown-coverage warnings, not verified status.
- [X] T041 [US4] Validate finite measurement/reference seats and local transformed weather-unit provenance in src/airport_analytics/data/validation.py and src/airport_analytics/data/catalog.py; negative seats/invalid numerics fail explicitly, absent unit provenance blocks the affected weather calculation with correction/removal rather than disabling unrelated analytics.
- [X] T042 [US4] Implement application-owned date spines, daily distinct->equal-day/weekday means and airline known seats->daily totals->common-date means in src/airport_analytics/analytics/multi_stage.py; verified no-flight days are zero, unknown contributions stay unknown, observed-day alternatives require an explicit analytical revision and no verified denominator yields unavailable.
- [X] T043 [US4] Implement chronological daily/Monday-week/month aggregation and approved period-change compilation in src/airport_analytics/analytics/multi_stage.py; inclusive dates, adjacent equal-day previous windows/calendar shifts, clamping/exposure flags, same population, signed relative formula and explicit zero/unavailable/negative-baseline handling.
- [X] T044 [US4] Implement metric ranking, positive/net departure-delay totals and manufacturer-qualified aircraft frequencies in src/airport_analytics/analytics/query_compiler.py and src/airport_analytics/analytics/multi_stage.py; defaulttop10, each/all<=500, stable code ties, exact omitted/cutoff/all-maxima disclosures and distinct observed tails unless flight activity is explicit.
- [X] T045 [US4] Implement anchored equal-width distribution templates and eligibility proposals in src/airport_analytics/analytics/multi_stage.py; delays15 minutes/distance250 miles, left-closed/right-open final upper>maximum, constant positive-width bin, intervening zero bins, missing reconciliation and smallest positive integer-multiple width proposal when >100 bins, never silent coarsening.
- [X] T046 [US4] Implement flight-pair and weather origin-hour pipelines in src/airport_analytics/analytics/multi_stage.py; same-flight approved variable pairs only, exact origin/hour collapse for four weather coefficients with n>=3/positive variances, explicit precipitation comparison grain, full pairs<=5,000 else complete<=20x20 density, constant-axis interval and disjoint missing/exclusion evidence; no flight-level Pearson, sampling, significance or regression.
- [X] T047 [US4] Execute main/support/count/pair-density purposes under bounded snapshot-aware orchestration in src/airport_analytics/analytics/execution.py; follow spec.md's evidence-bound table with one500-group primary pool, one separate500-row daily-support pool across all categories/collections and one separate500-row route pool per section, date/code-stable supporting order and exact omitted counts. Add multi-airline/origin pooled-bound assertions to tests/integration/test_exploration_daily_metrics.py; compute complete eligible populations before selection, avoid full-population Python fetch, preserve timeout and use source-bound prerequisite checks without producing unresolved report answers.
- [X] T048 [US4] Assemble typed AQ/result evidence and deterministic limitations in src/airport_analytics/analytics/metrics.py and src/airport_analytics/reports/generation.py; preserve full-precision numerators/denominators, exact ties/exclusions, unavailable reasons/provisional seat ranks and half-up display from exact daily count ratios.
- [X] T049 [US4] Wire analytical-form summaries, editable periods/bin proposals/observed-day alternatives and bounded exact evidence tables in app.py and src/airport_analytics/reports/rendering.py; preserve request meaning and expose weather coefficients/daily supports without pretending 003 charts or tagged PDFs are implemented.
- [X] T050 [US4] Extend src/airport_analytics/reports/export.py and tests/integration/test_exploration_analytical_forms.py for selected aggregate/daily/bin/pair-density exports, missingness/units/rounding/scope metadata and table-PDF parity; chart/PDF graphic and accessibility acceptance stays gated on003.

**Checkpoint**: Ten families and AQ numeric operations work independently of visual rendering. Real AQ interpretation remains a later live acceptance obligation.

## Phase 7: US5 - Several Related Analyses in One Report (Priority: P2)

**Goal**: One to four labelled independent sections share a snapshot, resolve before execution and retain truthful incomplete outcomes.
**Independent test**: Four sections with common/overridden scope, multiple clarifications and a runtime fault preserve all identities, gate execution and require exact failed-section acknowledgement before incomplete save/export.

### Tests

- [X] T051 [P] [US5] Add composite decomposition/shared-override/all-ready/no-silent-omission and runtime-failure contract cases in tests/integration/test_exploration_composites.py for1/4/5 sections, one weather panel as one section, explicit removal, all-failed and empty-valid outcomes.
- [X] T052 [P] [US5] Add parent retention/ownership/acknowledgement/consent-creation-time/bundle allocation cases in tests/integration/test_exploration_composite_storage.py; assert combined listing allocations<=10,000 and no partial artifact after export failure.
- [X] T053 [P] [US5] Add multiple pending section/target/all-sections/stale acknowledgement and incomplete-report UI cases in tests/browser/test_exploration_composite_ui.py, independent of actual provider calls.

### Implementation

- [X] T054 [US5] Extend src/airport_analytics/analytics/interpretation.py and src/airport_analytics/analytics/request_state.py for common explicit scope plus per-section overrides, stable ordered identities, explicit removal and >4 selection/confirmed partition; do not auto-submit additional reports or multiply weather-variable slots.
- [X] T055 [US5] Orchestrate every section's readiness before any main analytical query in src/airport_analytics/reports/generation.py; execute ready sections on one common immutable snapshot, retain completed/valid-empty/failed independently, no all-failed success report and no mixed-snapshot retry stitching.
- [X] T056 [US5] Persist complete/acknowledged-incomplete parent payloads and owner-scoped preference versions in src/airport_analytics/history/repository.py and src/airport_analytics/storage.py only if schema changes are necessary; retain one parent retention slot, original creation/session/consent eligibility, removed/failure identities and reject stale/foreign updates without destructive migration.
- [X] T057 [US5] Extend the one-section V2 shared-summary/FAQ compatibility completed in T022 to composite and acknowledged-incomplete reports in src/airport_analytics/consent/service.py, src/airport_analytics/consent/repository.py and src/airport_analytics/history/repository.py; preserve applicable original-session consent timing, incomplete failure notices, existing shared-artifact withdrawal/deletion lifecycle and no failure-as-answer publication.
- [X] T058 [US5] Build atomic composite CSV ZIP bundles with per-section files and manifest.json in src/airport_analytics/reports/export.py; explicit listing allocations total<=10,000, aggregates<=500/section, exact scope/status/metadata/escaping/null rules, acknowledgement plus partial confirmation when needed, and no download on technical failure.
- [X] T059 [US5] Wire ordered sections, targeted/all-section refinement, acknowledged incomplete saving/export, saved failure disclosures and section-owned preferences in app.py and src/airport_analytics/reports/rendering.py; preserve V1 history/downloads, disable unavailable historical paging and expose no preference that changes analytical evidence.

**Checkpoint**: Complete local002 composite functionality; automatic003 charts/PDFs and external release claims remain gated.

T052 must inject save/pruning failures and interrupted/stale preference updates; T056 must enforce atomic report insertion plus associated retention pruning and atomic version-checked preference updates under evidence-and-persistence.md section 5. Assert rollback preserves previously committed reports/preferences/evidence, no false save/update success, and actionable refresh/retry. T059 must retain unsaved results in the current session where possible without implying durability after session/process loss. Basic insertion/pruning atomicity also applies to US1's T022 save path; cover it in T005 before the US1 completion gate.

## Phase 8: Polish, Cross-Cutting Validation and Release Evidence

**Purpose**: Complete reproducible evaluation, cross-spec consistency, documentation and actual external gates. Tasks explicitly marked external may remain blocked; never invent evidence to complete them.

- [X] T060 Add CorpusCase/ReviewRecord/EvaluationRun validation in src/airport_analytics/models.py and corpus metadata under tests/fixtures/exploration/; first add evaluation-record field/constraint assertions from data-model.md section 8 in tests/unit/test_exploration_evaluation.py, then retain synthetic text/version/gold references, independent labels/agreement/disputes/adjudication/freeze provenance, run versions/settings/timing/case IDs/safe comparison categories/actual absolute errors and no routine raw provider bodies or private text. These assertions are a Phase 8 gate, not part of T004.
- [ ] T061 Prepare separate development and candidate held-out sets under tests/fixtures/exploration/ with100 unambiguous cases (10/family),20 ambiguity/unsupported cases, AQ-01..10 with>=3 ordinary-language variants each and separate composites; ordinary wording contains no internal expected plans, exposed cases become development material and independent author/reviewer evidence is required for held-out claims.
- [X] T062 Implement deterministic typed semantic canonicalization and independent result scoring in src/airport_analytics/analytics/evaluation.py and tests/unit/test_exploration_evaluation.py; retain original12-case regression, exact discrete/null comparisons, finite tolerance abs(actual-expected)<=max(1e-9,1e-12*abs(expected)), every generated result including wrong-scope sections, and composite pass only when all requested sections pass.
- [X] T063 Extend the explicit opt-in evaluation CLI in src/airport_analytics/analytics/evaluation.py and specs/002-natural-language-exploration/quickstart.md with suite/version selection, frozen environment/source/context metadata, all attempted failures counted, >=90/100 and >=8/10 each family, all20 negative and allAQ gates, no retry stitching, actual error magnitudes and distinct cold/warm timings.

T063 additionally instruments source validation, interpretation, analytical execution, browser-ready tables and export generation separately in src/airport_analytics/data/loader.py, src/airport_analytics/analytics/model_client.py, src/airport_analytics/analytics/execution.py, app.py and src/airport_analytics/reports/export.py. Add focused timing/redaction assertions in tests/performance/test_exploration_stage_timings.py; document the measurement method in specs/002-natural-language-exploration/quickstart.md. Capture representative actual cold/warm stage baselines in specs/002-natural-language-exploration/acceptance-results.md with environment, source/context versions, safe correlation/category metadata and failures, never question/filter/entity/report content. Browser-ready measurement distinguishes server preparation from observed browser readiness. Chart-ready timing remains explicitly not-run until003. No numerical latency SLA or background-job requirement is introduced.
- [X] T064 Add shared E2E-01..09 analytical/evidence/saved/export consistency cases in tests/integration/test_exploration_shared_e2e.py and a dated record in specs/002-natural-language-exploration/acceptance-results.md; record002 components separately while003 graphics/PDF/accessibility are not ready, including the independent E2E-09 fault variant.
- [X] T065 Add keyboard/label/focus/status and isolated-session review coverage for new controls in tests/accessibility/test_exploration_controls.py and tests/browser/test_exploration_accessibility.py; document automated versus actual browser/assistive evidence and do not equate automation with WCAG compliance.
- [X] T066 Update README.md, QUESTION_GUIDE.md, QUICKSTART.md and specs/002-natural-language-exploration/quickstart.md for actual supported operations, coverage limits, multi-section interactions, paging/downloads, V1 compatibility and003 boundaries; run focused tests/lint/format then broader suites only as warranted, recording exact outcomes without historical-result substitution.
- [ ] T067 Obtain two independent gold reviewers/adjudication and freeze approved corpus/source/context versions in tests/fixtures/exploration/review-records.json; external gate, never label agent-authored self-review as independent human acceptance.
- [ ] T068 Run explicitly authorized live candidate evaluation only after T063 and T067 and actual provider/terms/quota readiness, recording safe run evidence in specs/002-natural-language-exploration/acceptance-results.md; blocked/unavailable/incomplete runs cannot pass and no automatic retries or fabricated credentials are permitted.
- [ ] T069 Conduct the five-real-analyst formative study from SC-006 and record per-task first-unaided/assisted results and limitations in specs/002-natural-language-exploration/acceptance-results.md; external gate requiring>=4/5 each task, five new participants after material fixes/failed rounds and no population-wide claim.
- [ ] T070 Complete actual joint002/003 E2E/numeric/visual/PDF/export/accessibility evidence and reconcile existing001 retention/provider/study gates in specs/002-natural-language-exploration/acceptance-results.md and specs/003-visual-reporting/spec.md; external/dependent gate, retain dated failures/not-run states and withhold integrated release approval until both features satisfy shared criteria.

## Dependencies & Execution Order

### Implementation status (2026-10-18 UTC)

65/70 tasks are checked. Local US4/US5 implementation and Phase 8 tooling are
verified by the dated [acceptance record](./acceptance-results.md).
T061 remains incomplete: development metadata is not the required independently
authored candidate corpus/gold. T067 requires that corpus and two independent
human reviewers/adjudication; T068 additionally requires fresh live-run
authorization/provider readiness; T069 requires five real analysts; T070 requires
actual 003 integration and the outstanding 001 release evidence. Do not check
these tasks on the strength of synthetic tests or agent self-review.

### Phase and story graph

```text
Setup T001..T003
  -> Foundation T004..T014
     -> US1 T015..T022
        -> US2 T023..T028
           -> US3 T029..T035 ----+
           -> US4 T036..T050 ----+-> US5 T051..T059
                                    -> Local validation T060..T066
                                    -> Independent freeze T067
                                       -> Live acceptance T068
                                       -> Analyst study T069
                                          -> Joint release T070 (+003 +001 external gates)
```

US2 uses US1's interpreter/generator/UI. US3 and US4 depend on US1/US2 and are independently testable with fixtures; neither needs the other's results. Their production edits to models/compiler/execution/app/export overlap, so implement serially or coordinate explicit file ownership. US5 integrates the already usable individual operations; it requires both US3 and US4 to demonstrate the shared four-section journey.

### Task-level prerequisites within phases

- T002 and T003 may run together after baseline environment isolation; tests must consume both finished fixture/oracle helpers.
- T004 and T005 are independent test definitions before foundational implementation. T006 -> T007 -> T008 -> T009 -> T010 -> T011 -> T012 -> T013 -> T014 is the safe shared-file integration order; make their targeted assertions pass before foundation completion.
- Within each story, marked test-authoring tasks share only completed prerequisites and can proceed together. Production tasks follow listed order; do not mark later production tasks parallel merely because their test fixtures differ.
- T028 requires T025-T027; US3/US4 start only after the P1 gate. T036-T038 depend on existing fixture/oracle helpers, not unfinished metric implementations.
- T051-T053 depend on finished individual-story interfaces, not on each other. T054-T059 integrate sequentially.
- T060 -> T061 -> T062 -> T063 -> T064 -> T065 -> T066 is the safe local completion sequence. Corpus development work may be prepared earlier but cannot be frozen or claimed independent without T067.
- T067 follows candidate-suite preparation; T068 requires completed local scoring and independent freeze. T069 requires usable feature/study tasks and real participants. T070 requires all relevant prior evidence plus003 and applicable001 approvals.
- Review findings, unavailable source provenance, weather-unit evidence, provider terms/quotas, real reviewers/participants and003 readiness are explicit blockers, not permission for silent substitutes.

## Parallel Execution Examples

Only test/fixture authoring shown below is marked parallel; each example starts after its phase prerequisites are satisfied.

| Story / phase | Independent work pair or group | Join before |
|---------------|--------------------------------|-------------|
| Setup | T002 synthetic CSVs + T003 independent oracle helpers | T004 and story fixture use |
| Foundation | T004 strict contracts + T005 legacy persistence regressions | T006 |
| US1 | T015 interpretation cases + T016 summary/UI cases | T017 |
| US2 | T023 pure state cases + T024 clarification UI cases | T025 |
| US3 | T029 browsing cases + T030 CSV/metadata cases | T031 |
| US4 | T036 daily/coverage + T037 analytical forms + T038 weather/aircraft cases | T039 |
| US5 | T051 orchestration + T052 persistence/export + T053 UI cases | T054 |

Do not run overlapping production edits or live paid inference merely for parallel speed. A test-writing task can initially fail by design; validate only after its implementation prerequisites are complete.

## Requirement and Contract Coverage

| Requirement group | Primary tasks |
|-------------------|---------------|
| FR-001-005, FR-009, FR-019, FR-026 | T004-T022 |
| FR-006-008, FR-025 | T019, T023-T028 |
| FR-010-013, FR-030 | T029-T035, T044, T050, T058 |
| FR-014-018, FR-029 | T036-T050 |
| FR-020, FR-027 | T005, T008, T013-T014, T022, T056-T059 |
| FR-021, FR-028 | T060-T063, T067-T068 |
| FR-022, FR-031 | T064-T066, T068-T070 |
| FR-023-024 | T051-T059 |
| FR-032-037 / AQ-01..10 / SC-010-011 | T036-T050, T061-T063, T067-T068 |
| SC-001-003 | T060-T063, T067-T068 |
| SC-004, SC-007-009 | T023-T050, T051-T053, T062 |
| SC-005-006 | T064, T069-T070 |
| Interpretation contract | T004, T006-T011, T015, T018-T019, T023-T027, T054 |
| Coverage contract/schema | T014, T036, T039-T042 |
| Evidence/persistence contract | T005, T008, T013, T016, T020-T022, T030-T035, T037-T050, T052, T056-T059, T064 |
| Data-model constraints | T006-T010, T025, T031, T039-T040, T048, T056, T060 |

## Implementation Strategy

1. **MVP first**: Finish setup/foundation and US1 for a locally demonstrable ordinary-summary/grouping increment. Keep unsupported/unresolved forms safely blocked. No claim that this closes full002 or003.
2. **Usable P1 increment**: Add US2 before advertising assisted language exploration. Retain draft input safely and preserve every provider gate.
3. **Incremental breadth**: Add US3 and US4 with independent evidence. Release small local increments only with accurate documentation of still-unavailable operations; do not claim AQ coverage before all definitions/ordinary-language acceptance are complete.
4. **Composite integration**: Add US5 after individual operations work, then verify partial-outcome/consent/export lifecycle rather than merely concatenating tables.
5. **Measured acceptance**: Complete local regression/scoring, independent gold freeze, authorized live runs and real analyst study. Join003 evidence only when actually available; retain001 external gates.

## Notes

- T001-T035 are complete (35/70); T036-T070 remain pending. `[P]` is scheduling guidance, not completion or approval.
- Reviewer-owned checklist markers remain untouched. `/speckit-implement` must observe its checklist gate; generating tasks does not waive it.
- Use existing package managers/tests/formatters; no new runtime dependency, service, queue or migration framework is planned.
- Preserve dirty unrelated work. Amend design/product decisions only with explicit reviewer disposition rather than silently treating a task description as a spec change.
- Update actual evidence records during implementation; never insert passing dates, analyst sessions, live-model outcomes, source coverage or owner approvals without evidence.
