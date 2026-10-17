# Tasks: Interactive Airport Data Platform

**Input**: Design documents from `specs/001-airport-analytics-platform/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`

**Organization**: Tasks are grouped by the five user stories in priority order. Acceptance and
failure-path tests are included because the specification defines testable acceptance scenarios
and measurable correctness, privacy, budget, and isolation criteria.

## Phase 1: Setup

**Purpose**: Initialize the Python application and its shared project structure.

- [X] T001 Create `pyproject.toml` for Python 3.12 with Streamlit, DuckDB, LangChain core and Ollama integration, Pydantic, Plotly, SQLite support, pytest, and Streamlit AppTest dependencies.
- [X] T002 [P] Create the application package, test directories, and package entry point in `src/airport_analytics/__init__.py`, `src/airport_analytics/`, `tests/unit/`, `tests/integration/`, `tests/browser/`, and `app.py`.
- [X] T003 [P] Add environment-variable configuration examples and secret-handling guidance in `.env.example` and `README.md`; do not include API keys, provider credentials, or real identity-provider secrets. At implementation start and after each implementation milestone, record authoritative Copilot/session token usage in `read_me.md`; never estimate or invent usage figures.
- [X] T004 Configure formatting, linting, and test discovery in `pyproject.toml`.

## Phase 2: Foundational

**Purpose**: Complete shared identity, data, persistence, and safety foundations before story work.

- [X] T005 Implement typed application settings, provider selection, model token ceilings, and secret loading in `src/airport_analytics/config.py`; reject missing credentials for a configured hosted provider and reject unknown provider identifiers.
- [X] T006 Implement the versioned closed dataset and metric catalog in `src/airport_analytics/data/catalog.py`, including only source-verified tables, field types, filterable fields, dimensions, metrics, and declared join relationships.
- [X] T007 Implement source snapshot loading and validation in `src/airport_analytics/data/loader.py` and `src/airport_analytics/data/validation.py`; record per-file SHA-256, row count, headers, schema version, missingness, and join-key coverage before analytics is enabled.
- [X] T008 Implement OIDC analyst identity resolution and server-side authorization in `src/airport_analytics/auth.py`; derive the stable analyst key from issuer and subject, never mutable email, and require ownership checks on private resources.
- [X] T009 Implement SQLite connection management, schema initialization, and transactional repository helpers in `src/airport_analytics/storage.py`; keep report, consent, shared-reuse, and model-usage records locally persisted.
- [X] T010 [P] Implement common typed error categories and user-safe error presentation in `src/airport_analytics/errors.py`; distinguish invalid question plans, unsupported analysis, provider failure, exhausted budget, and unavailable datasets without leaking secrets.
- [X] T011 [P] Create shared Pydantic types for dataset snapshots, analysis plans, validated results, and report scope in `src/airport_analytics/models.py`, consistent with `data-model.md` and `contracts/analysis-plan.schema.json`.
- [X] T012 Implement deployment-wide monthly spend reservations in `src/airport_analytics/analytics/budget.py` and SQLite schema in `src/airport_analytics/storage.py`; cap metered model and enabled tracing charges at USD 10 per UTC calendar month, atomically count in-flight reservations, reject unbounded paid calls, and reconcile settled usage.
- [X] T013 Implement explicit model-provider policy and provider-use disclosure state in `src/airport_analytics/analytics/provider_policy.py`; distinguish provider data-use disclosure from FAQ/report reuse consent and do not silently switch providers.
- [X] T014 Implement a LangChain model adapter interface and explicit Ollama/local plus hosted-provider construction in `src/airport_analytics/analytics/model_client.py`; enforce configured provider identity and return provider usage metadata when available.
- [X] T015 Implement LangSmith tracing configuration in `src/airport_analytics/observability/tracing.py`; tracing must be disabled by default, and enabling it must require explicit operator configuration and a disclosure flag.

**Checkpoint**: Shared project, identity, dataset catalog, persistence, provider selection, and budget foundations are ready.

## Phase 3: User Story 1 - Ask a Question and Get a Report (Priority: P1) 🎯 MVP

**Goal**: Let an analyst ask a supported natural-language question and receive a relevant, evidence-grounded report with safe model use.

