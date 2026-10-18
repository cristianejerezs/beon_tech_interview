# Validation Quickstart: Natural-Language Exploration

**Status**: V2 is enabled by default for summaries, listings, multi-stage analytics and one to
four resolved sections, with local correction, history and bounded CSV/table-PDF exports.
Turn the toggle off for V1 generation; saved V2 evidence remains readable. The offline evaluator
and timing instrumentation exist, but independent corpus preparation/freeze, live evaluation,
real analyst/accessibility work and integrated 003 acceptance remain outstanding. See the
[dated acceptance record](acceptance-results.md) and [task-level status](tasks.md).

## 1. Existing setup and baseline commands

Use Python 3.12 and this workspace. Follow the existing [application quickstart](../../QUICKSTART.md) for environment/provider configuration, local sign-in restrictions and source CSV placement. Do not overwrite an existing environment file, secrets, data directory or database.

```powershell
Set-Location 'C:\Users\Cristian E Jerez S\Desktop\BEON\beon_tech_interview\interactive-airport-data-platform'
python --version
python -m pytest tests\unit\test_analysis_plan.py tests\unit\test_follow_up_context.py tests\unit\test_query_compiler.py tests\unit\test_evaluation.py tests\integration\test_query_execution.py tests\integration\test_report_evidence.py tests\integration\test_report_exports.py tests\integration\test_report_ownership.py tests\integration\test_report_retention.py tests\integration\test_consent_transitions.py tests\integration\test_model_failure_modes.py
```

Do not install dependencies solely for documentation work. For a fresh development setup or an actual missing-dependency failure, use the manifest's documented editable installation, not arbitrary package upgrades. Tests use isolated temporary storage; never point fixture mutation tests at personal reports or the supplied source files.

For local UI validation:

```powershell
python -m streamlit run app.py --server.address 127.0.0.1
```

Use existing approved local identity/OIDC and local model configuration. Verify the server is responsive before browser checks. Hosted submission requires actual configured terms/disclosure/budget gates; default-on choices are not proof of affirmative consent. Turning acknowledgements off must still block dispatch.

After signing in, **Use V2 summary exploration** is on by default. Ask one
ordinary summary, analytical request or up to four labelled related analyses; interpretation is shown before
local editing. **Apply interpretation** computes and saves a new revision without a provider
call; **Cancel edits** keeps the saved report unchanged. Unchanged/unshown filters are retained,
including exclusions; explicit removal controls clear origin/airline restrictions. Date bounds
intersect retained date filters. If persistence fails, the session retains visible unsaved
evidence and offers **Save unsaved report**, without another model call. Switching the preview
off restores V1 generation; V2 saved summaries remain readable/exportable.

For lists, try "List distinct destinations served from JFK" or "Show individual flights from EWR".
Observed origins/destinations/airlines are distinct from "List every airport in the airport
reference file", which includes reference-only airports and cannot take flight-date/airline filters.
Saved previews contain at most 100 initial rows, with exact population totals. **Load listing page**
supports 25/50/100/500 rows, approved column sorting and 1-based page positions. Scope, sort and
size changes reset to page one; out-of-range positions show a reset notice. These actions never
call the model. Listings have no arbitrary numeric chart or summary-sharing control.

**Download saved preview (CSV)** and the table PDF use saved evidence only. For more records,
choose **Listing export rows**, confirm any partial population, then **Prepare listing CSV**.
Only complete prepared bytes enable download; one listing export is capped at 10,000 data rows.
Exports start at row one in saved report order, not the browsing page. CSVs include BOM/CRLF,
full precision, ISO dates, exact exported/total counts, scope/definition/field metadata and
`_meta_null_fields`. Empty listings have one labelled metadata-only row. Risky text (an apostrophe
prefix, or =/+/-/@ after whitespace) gains one leading apostrophe; removing that one transport
prefix recovers the source text. Stored evidence is unchanged.

Changed/missing sources or context disable continuation/full-listing export, not saved previews.
**Restart listing on current source** copies the original question into the form; review and
explicitly select **Generate report** to start again under normal provider/disclosure/budget gates.
Catalog 2.2 includes the analytical definitions, so historical older-context evidence remains readable but cannot
be silently recomputed against the newer context.

