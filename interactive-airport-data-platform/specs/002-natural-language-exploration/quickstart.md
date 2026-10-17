# Validation Quickstart: Natural-Language Exploration

**Status**: Design-only. New V2 types/UI/evaluator are not implemented. Commands in section 1 exist today; scenarios in sections 2-5 are future implementation acceptance obligations, not a claim that the current app supports them.

## 1. Existing setup and baseline commands

Use Python 3.12 and this workspace. Follow the existing [application quickstart](../../QUICKSTART.md) for environment/provider configuration, local sign-in restrictions and source CSV placement. Do not overwrite an existing environment file, secrets, data directory or database.

```powershell
Set-Location 'C:\Users\Cristian E Jerez S\Desktop\BEON\beon_tech_interview\interactive-airport-data-platform'
python --version
python -m pytest tests\unit\test_analysis_plan.py tests\unit\test_follow_up_context.py tests\unit\test_query_compiler.py tests\unit\test_evaluation.py tests\integration\test_query_execution.py tests\integration\test_report_evidence.py tests\integration\test_report_exports.py tests\integration\test_report_ownership.py tests\integration\test_report_retention.py tests\integration\test_consent_transitions.py tests\integration\test_model_failure_modes.py
```

Do not install dependencies solely for documentation work. For a fresh development setup or an actual missing-dependency failure, use the manifest's documented editable installation, not arbitrary package upgrades. Tests use isolated temporary storage; never point fixture mutation tests at personal reports or the supplied source files.

For UI validation once implemented:

```powershell
python -m streamlit run app.py --server.address 127.0.0.1
```

Use existing approved local identity/OIDC and local model configuration. Verify the server is responsive before browser checks. Hosted submission requires actual configured terms/disclosure/budget gates; default-on choices are not proof of affirmative consent. Turning acknowledgements off must still block dispatch.

The current `python -m airport_analytics.analytics.evaluation --run-live` command dispatches real model calls and evaluates only the original twelve cases. It is **not** V2 acceptance and is not run by this planning workflow. The implementation must extend its explicit opt-in interface with versioned suite selection and document the actual command when that exists; do not report a future CLI as already runnable.

## 2. Future offline acceptance matrix

Use synthetic source fixtures with enumerated source identities, date coverage and expected values. Test each operation with production compilation/execution but calculate expected values independently from CSV rows/sets/date lists/Decimal/centered sums. Do not call production metric/compiler helpers from the oracle.

| Area | Required checks and expected outcome |
|------|--------------------------------------|
| Trust boundary | V2 strict properties/enums/finite numbers/provider projections; reject injected SQL, unknown dimensions, unsupported operations, contradictory scope and fabricated entities before execution |
| Entities/defaults | Exact case-insensitive codes, names/aliases, duplicate names, confirmed spelling suggestion, reference-only and unknown entities; explicit defaults/field provenance |
| Clarification | Turns1/2/3, then guided correction; stale/cancelled/superseded/cross-session answers execute nothing; provider failure does not consume a turn |
| Follow-up/edit | Retain/add/replace/remove diff, target section/all-sections, Apply/Cancel, all-origin/date expansion, page reset, changed-snapshot acknowledgement |
| Composite | 1/4 accepted,5 requires selection; all sections resolve before main execution; explicit removals; valid empty; first/middle/last runtime failure; all-failed not saved |
| Partial acknowledgement | No auto-save/download of incomplete report; exact failed IDs retained after acknowledgement; acknowledgements cannot bypass technical export failure or retroactively qualify content for consent |
| Paging | Sizes25/50/100/500; three consecutive pages match independent ordered slices with no duplicate/missing IDs; change size/sort/filter reset; out-of-range notice; source/context change blocks continuation |
| Groups/ranks | 499/500/501 groups, top0/top501 rejected, defaulttop10, stable equal-value order and cutoff tie; all monthly/aircraft maxima; total groups exact |
| Export | 9,999/10,000/10,001 listing rows; combined allocations below/at/above10,000; confirmation invalidated by scope changes; aggregate selected groups only; CSV text/encoding/metadata round trip |
| Dates/periods | Inclusive endpoints, Monday weeks, year-month order, leap dates/month-end clamps, equal-day prior window, unequal calendar exposure, zero/unavailable/negative baseline |
| Bins | 15-minute/250-mile defaults; negative/exact-endpoint/constant/missing data;99/100/101 bins; proposed smallest integer-width multiple requires acceptance; exact bin reconciliation |
| Pairs | Same-flight identities; missing partition;5,000 scatter vs5,001 full density;20x20 max cells; constant axes; no arbitrary Pearson/regression |
| Coverage | Applicable/missing/stale/conflicting/gap declarations, observed row without completeness evidence, scope spanning origins; unavailable verified means and explicitly selected observed-day alternative |
| Persistence | V1 read/export unchanged, V2 parent/section ownership, reopen without source rows, no automatic recomputation, one composite retention slot, preference update scope, corrupted/unknown version explicit failure |
| Privacy/budget | Existing reservations/free quota/tracing, explicit retry, uncertain acceptance across restart/month; no raw provider bodies/source rows/private text in diagnostics/prompts |

### AQ numerical fixtures

Include AQ-01 through AQ-10 plus three ordinary-language variants each, separately from family quotas:

- Repeated destinations across dates: global distinct, daily distinct and weekday means differ; verify unequal weekday occurrences and half-up display boundary.
- Verified zero-flight dates versus unknown dates: distinct/capacity numerator and eligible-day denominator must agree across interpretation/table/evidence/export.
- Positive delay sums with early/missing delays versus explicitly selected net sums; tied monthly maxima.
- Duplicated weather-flight hours: collapse to equal-weighted origin-hour means, four variable-specific pair counts, fewer than3 pairs, constant axes, precipitation band boundaries and missing/unmatched weather.
- Missing seat references, negative invalid seats, common date set across airlines, no known seats, provisional lower-bound rankings; no implication of ticket availability.
- Unequal flight activity across aircraft, reused model text across manufacturers, unmatched/null manufacturer/model/tail data; distinct-aircraft and explicit flight-frequency definitions remain different.

For finite computed values record actual absolute error and enforce `<=max(1e-9,1e-12*abs(expected))`; exact identities/counts/order/bin membership and null reasons. A numeric failure anywhere fails the run, including a result from a wrongly interpreted question.

## 3. Future UI and integrated validation

Execute E2E-01 through E2E-09 from [the authoritative spec](spec.md#shared-end-to-end-acceptance-cases). Compare interpretation, independent values, 003 visual evidence, table, saved reopen and all selected exports on the same snapshot/context. Add the E2E-09 runtime fault as a separately recorded variant.

Before 003 is ready, record only completed 002 components; table-only PDFs are not chart/PDF accessibility acceptance. Chart rendering, compatible switches, density, subsets, embedded graphics and tags/font/reader checks follow 003's own plan.

Check labelled controls, focus movement and recoverable loading/error states with AppTest plus actual keyboard/browser testing; automated assertions alone do not establish WCAG or screen-reader support. Analyst participant testing remains separate from correctness.

## 4. Future live interpretation and human gates

1. Two reviewers independently label and adjudicate a versioned held-out corpus before candidate output:100 unambiguous requests (10/family),20 negatives, separate AQ/composite/state suites.
2. Freeze prompts/schema/catalog/aliases/source/context/model/settings and independent expected results. No gold plans in user wording/prompts.
3. Explicitly authorize local/hosted evaluation; verify provider availability/terms/quotas and tracing/privacy/cost settings. Never fabricate an account or free quota. An unavailable provider is a failed/incomplete run, not an omitted case.
4. Run each frozen case once per declared run; no selective retries or stitched successes. Require>=90/100 overall,>=8/10 every family, all20 negative boundaries correct, all AQ variants approved and every produced numeric result correct. Record other suites separately.
5. Review failed held-out wording only as development material; replace exposed cases independently before another acceptance claim and preserve earlier runs.
6. Recruit five real nonimplementer analysts per spec SC-006, require4/5 unaided success separately for every task, record assistance/limitations and repeat after material fixes using five new participants.

Pending external gates from001 (retention owner approval, actual provider acceptance, analyst/accessibility/latency evidence) remain pending. Neither a mock suite nor a design document closes them.

## 5. Requirement traceability for task generation

| Requirements | Design / validation obligation |
|--------------|--------------------------------|
| FR-001, FR-003-005, FR-009-010, FR-026 | Catalog operations, scope/entity defaults and compatible one/two-dimensional definitions; family/combination tests |
| FR-002, FR-006-008, FR-025 | Interpretation edit/provenance, request state, bounded clarification, stale guards and field-level inheritance tests |
| FR-011-013, FR-030 | Page/count/snapshot boundaries, explicit listing allocation/confirmation and selected group exports |
| FR-014-018 | Rank/trend/period/bin/pair definitions and independent arithmetic/boundary fixtures |
| FR-019 | Existing authorization/disclosure/budget/privacy/source protections and provider-output rejection |
| FR-020, FR-027, FR-029 | V1/V2 owned immutable report payloads, ten-parent retention, full precision/format and version-aware consumer tests |
| FR-021, FR-028 | Frozen corpus, independent reviewers, versioned semantic normalization, live run records/no retry stitching |
| FR-022, FR-031 | Shared nine-case002/003 release and real operational/accessibility/usability evidence, no invented latency SLA |
| FR-023-024 | Four-section orchestration, upfront readiness, explicit removal, runtime partial acknowledgement and all-or-nothing exports |
| FR-032-037 | Daily/weekday means, delay sums, weather panel, seat ranks, aircraft identity and snapshot-specific coverage, AQ/SC-011 fixtures |
| SC-001-003,010 | Fixed corpus family/negative/AQ quotas and every-result numerical reconciliation |
| SC-004,007-009,011 | Paging, state, ceilings, definitions and coverage boundary suites |
| SC-005-006 | Integrated E2E and real formative analyst studies |

## Planning execution record

| Check | Actual outcome |
|-------|----------------|
| Repository/source/consumer reconnaissance | Completed; five CSVs, no accompanying coverage declaration; V1-only assumptions identified |
| Local read-only runtime probe | DuckDB ISO weekday/week-start and Pearson primitives available; package versions recorded in plan |
| Unit provenance | Upstream weather units documented; transformed local-source provenance still requires validation |
| JSON schema/document links/prerequisites | Passed: six design documents' relative file links/template checks, all37 FR mappings, Draft2020-12 schema validity, one synthetic positive and five negative structural cases; Spec Kit prerequisites resolve002. These checks do not execute the feature or prove real source coverage |
| Post-plan hooks | No `.specify/extensions.yml` present; no registered hooks to execute |
| V2 implementation/live corpus/AQ/E2E/human study | Not executed; feature not implemented in this planning phase |