**Independent Test**: With the validated source snapshot and a configured model, ask clear questions about connectivity, airline delays, and aircraft activity. Verify the model returns a valid plan, application-compiled queries match independently calculated results, reports identify scope and metric definitions, provider disclosure precedes hosted calls, and the shared budget cannot be exceeded.

### Tests for User Story 1

- [X] T016 [P] [US1] Create a fixed 12-question golden corpus (three supported questions per analysis area) with independent expected metrics and scope in `tests/fixtures/golden_questions.json` and `tests/fixtures/golden_expected_results.json`; add exact-result integration coverage in `tests/integration/test_question_reports.py`.
- [X] T017 [P] [US1] Add structured-plan contract and rejection tests for unknown metric/dimension/filter, invalid operator/value, excessive row limit, clarification, and unsupported status in `tests/unit/test_analysis_plan.py`; add empty, non-text, whitespace-only, 2,001-code-point-after-trimming, and maximum-length question tests in `tests/unit/test_question_validation.py`, proving invalid input is rejected before model invocation or budget reservation.
- [X] T018 [P] [US1] Add query-compiler tests proving SQL-shaped model output, unknown identifiers, and injection-shaped filter values cannot produce executable arbitrary SQL in `tests/unit/test_query_compiler.py`.
- [X] T019 [P] [US1] Add budget tests for shared-cap enforcement, concurrent reservation transactions, UTC month rollover, unbounded price, provider fees/taxes/FX, late invoices attributed to request-acceptance month, partial responses, failed-call reconciliation, and usage accounting in `tests/unit/test_budget.py`; prove automatic retry occurs only on provider-confirmed non-acceptance, uncertain reservations remain held until reconciliation, and reconciled charges above reservation are recorded and surfaced while further paid calls are blocked when the cap is exhausted.
- [X] T020 [P] [US1] Add provider-policy tests proving provider disclosure occurs before each provider's first hosted call and is separate from reuse consent in `tests/unit/test_provider_policy.py`.
- [X] T021 [P] [US1] Add tests that LangSmith tracing is disabled by default and cannot start without operator configuration and disclosure in `tests/unit/test_tracing.py`.

### Implementation for User Story 1

- [X] T022 [US1] Implement analysis-plan parsing and JSON Schema validation in `src/airport_analytics/analytics/plan_schema.py` using `contracts/analysis-plan.schema.json`; reject extra fields and validate identifiers against `src/airport_analytics/data/catalog.py`.
- [X] T023 [US1] Implement the deterministic plan-to-DuckDB compiler in `src/airport_analytics/analytics/query_compiler.py`; compile only allowlisted metrics, dimensions, joins, filters, and bounded sort/row limits into parameterized read-only `SELECT` queries.
- [X] T024 [US1] Implement read-only DuckDB dataset registration and bounded query execution in `src/airport_analytics/analytics/execution.py`; apply query timeout/result limits and preserve missing values rather than treating them as zero.
- [X] T025 [US1] Implement LangChain structured analysis-plan generation in `src/airport_analytics/analytics/model_client.py`; accept only a non-empty trimmed plain-text question of at most 2,000 Unicode code points, pass only that question, minimal active structured follow-up context, schema/metric glossary, and plan schema, never raw source rows, credentials, analyst identity, saved/private report history, or database tools.
- [X] T026 [US1] Implement hosted-call budget reservation, provider disclosure gating, usage settlement, and explicit provider-failure handling in `src/airport_analytics/analytics/model_client.py` and `src/airport_analytics/analytics/budget.py`; include directly attributable provider fees/taxes and FX charges, attribute costs to the accepted-request UTC month, reconcile partial responses, retry only on provider-confirmed non-acceptance, retain uncertain reservations, and on cap exhaustion offer an explicit local switch without automatic fallback.
- [X] T027 [P] [US1] Implement deterministic metric definitions, unit/population descriptions, missing-value handling, matched/unmatched join counts and coverage, and analytical-term glossary in `src/airport_analytics/analytics/metrics.py`.
- [X] T028 [US1] Implement evidence-grounded report generation in `src/airport_analytics/reports/generation.py`; generate narrative only from validated aggregate results and metric definitions, and verify numeric claims against those results.
- [X] T029 [US1] Implement deterministic chart/table selection and report rendering in `src/airport_analytics/reports/rendering.py`; choose visuals from validated result shape and show data period, material scope, sample counts, matched/unmatched join coverage, and limitations.
- [X] T030 [US1] Implement the initial authenticated question/report page in `app.py`; collect natural-language questions, display a focused clarification or unsupported-data explanation when needed, and render a complete report only after a valid analysis plan executes.
- [X] T031 [US1] Implement provider selection and provider-use disclosure in the question flow in `app.py`; disclose the selected hosted provider and product-improvement terms before its first hosted request and make the disclosure distinct from FAQ/reuse consent.
- [X] T032 [US1] Implement monthly budget status, hosted-call blocking, and analyst-initiated local-provider switch in `app.py`; when the deployment cap is exhausted, stop hosted requests and either switch only after explicit analyst action or explain hosted service resumes next UTC month.