For a valid ambiguous interpretation, **Pending analysis** shows the focused question and
retained candidate scope. Choose a locally validated **Clarification choice** and select
**Use selected choice**, or enter **Clarification answer** and select **Submit clarification**.
Choices and structured correction are local; a submitted free-text answer makes one gated
provider call. Three answered but still unresolved turns lead to **Guided summary correction**,
not an unbounded recursive model loop. Correct measure/grouping/origin/destination/airline,
date bounds, ordering and output bound, then **Apply guided correction**; or restart/cancel.

A provider failure or invalid response preserves the question/choices and consumes no answered
turn. **Retry interpretation** is explicit and rechecks the existing safeguards. For a failed
clarification it restores the controls; explicitly submit the answer again to dispatch.
The app does not pretend an invalid structured response is a valid ambiguity.
Pending state is session-only and is cleared on sign-out. A fresh submitted question replaces it.
Four-section execution and daily/weekday means are implemented. The airport exercise still needs
an explicit origin/period and reviewed calendar coverage, or an explicitly revised observed-day
denominator. Missing evidence never produces a fabricated complete-day answer.

The evaluator now selects `--suite legacy12` or `--suite v2`. Both require `--run-live`;
hosted providers additionally require `--acknowledge-hosted-processing`, actual provider
readiness, disclosure/budget safeguards and disabled tracing. No live run was performed here.

```powershell
# Only after independent corpus/gold review and fresh explicit live authorization:
python -m airport_analytics.analytics.evaluation --run-live --suite v2 `
  --corpus-version '<reviewed-version>' --corpus '<reviewed-corpus.json>' `
  --gold '<reviewed-gold.json>' --thermal-state cold
```

Corpus/gold paths above are operator-supplied files, not existing frozen fixtures.
Every attempted case is counted; no automatic retries or stitched successes occur.
Gates require 100 unambiguous cases (10/family), at least 90 correct overall and 8/family,
all 20 negative cases, at least three variants for every AQ-01..10, and correct numbers
for every generated section even with a wrong interpretation. CLI release status remains
blocked while independent review and external acceptance are unverified.

`capture_stage_timings()` records context-local cumulative durations for source validation,
interpretation, execution, table preparation, server preparation and export generation.
Normal use does not persist timing records or arguments/content/exception bodies. Reentrant
calls of the same stage are not double-counted; different stages can overlap and must not be
summed as a wall-clock SLA. Evaluation emits safe versions/settings, source/context hashes,
all case outcomes and finite absolute numerical errors. A declared warm CLI run does not
cause hidden warm-up/provider calls. The [offline timing test](../../tests/performance/test_exploration_stage_timings.py)
measures a new fixture executor, then the same executor/client reused once. It is a synthetic
local cold/warm baseline, not hosted-model latency or production throughput. Server/table
preparation is not observed browser readiness. Actual browser/assistive and chart-ready
measurements remain not-run/003-dependent.