**Checkpoint**: User Story 1 provides a safe, independently verifiable question-to-report MVP.

## Phase 4: User Story 2 - Refine a Report with a Follow-Up Question (Priority: P2)

**Goal**: Let analysts refine a report using conversational context and make updated scope explicit.

**Independent Test**: Generate a report, ask a follow-up that adds or changes a supported airport, airline, or date constraint, and verify the new validated plan and report reflect the intended active scope without silently preserving conflicting filters.

### Tests for User Story 2

- [X] T033 [P] [US2] Add follow-up tests for added, replaced, and contradictory date/airport/airline filters and visible active scope in `tests/integration/test_follow_up_questions.py`.
- [X] T034 [P] [US2] Add tests that follow-up context sent to a hosted model is bounded and excludes private report history beyond the minimum necessary current context in `tests/unit/test_follow_up_context.py`.

### Implementation for User Story 2

- [X] T035 [US2] Implement follow-up context construction and scope replacement rules in `src/airport_analytics/analytics/follow_up.py`; retain only relevant current question/plan context and resolve changed filters explicitly.
- [X] T036 [US2] Integrate follow-up planning, validation, query recompilation, and visible scope updates in `src/airport_analytics/reports/generation.py` and `app.py`; each follow-up must pass the same plan, provider disclosure, and budget checks as a first question.

## Phase 5: User Story 3 - Understand the Report (Priority: P2)

**Goal**: Help analysts inspect evidence, definitions, limitations, and export complete reports and result tables.

**Independent Test**: Review representative rate, average, and ranking reports; confirm population, numerator/denominator when relevant, period, units, sample counts, and limitations are clear; export a complete PDF and matching tabular CSV.

### Tests for User Story 3

- [X] T037 [P] [US3] Add tests for metric definitions, units, population, denominators, relevant analytical-term explanations, and result/narrative consistency in `tests/integration/test_report_evidence.py`.
- [X] T038 [P] [US3] Add PDF and CSV export-content tests, including full narrative/report sections and tabular result fidelity, in `tests/integration/test_report_exports.py`.

### Implementation for User Story 3

- [X] T039 [US3] Extend report composition in `src/airport_analytics/reports/generation.py` and `src/airport_analytics/reports/rendering.py` to include metric definitions, units, numerator/denominator where relevant, population, period, sample size, glossary explanations, and material limitations.
- [X] T040 [US3] Implement complete-report PDF export in `src/airport_analytics/reports/export.py`; include the report question, answer, metric definitions, visual/table context, provenance, and limitations.
- [X] T041 [US3] Implement result-table CSV export in `src/airport_analytics/reports/export.py`; serialize only the current report's tabular result data with stable headers and correct null handling.
- [X] T042 [US3] Add authenticated PDF/CSV export controls to `app.py`; verify report ownership before rendering or returning any export.

## Phase 6: User Story 4 - Keep Reports Private and Control Reuse (Priority: P2)

**Goal**: Provide analyst-private history capped at ten reports and explicit, reversible session consent for shared reuse.

**Independent Test**: Create reports for two analysts and verify each can access only their own latest ten. Decline consent, later opt in, withdraw, and re-enable during a session; verify only content created while consent is active is reused and already-reused material remains after withdrawal.

### Tests for User Story 4

- [X] T043 [P] [US4] Add cross-analyst authorization tests for report listing, detail lookup, deletion, and export in `tests/integration/test_report_ownership.py`.
- [X] T044 [P] [US4] Add consent-state transition tests for initial decline, later opt-in, withdrawal, re-enable, new session, and preserved prior reuse artifacts in `tests/integration/test_consent_transitions.py`.
- [X] T045 [P] [US4] Add report-history retention tests verifying only the ten newest private reports remain per analyst and private payloads beyond the cap are removed without deleting separately retained shared artifacts in `tests/integration/test_report_retention.py`.

### Implementation for User Story 4

- [X] T046 [US4] Implement private report and shared-reuse artifact repositories in `src/airport_analytics/history/repository.py`; enforce analyst ownership at every repository operation and retain only ten private reports per analyst.
- [X] T047 [US4] Implement append-only consent-event persistence in `src/airport_analytics/consent/repository.py`; record analyst/session, purpose, action, timestamp, and notice version.
- [X] T048 [US4] Implement session-scoped reuse consent state transitions in `src/airport_analytics/consent/service.py`; start disabled, permit later opt-in/withdrawal/re-enable, and reuse only content created during active consent.
- [X] T049 [US4] Implement shared artifact creation and persistence in `src/airport_analytics/consent/service.py` and `src/airport_analytics/history/repository.py`; preserve authorized prior artifacts after withdrawal and omit analyst identity by default.
- [X] T050 [US4] Implement report-history UI, consent notice, consent controls, and ownership-scoped report detail access in `app.py`; disclose retention of previously reused content before opt-in and keep this consent separate from hosted-provider data-use disclosure.

## Phase 7: User Story 5 - Handle Unsupported or Unclear Questions (Priority: P3)

**Goal**: Return focused clarification or clear unsupported-data guidance instead of fabricated answers.

**Independent Test**: Submit ambiguous questions, questions requiring unavailable fields, and questions under provider failure; verify no definitive report is shown without a valid plan and no external fallback occurs.

### Tests for User Story 5

- [X] T051 [P] [US5] Add clarification and unsupported-question integration tests for ambiguous metrics, missing fields, unavailable data, and empty supported result sets in `tests/integration/test_question_boundaries.py`.
- [X] T052 [P] [US5] Add provider-error and budget-exhaustion tests verifying no invalid plan is executed, no over-budget call occurs, and provider changes require explicit action in `tests/integration/test_model_failure_modes.py`.

### Implementation for User Story 5

- [X] T053 [US5] Implement model-plan outcome handling for `needs_clarification` and `unsupported` in `src/airport_analytics/reports/generation.py`; return one focused clarification or data limitation without compiling or executing a query.
- [X] T054 [US5] Implement distinct empty-result, unavailable-data, provider-error, and exhausted-budget states in `src/airport_analytics/errors.py` and `app.py`; do not show stale reports or fabricate zero-valued results.

## Phase 8: Polish and Cross-Cutting Concerns

**Purpose**: Validate the integrated product, deployment guidance, and privacy/cost boundaries.