See the [product analytical workflows](../../QUICKSTART.md#v2-analytical-and-multi-section-workflows)
for declaration formats, explicit per-section/all-section scope edits, incomplete acknowledgement,
versioned preferences, and allocated composite ZIP exports.

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

## Implementation baseline (2026-10-17)

- T001 targeted command in section 1: **75 passed in 17.91 seconds**, with no provider calls.
- Shell runtime: Python 3.12.0, DuckDB 1.5.6, Pydantic 2.14.1, Streamlit 1.66.0,
  pytest 8.4.2; no assertion about the editor-selected interpreter.
- Existing parent Git ignore rules cover Python caches, virtual environments, build artifacts,
  `.env` secrets, Streamlit credentials and runtime SQLite storage. No additional stack-specific
  ignore file is needed for this Python-only change.
- Independent oracle and fixture suite: **10 passed**. All five synthetic CSVs also pass the
  existing loader's schema/grain validation; fixture coverage is fictional, not real completeness.
- Source SHA-256 identities at baseline:

| Source | SHA-256 |
|--------|---------|
| nyc_airlines.csv | `162551bd3401a12d63db3d92b7e66af3017d2e40d55919d6a678489323c10609` |
| nyc_airports.csv | `de7e0da52e127a51eac24173c3bfa4aa018848b76c040e94bfc904ee27c37582` |
| nyc_flights_fixed.csv | `a49ebb57726790405f195976121f700592f14f81dc6022d45c40de23bfd0472b` |
| nyc_planes.csv | `778962edec8339f6f6edb1d6506869f61cab573eda03d7e162d2899c76d04c1a` |
| nyc_weather.csv | `f7c867ce8b3592696a6eb6c6d741d5cfe9df776b73e9e9952024e1c74f5e6db8` |

## Executed foundation checkpoint

- Full regression command: `python -m pytest -q`: **242 passed, 1 skipped in 44.13 seconds**.
  The intentionally skipped live-provider acceptance/latency test requires explicit operator
  authorization. No paid, hosted or live local inference was performed.
- Ruff checks on the application/source and new exploration tests passed; `git diff --check`
  passed. Pylance reported no diagnostics for changed models, provider client, repository,
  loader and app; executor has only unused context-manager argument hints.
- Structural tests cover all eight result variants, finite/null-with-reason values, closed
  catalogs/schema, 500-group and pooled-support bounds, 100 bins, 5,000 pairs and 400 density cells.
- Provider projections are exercised with fake Ollama, OpenAI-compatible and Groq responses:
  one dispatch per composite, local rejection without repair/fallback, disclosure/budget
  refusal before dispatch, uncertainty preservation and minimal active semantic context.
  These tests do not establish provider-side/live schema acceptance or paraphrase accuracy.
- V1/V2 storage, unknown/corrupt versions, ownership, rollback, exact incomplete-report
  acknowledgement and no-first-section-proxy regressions pass. AppTest verifies readable V2
  history/deletion and explicitly gated V2 export/sharing/refinement while preserving V1 UI.
- Source/context changes reject stale continuation without replacing saved snapshot evidence.
  A coverage file's presence/content is fingerprinted as **unverified**, never proof of
  completeness. Detailed coverage approval/eligibility remains T036/T039.
- T015-T070 and all external/integrated release gates remain pending. No extension hook
  configuration was present at the post-implementation check.

## Executed US1 summary checkpoint

This supersedes the foundation checkpoint's integration status, not its historical results.

- T015-T022 completed; **22/70 tasks** are now checked. T023-T070 remain pending.
- Full regression: `python -m pytest -q`: **275 passed, 1 skipped in 42.53 seconds**.
  The skipped live-provider acceptance/latency test still requires operator authorization.
- `python -m ruff check app.py src\airport_analytics tests` and `git diff --check` passed.
  Pylance returned no diagnostics for the changed app, interpretation, models, metrics and
  export modules.
- Targeted US1 run: `python -m pytest tests\unit\test_exploration_interpretation.py tests\integration\test_exploration_summaries.py tests\browser\test_exploration_summary_ui.py -q`:
  **33 passed**. The full regression also exercises the original V1 authentication, consent,
  provider, history and export workflows.
- Independent CSV/set/numeric oracles verify all eight aggregate measures, global versus
  per-origin distinct counts, two-role grouping, date ordering, known/missing observations,
  reference-only valid-empty scope, unmatched categories and stable aircraft-model identity.
  Weather-context summaries remain matched-flight-weighted, not the future hour-weighted
  weather-correlation analysis.
- A 501-group/501-route fixture verifies exact full-population totals and cutoff ties before
  separate 500-row result/route selections. Executable-looking filter text remains bound data.
- AppTest verifies explicit V2 generation/follow-up, labelled local edits, Cancel/Apply
  revision behavior, exclusion/unshown-filter preservation, saved reopen/downloads/FAQ and
  interrupted-save recovery without repeat inference.
- One-section sharing verifies ownership, original-session/creation eligibility, withdrawal
  and exclusion of reports predating a new grant. CSV/table-PDF use saved typed evidence;
  table PDFs do not claim 003 chart or accessibility acceptance.
- No live provider inference, human acceptance study or visual/accessibility certification
  was performed. Mocked wording/provider tests do not establish natural-language accuracy.
- Both reviewer-owned checklists remain unchanged and fully checked (40/40 and 16/16).
  No extension-hook configuration was present at the final post-implementation check.

## Groq V2 schema compatibility verification

- A separately authorized synthetic request reproduced Groq HTTP 400 on overlapping
  `integer`/`number` filter-value alternatives. After removing the redundant integer branch,
  a second authorized check exposed duplicate string-type enum alternatives in ordering.
  Both are now normalized recursively in the Groq wire projection without changing the
  authoritative local schema or disabling strict output.
- A third separately authorized request to `openai/gpt-oss-20b` succeeded: synthetic
  **Count flights** returned `proposed` / `aggregate` / `flight_count` and passed full local
  V2 validation. No source rows, private history or saved reports were sent; tracing was off.
  Existing persistent budget/free-quota/disclosure gates applied; no automatic retries or
  provider switches occurred. Failed-call reservation safeguards were not cleared.
- Full regression after the fix: **279 passed, 1 skipped in 50.40 seconds**.
  Ruff, whitespace checks and Pylance diagnostics for the provider client passed.
  Offline tests include schema-equivalence checks and the real LangChain HTTP adapter with
  mock transport. This one live synthetic success is not corpus/AQ/E2E or latency acceptance.
- Restart Streamlit after loading this fix, then explicitly submit the desired question again.

## Executed US2 clarification checkpoint

- T023-T028 completed; **28/70 tasks** are checked. T029-T070 remain pending.
- Full offline regression: `python -m pytest -q`: **307 passed, 1 skipped in 58.90 seconds**.
  The intentionally skipped live-provider latency/acceptance test remains authorization-gated.
- Focused command: `python -m pytest tests\unit\test_exploration_state.py tests\browser\test_exploration_clarification_ui.py tests\integration\test_exploration_clarification.py tests\integration\test_model_failure_modes.py tests\integration\test_tracing_privacy.py tests\unit\test_budget.py -q`:
  **78 passed in 16.96 seconds**.
- Pure transitions cover session/request/revision/section/question binding, turns 0..3,
  cancellation/supersession, explicit retry and execution terminal states. Stale/cross-session
  answers and changed sources are rejected before provider dispatch or analytics.
- AppTest covers local choices, invalid offered-choice suppression, free-text loops,
  third-turn guided correction, local corrected execution, failed-provider recovery without
  consuming a turn, retained original wording, fresh-request supersession and sign-out.
  Existing FAQ-prefill and question-retention regressions also remain green.
- Integration tests verify no analytics while unresolved, preservation of resolved measure,
  grouping and carrier scope, corrected-revision provenance and explicit nonexecution of
  composites even after their ambiguity resolves.
- Each free-text clarification uses the existing dispatch/reservation/settlement path.
  Tests cover missing disclosure, malformed output without repair, uncertain paid acceptance
  surviving restart and month changes, disabled versus enabled content-bearing tracing policy,
  trace-charge accounting and redacted operational logs.
- Ruff and whitespace checks passed; Pylance returned no diagnostics for the app, request-state,
  interpretation, generation and provider-client modules. Python-only ignore rules remain valid;
  no new package or service was added.
- No live provider request or external trace was made for this milestone. Mocked provider
  responses establish workflow behavior, not live language accuracy, full AQ/E2E acceptance,
  browser keyboard/screen-reader accessibility or production retention approval.
- No extension-hook configuration was present at the post-implementation check.

## Executed US3 browsing checkpoint

- T029-T035 completed; **35/70 tasks** are checked. T036-T070 remain pending.
- Full offline regression: `python -m pytest -q`: **327 passed, 1 skipped in 61.72 seconds**.
  The live-provider latency/acceptance test remains explicitly authorization-gated.
- Focused command: `python -m pytest tests\integration\test_exploration_browsing.py tests\integration\test_exploration_listing_exports.py tests\browser\test_exploration_browsing_ui.py -q`:
  **20 passed in 13.97 seconds**.
- Tests compare all entity populations against CSV sets, three consecutive flight pages at
  each size against source identities, count/page predicates, delay ties, missing references,
  empty/out-of-range resets, changed scope/size/order and stale owner/request/source/context.
- Export tests reconcile identities at 9,999/10,000/10,001 rows and combined allocations below,
  at and above 10,000; stale scope/order/context/snapshot/revision/allocation cannot reuse a
  selection. Actual empty strings, nulls, quotes, embedded newlines and formula-like text
  round-trip without changing saved evidence. Missing source files and closed executors fail.
- AppTest covers local paging/downloads, partial confirmation, no stale download after a
  technical failure, saved V2 browsing while V1 generation is selected, explicit restart without
  dispatch and saved-preview access when no current source can be loaded.
- Aggregate evidence retains its separate 500-group ceiling; shared allocation types enforce
  the common 10,000 listing ceiling. Composite allocation/bundles and failed-section metadata
  integration remain T058, not an implemented composite export. All-failed reports remain invalid.
- No new dependency, migration, live provider request or external trace was required.
  These are synthetic offline workflow/numerical results, not full AQ/live-language acceptance.
- Repository Ruff and whitespace checks passed; targeted Pylance checks found no error
  diagnostics in the changed application modules. No extension-hook configuration was present.