- [X] T055 [P] Update `README.md` and `.env.example` with setup, local/hosted provider configuration, disclosure behavior, secret handling, LangSmith opt-in, shared monthly budget settings, English-only MVP scope, accessibility baseline, and the absence of availability/concurrency-throughput SLAs.
- [X] T056 [P] Add deployment-wide budget concurrency and restart-persistence integration tests in `tests/integration/test_budget_concurrency.py` and `tests/integration/test_restart_persistence.py`; verify the shared reservation ledger and committed reports/consent events survive a normal process restart.
- [X] T057 [P] Add a privacy test for LangSmith tracing opt-in in `tests/integration/test_tracing_privacy.py`; verify default-off behavior and that no traces contain prompts/results unless explicit disclosure and configuration are enabled.
- [ ] T058 Compare candidate local and hosted model/provider configurations for structured-plan support, free-tier quotas, current data-use/retention terms, rates, fees/taxes/FX, and performance; evaluate against `tests/fixtures/golden_questions.json` and `tests/fixtures/golden_expected_results.json`, require at least 11/12 expected metric-and-scope interpretations and exact independent numeric results for every generated report, then document selection/rationale in `specs/001-airport-analytics-platform/research.md` and `specs/001-airport-analytics-platform/quickstart.md` without recording secrets.
- [ ] T059 Benchmark end-to-end report latency for representative supported questions against the selected host and provider in `tests/performance/test_report_latency.py`; record the benchmark method and measured baseline in `specs/001-airport-analytics-platform/quickstart.md` without imposing a hard MVP pass/fail threshold.
- [ ] T060 Before production enables shared reuse, obtain deployment-owner approval for retention periods and deletion procedures covering analyst identity mappings, private reports, consent events, shared artifacts, and backups; document the approved policy in `docs/privacy-data-retention.md` and keep production reuse disabled until approval is recorded.
- [ ] T061 Create the acceptance protocol and run five anonymous analyst sessions in `tests/acceptance/analyst_study.md`; use distinct tasks for first-question comprehension (SC-001), follow-up scope refinement (SC-004), and finding/definition/limitation comprehension (SC-006), record only de-identified outcomes, and verify at least 4/5 analysts meet each criterion.
- [ ] T062 Run project formatting, linting, full automated tests, and an accessibility review in `tests/accessibility/test_ui_accessibility.py`; resolve any keyboard, labelling, focus, or non-color status/error findings in `app.py` and `src/airport_analytics/reports/rendering.py`, then run a final diff check.

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies; establishes the Python package and development configuration.
- **Foundational (Phase 2)**: Depends on Setup; blocks all user stories because stories share identity, data catalog, persistence, model-provider, and budget foundations.
- **User Story 1 (Phase 3)**: Depends on Foundational; delivers the MVP.
- **User Story 2 (Phase 4)**: Depends on User Story 1's analysis-plan and report pipeline to extend it with follow-up scope.
- **User Story 3 (Phase 5)**: Depends on User Story 1's report representation; adds evidence detail and exports.
- **User Story 4 (Phase 6)**: Depends on Foundational identity/persistence and User Story 1's report creation; secures private history and consented reuse.
- **User Story 5 (Phase 7)**: Depends on User Story 1's structured-plan and provider-error handling.
- **Polish (Phase 8)**: Depends on all user stories selected for delivery.

### User Story Completion Order

1. **US1 (P1)** must complete first for the usable question-to-report MVP.
2. **US2 (P2)**, **US3 (P2)**, and **US4 (P2)** can be scheduled after US1; US3 and US4 are separable from each other, while US2 consumes US1's report context.
3. **US5 (P3)** extends US1's boundary/error outcomes and follows the stable report/provider path.

### Parallel Opportunities

- Setup tasks **T002–T004** can run in parallel after T001 establishes the Python project.
- Foundational tasks **T006–T008**, **T010–T011**, and **T013–T015** can proceed in parallel when their shared files do not conflict; coordinate edits to `storage.py` and `config.py`.
- Within US1, tests **T016–T021** can be authored in parallel. Implementation tasks **T027**, independent metrics work, can proceed alongside schema/compiler work; UI integration waits for generation/provider behavior.
- US1 test tasks **T016–T021** use distinct test files and can run in parallel.
- The latency benchmark **T059** follows provider/model selection in **T058** and records a baseline without an MVP pass/fail threshold.
- The five-analyst sessions **T061** follow completion of the user stories being evaluated and use the explicitly stated SC-001/004/006 thresholds.
- Production reuse remains disabled until the owner-approved policy in **T060** is documented; this is a release gate, not permission to infer retention periods.
- US2 tests **T033–T034**, US3 tests **T037–T038**, US4 tests **T043–T045**, and US5 tests **T051–T052** each use separate files and can be authored in parallel within their story.
- After US1 is complete, US3 and US4 implementation can proceed in parallel with coordination around `app.py`; US2 and US5 can also proceed independently of US3/US4 core services.

## Parallel Example: User Story 1

```text
After the Phase 2 foundation is ready:
1. Author T016 golden-question tests, T017 plan tests, and T018 compiler safety tests in parallel.
2. Author T019 budget, T020 provider disclosure, and T021 tracing tests in parallel.
3. Implement T022 plan validation before T023 query compilation and T024 execution.
4. Implement T027 metric definitions in parallel with the compiler/execution tasks.
5. Integrate T025-T026 model orchestration and T028-T032 report/UI flow after their foundations are ready.
6. Run the US1 independent test criteria before beginning dependent report-history or follow-up integration.
```

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 Setup.
2. Complete Phase 2 Foundational work.
3. Complete Phase 3 User Story 1, including structured-plan validation, safe compilation, budget/disclosure controls, and the first report UI.
4. **Stop and validate** the US1 independent test criteria and golden questions before adding history, follow-ups, or exports.
5. Add each P2/P3 story incrementally, preserving the validated-query and monthly budget boundaries.

### Incremental Delivery

1. Setup + Foundational → shared application ready.
2. US1 → end-to-end MVP question-to-report experience.
3. US2 → conversational refinement.
4. US3 → deeper report interpretation and exports.
5. US4 → private history and consent-controlled reuse.
6. US5 → explicit ambiguity, unsupported-data, and provider-failure paths.
7. Polish → integrated privacy, cost, acceptance validation, measured response-time baseline, and release gates for retention policy and analyst usability.

## Phase 9: Convergence

Assessment outcome: `tasks_appended`. These tasks assess the present implementation against the specification, plan, and constitution; existing task completion marks are unchanged. F001-F017 identify the findings reported in-session. Tasks addressing existing release gates complete or strengthen them rather than replace their original tasks. Dependencies are stated explicitly below.

- [X] T063 CRITICAL [F001] Derive report period metadata from all effective date constraints, including `flight_date`, `flight_year`, and `flight_month_number` filters as well as `time_range`, in `src/airport_analytics/analytics/metrics.py`; keep narrative, visible scope, chart titles/captions, and PDF labels consistent in `src/airport_analytics/reports/generation.py`, `src/airport_analytics/reports/rendering.py`, and `src/airport_analytics/reports/export.py`. Add regressions proving a June-only filter does not claim a full-year active period and every displayed visualization identifies its period and units per Constitution I/IV, FR-008, FR-014, SC-003, and T027/T029/T039 (contradicts).
- [X] T064 CRITICAL [F002] Establish and validate each input's documented grain, expected field types, and duplicate-record/key policy in `src/airport_analytics/data/catalog.py`, `src/airport_analytics/data/validation.py`, and `src/airport_analytics/data/loader.py`; distinguish duplicate source identifiers from legitimate repeated flight observations, preserve source meaning rather than silently deduplicating, and surface invalid types or material duplicate issues before analytics. Add malformed-source, duplicate, null/key, and join-fan-out tests in `tests/integration/test_data_validation.py` per Constitution II and Development Workflow quality gates, plan decision 3, and T006/T007 (partial).
- [X] T065 [F003] Calculate matched/unmatched reference and weather coverage for the report's effective filtered flight population before match-only exclusions, while retaining separately labelled full-snapshot provenance where useful, in `src/airport_analytics/analytics/execution.py`, `src/airport_analytics/analytics/metrics.py`, and report rendering/export; add scoped EWR/date/aircraft/weather tests that independently reconcile denominators and exclusions rather than asserting full-snapshot counts for filtered reports per FR-012, FR-036, SC-003, and T027/T029 (partial).
- [X] T066 [F004] Add application-compiled supporting origin/destination route evidence to distinct-destination reports in `src/airport_analytics/analytics/query_compiler.py`, `src/airport_analytics/analytics/execution.py`, and `src/airport_analytics/reports/generation.py`; carry it through report persistence, UI, PDF, and tabular CSV exports with explicit completeness/bounds information, and independently reconcile route identities with the selected distinct count per FR-009, FR-018, US1/AC1, and T023/T028/T040/T041 (missing).
- [X] T067 [F005] Export the complete active scope, grouping, filters, geographic coverage, supporting tables, and visual context or an explicitly equivalent labelled representation in `src/airport_analytics/reports/export.py`; extend `tests/integration/test_report_exports.py` with non-empty airport/carrier/date filters and a grouped report so extracted PDF content must include the same material scope and evidence shown in the UI. Coordinate with T063/T065/T066 for their new metadata and tables per FR-018, US3/AC3, plan decision 6, and T040 (partial).
- [X] T068 [F006] Resolve default-on reuse grants in `app.py` against the explicit analyst opt-in requirements: under the current authoritative specification restore initially disabled purpose-specific session consent, record a grant only after an affirmative analyst action, preserve decline/later-opt-in/withdrawal/re-enable and pre-grant exclusion, and test both normal and development sign-in plus new sessions in `tests/browser/test_app_authentication.py` and `tests/integration/test_consent_transitions.py`. The later requested default-on behavior conflicts with the artifacts; if it is to remain, obtain an approved specification/plan amendment in a separate workflow before treating automatic grants as conformant. Reconcile related notices/docs without conflating hosted disclosure with reuse consent per FR-019-FR-023, US4/AC3-AC5, plan decision 9, and T044/T048/T050 (contradicts).
- [X] T069 [F007] Persist an explicit uncertain-acceptance/cost state and make paid authorization fail closed while unresolved, including after restart and UTC rollover as applicable, in `src/airport_analytics/analytics/budget.py` and `src/airport_analytics/storage.py`; preserve ordinary concurrent in-flight reservations, bound reconciliation/release to confirmed evidence, and add tests with ample remaining allowance so cap exhaustion cannot mask the uncertainty gate per FR-025, SC-008, and T012/T019/T026 (partial).
- [X] T070 [F008] Consume inference and tracing `Settlement` results in `src/airport_analytics/analytics/model_client.py` and surface over-reservation incidents through repository-standard operator-visible logging/notification without exposing questions, credentials, or provider bodies; verify the actual charge remains recorded and further paid calls block when allowance is exhausted, using adapter-level tests rather than only ledger return-value assertions per FR-025 and T019/T026 (partial).
- [ ] T071 [F009] Complete T058 by implementing a controlled provider-evaluation harness for `tests/fixtures/golden_questions.json` and `tests/fixtures/golden_expected_results.json` that invokes the selected local/hosted candidate, compares generated metric and scope rather than feeding expected plans to the executor, requires at least 11/12 interpretations and independent numeric agreement for every generated report, and rejects every invalid plan before execution. Verify live structured-output compatibility, current account quotas/data-use terms/cost bounds and representative clarification/unsupported behavior; use authorized minimal payloads, no secrets in artifacts, no automatic retries/fallback, and the normal disclosure/budget gates. Record provider/model selection and any remaining failures in `specs/001-airport-analytics-platform/research.md` and `specs/001-airport-analytics-platform/quickstart.md` per FR-002, FR-006, FR-007, FR-024-FR-029, SC-002, US1/AC1-AC7, and plan decision 2 (partial).
- [X] T072 [F010] Resolve the shared development identity/sign-in bypass in `app.py`, `src/airport_analytics/auth.py`, and `src/airport_analytics/config.py` against required OIDC authentication for analyst-specific resources: either enforce FR-031 as written or obtain an approved, separately documented development-only exception through the specification/plan workflow before retaining it as conformant. Preserve production prohibition and loopback restrictions while reviewing the exception; test that no supported production configuration can access private history or exports without OIDC per FR-031, US4/AC1-AC2, plan decision 1, and T008/T030/T043 (contradicts).
- [ ] T073 [F011] Complete T060 by obtaining actual deployment-owner approval and documenting retention periods and deletion/backup procedures for identity mappings, private reports, consent audit records, and retained shared artifacts in `docs/privacy-data-retention.md`; tie production reuse enablement guidance to recorded approval and test the unapproved-production gate. Do not invent owner approval or retention periods per FR-035, plan decision 9, and T060 (missing).
- [ ] T074 [F012] Complete T061 after T071 establishes a usable provider and the scope/evidence/accessibility corrections T063/T065/T066/T067/T075/T076 are validated: create `tests/acceptance/analyst_study.md`, run five real de-identified analyst sessions with separate first-question, follow-up-scope, and definition/limitation tasks, and record actual outcomes against the 4/5 threshold for each criterion without fabricating participants or results per SC-001, SC-004, SC-006, US1-US3, and T061 (missing).
- [ ] T075 [F013] Complete T062 with an authenticated browser accessibility review covering question entry, FAQ selection/submission, refinement, provider/disclosure controls, reuse controls, history, deletion, and downloads; extend `tests/accessibility/test_ui_accessibility.py` beyond sign-in/title assertions to verify keyboard operation, labels, visible focus, and non-color status/error cues, record browser/manual evidence where automation cannot prove a criterion, and resolve findings in `app.py` and `src/airport_analytics/reports/rendering.py` per FR-033, SC-012, plan decision 10, and T062 (partial).
- [X] T076 [F014] Define and implement explicit tie presentation and bounded cutoff handling for rankings in `src/airport_analytics/analytics/query_compiler.py`, `src/airport_analytics/reports/generation.py`, and `src/airport_analytics/reports/rendering.py`; preserve deterministic ordering, disclose any tied entries omitted by the result bound, avoid claiming a unique winner when tied, and add independent tied-value/top-N boundary tests per FR-011, SC-005, US1/AC2, and T023/T028/T029 (partial).
- [X] T077 [F015] Detect changes to the configured source files before reusing the cached executor in `app.py` and revalidate/rebuild snapshot state through `src/airport_analytics/data/loader.py` without publishing partially refreshed or invalid data; add a regression proving changed source content cannot silently keep serving the prior cache as current and that old saved reports retain their original snapshot provenance per FR-003, US1/AC4, and T007/T024 (partial).
- [ ] T078 [F016] Complete T059 after T071 selects a usable host/provider by adding `tests/performance/test_report_latency.py` and recording reproducible end-to-end measurements for representative supported questions in `specs/001-airport-analytics-platform/quickstart.md`; identify environment, model/provider, cold/warm conditions, method, and failures without imposing an MVP response-time threshold or reporting mocked timing as live latency per SC-010, plan performance constraints, and T059 (missing).
- [X] T079 [F017] Extend `tests/integration/test_restart_persistence.py` to create committed reports, consent events, and held/settled usage in one application process and verify owner-scoped access and budget continuity from a separate process after normal termination; distinguish persisted consent audit events from fresh-session consent state, and ensure tests cannot pass solely by reopening `Storage` within the same interpreter per FR-034, SC-011, and T056 (partial).

### Implementation evidence and remaining release gates

- T063-T067/T076: independent filtered coverage, period, route reconciliation/bounds, ranking cutoff, and extracted-PDF scope regressions are in `tests/integration/test_convergence_evidence.py`; weather coverage is also asserted in `test_report_evidence.py`.
- T064/T077: malformed types/keys, preserved repeated observations, source fingerprint refresh, and invalid replacement tests are in `tests/integration/test_convergence_sources.py`, alongside the existing data-validation suite.
- T068/T072: the owner explicitly approved retaining default-on reversible session choices and the guarded loopback-only development identity. The approved exceptions are recorded in `spec.md`, `plan.md`, `data-model.md`, `research.md`, and `contracts/question-report.md`; default selection is not represented as affirmative legal consent.
- T069/T070/T079: ample-allowance uncertainty, rollover, adapter overrun logging/blocking, and separate-process persistence tests cover the budget changes and session isolation.
- T071/T078 remain open: an explicit live-evaluation CLI, comparison tests, and opt-in latency runner now exist, but no live provider pass, current account terms/quota verification, or live latency measurements have been recorded.
- T073 remains open: `docs/privacy-data-retention.md` is an approval worksheet, not approved policy.
- T074 remains open: `tests/acceptance/analyst_study.md` is the five-participant protocol; no real sessions or outcomes are claimed.
- T075 remains open: `tests/accessibility/REVIEW.md` records the isolated keyboard review and outstanding authenticated paths; FAQ evidence is now static labelled tables. The browser download check timed out, so successful download completion is not claimed.
- Original release tasks T058-T062 remain unchecked until their actual evidence is available.
- Offline verification: 169 tests passed and one explicitly authorized live-provider test skipped; Ruff check/format and whitespace validation passed. No live-provider acceptance or measured live latency is implied.
