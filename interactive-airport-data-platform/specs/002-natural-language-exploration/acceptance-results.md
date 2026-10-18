# Natural-language exploration: implementation acceptance record

Date: 2026-10-18 (UTC).

## Decision and scope

**Local implementation verified; integrated release approval withheld.**

T001-T060 and T062-T066 are checked in [tasks.md](./tasks.md): 65 of 70 tasks.
T061 and T067-T070 remain incomplete. No independent held-out corpus, human
review/adjudication, authorized live candidate run, five-analyst study or joint 003
visual/accessibility acceptance is claimed.

The current worktree contains the implementation; no commit or push was requested.
Prior milestone results in the quickstart remain historical, not substitutes for
the verification below.

## Reproducible local verification

Environment: Windows 11 AMD64, Python 3.12.0, DuckDB 1.5.6, Pydantic 2.14.1,
Streamlit 1.66.0. Commands ran from the project folder using the existing
`..\beon\Scripts\python.exe` interpreter; no packages were installed.

| Check | Actual outcome |
|-------|----------------|
| `python -m pytest -q --tb=short` | **431 passed, 1 skipped in 97.63 seconds** |
| Final focused analytical/composite/storage/UI/evaluation run | **58 passed in 16.31 seconds**, subsequently included in the full run |
| `python -m ruff check app.py src tests` | All checks passed |
| `python -m ruff format --check app.py src tests` | 113 files already formatted |
| `git diff --check` | Passed |
| Focused Pylance diagnostics after final code changes | No errors in analytical execution, multi-stage analytics, export or evaluation records; executor retains unused context-manager parameter hints |
| Python signature compatibility | Distribution prerequisite and multi-stage dispatch call sites compatible after adding timeout propagation |
| Reviewer-owned exploration checklist | 40/40 checked; markers not changed by implementation |
| Requirements checklist | 16/16 checked; markers not changed by implementation |
| Extension hooks | No `.specify/extensions.yml` present at the final implementation check |

The skipped test is the explicitly gated live-provider acceptance/latency test.
No provider request was made by these runs. The evaluation CLI also has a test
proving that omission of `--run-live` refuses dispatch.

### Important numerical and workflow assertions

- Independent CSV/set/Decimal oracles cover distinct destinations, equal-day and
  weekday denominators, verified zero-flight days, unknown coverage, calendar gaps,
  half-up rounding, common-airline date sets and provisional known-seat capacity.
- Weather uses distinct origin-hour populations, per-variable missingness and
  provenance-checked units; coefficients require sufficient nonconstant pairs.
  Manufacturer/model identity and distinct-tail versus flight-frequency semantics
  are independently exercised.
- Boundary cases cover 499/500/501 primary groups, pooled daily support across
  multiple categories, top-501 rejection, ties, relative calendar periods,
  99/100/101 bins and 5,000/5,001 complete pairs.
- Distribution eligibility is checked for every section before any main section
  query. Large-span proposals start at a necessary range bound, retain the
  smallest anchored integer multiple, and observe the existing query timeout.
  Nonrepresentable bin indexes/edges fail explicitly rather than silently
  coarsening or emitting nonfinite boundaries.
- Analytical CSV and ZIP counts distinguish exported pair/density rows from one
  analytical relationship. Density counts reconcile to the full pair population;
  auxiliary weather files retain separate pair-population metadata. Manifests
  enumerate auxiliary daily/weather files.
- Multiple pending sections resolve locally before any main query. Focused
  correction preserves the other sections; explicit removal and confirmed
  selection of at most four sections do not queue extra reports.
- Runtime faults remain section failures; all-failed reports are rejected.
  Incomplete persistence/export/sharing needs the exact acknowledgement.
  Listing allocations share the 10,000-row bound and fail without partial output.
- Owner/session/source/revision binding, original-session consent eligibility,
  retention rollback, stale preference rejection and atomic preference rollback
  are covered. V1 regressions remain in the complete suite.

## Shared E2E component evidence

[The shared E2E tests](../../tests/integration/test_exploration_shared_e2e.py)
exercise 002 numerical/table/persistence/export components with deterministic
synthetic proposals, not live ordinary-language interpretation.

| Case | Executed 002 component |
|------|------------------------|
| E2E-01 | Distinct destinations by origin against independent source sets |
| E2E-02 | Chronological monthly counts against independent grouped counts |
| E2E-03 | Clarification then snapshot-bound individual-record identities |
| E2E-04 | Inclusive period means, absolute change and signed relative change |
| E2E-05 | Anchored bins and exact known/missing reconciliation |
| E2E-06 | Complete same-flight pair identities and numerical values |
| E2E-07 | Ranked destination counts and deterministic ties |
| E2E-08 | Overall count and saved/table/CSV/table-PDF consistency |
| E2E-09 | Mixed four-section persistence/CSV bundle consistency, plus a separately injected runtime fault |

These use the fixture's actual January dates and observed origins. They do not
pretend to execute production June/EWR prompts against an absent population.
Single-section PDF checks cover table/text consistency, not graphics, tagged PDF,
screen-reader accessibility or 003 presentation acceptance. Composite graphical
PDF remains explicitly unsupported until 003 integration.

## Actual limited browser review

A temporary loopback-only Streamlit server and isolated synthetic SQLite history
were used without provider calls. Keyboard sign-in/history opening displayed all
four saved sections. Enter/Tab navigation reached and operated the presentation
target, selected/all-section scope target and daily-denominator selector.

Two automation attempts used an incorrect heading locator or overshot a dropdown;
corrected navigation passed. These were test-driver errors, not app failures.
The temporary server was stopped and its exact temporary database removed.

AppTest and accessibility tests additionally cover labels, statuses, session
isolation, incomplete acknowledgements and local controls. This is not a
screen-reader audit, a complete keyboard audit, a WCAG compliance claim or
numerically measured browser readiness.

## Actual synthetic cold/warm stage baseline

Final focused measurement:
`python -m pytest -q -s tests\performance\test_exploration_stage_timings.py -k offline_cold_warm`
produced **1 passed, 2 deselected in 3.07 seconds**, with no live inference.

- Provider category: `synthetic-stub`; one pair of measurements, not a latency study.
- Source: managed nine-flight synthetic fixture.
- Snapshot: `88a0d85a19b96d3dbccf642aec0968525496c25f66fdef78898c88e46de18b50`.
- Context: `0ca4830e377fd9b714997961ae0701f0ac28768ff5524b5af90553d9594f1877`.
- Source schema: 1.1; exploration catalogue: 2.2; strict V2 intent/result contracts.
- Cold: new executor/client in an existing pytest process, including source
  validation. This is not a cold operating-system cache or model-load measurement.
- Warm: same executor/client; no repeated source-validation stage.

| Stage | Cold seconds | Warm seconds |
|-------|-------------:|-------------:|
| Source validation | 0.0683187000 | Not repeated |
| Interpretation (stub) | 0.0013917000 | 0.0015444000 |
| Analytical execution | 0.6213956000 | 0.0242392000 |
| Table preparation | 0.0000204000 | 0.0000159000 |
| Export generation | 0.0007341000 | 0.0006504000 |
| Streamlit server preparation | Not measured in this offline path | Not measured |
| Observed browser readiness | Not measured | Not measured |
| Chart readiness | Not run; 003-dependent | Not run |

Timings are opt-in, context-local elapsed measurements with fixed stage names;
they record no questions, filters, entities, reports or raw provider bodies.
Nested different stages may overlap, so do not sum them into an SLA. The sample
does not measure real-provider quality, latency, quotas, cost or production-scale
dataset performance.

## Incomplete prerequisites and external gates

| Task | Status and required evidence |
|------|------------------------------|
| T061 | **Incomplete.** Only development scaffolding metadata exists. An independently authored candidate set still needs 100 unambiguous cases across ten families, 20 negatives, at least three variants of each AQ-01..10 and separate composites, with independent gold references. Exposed/agent-authored cases cannot become held-out evidence by relabelling. |
| T067 | **Blocked by T061 and independent people.** Two independent human gold reviewers, dispute adjudication and frozen corpus/source/context records are absent. No fabricated review-records file was created. |
| T068 | **Blocked by T061/T067 and fresh authorization/readiness.** No live candidate evaluation was run. Earlier individual synthetic provider probes do not authorize this run or establish the required overall/family/negative/AQ thresholds. |
| T069 | **Not conducted.** Five real analysts and per-task unaided/assisted results are required; synthetic tests or agent self-review cannot substitute. |
| T070 | **Not complete.** Actual joint 002/003 numeric/visual/PDF/export/accessibility evidence and outstanding 001 retention/provider/study gates remain necessary. |

The local implementation and evaluation tooling are available for those steps.
None of the automated results above converts these missing prerequisites into
passed release evidence.

## Provider clarification-envelope correction (2026-10-18 UTC)

A separately authorized Groq `openai/gpt-oss-20b` diagnostic reproduced
`json_validate_failed` for a distinct-destination-count request with an unnamed
airport. Local structural inspection of the rejected generation found one schema
error: the required root `selection_reason` field was absent. The generated
section otherwise requested origin clarification with `distinct_destination_count`.
The raw rejected generation was not persisted.

The interpretation prompt now explicitly requires all five root keys, explains
that required nullable fields must remain present, and includes a complete valid
clarification-envelope example. Strict provider/local schemas were not relaxed;
missing fields are not repaired or defaulted, and automatic retries/provider
switching remain disabled.

Offline provider/clarification/failure/context regression: **57 passed in 11.66
seconds**; focused Ruff and formatting checks passed. The added regression proves
that the prompt example passes both schemas and that removing `selection_reason`
reproduces the observed required-property failure.

One additional, separately authorized Groq verification with the corrected prompt
returned a locally validated `needs_clarification` envelope, an origin
clarification, `distinct_destination_count` and explicit `selection_reason=null`.
This verifies this prompt once; it does not establish paraphrase accuracy or
complete T068 live-corpus acceptance.

Request accounting: three individually authorized requests total. The first used
the terminal's Ollama configuration rather than the app-selected Groq provider
and did not reproduce the error; the second explicitly selected Groq and
reproduced it; the third explicitly selected Groq and verified the correction.
Each used normal dispatch/budget safeguards with tracing disabled and no retry.

## Readable V2 details and catalogue-wide connections (2026-10-18 UTC)

The user explicitly confirmed either-direction connections and inclusion of all
catalogue airports, including zero recorded connections. Catalogue version 2.3
adds the closed `airport_connections` population to the existing `entity_list`
operation. It preserves outgoing-only `distinct_destination_count` semantics.

The local pipeline unions the two orientations of each scoped flight edge,
deduplicates neighbour codes and left-joins counts to every reference airport.
It excludes missing endpoints and self-connections, counts unmatched neighbour
codes without inventing catalogue rows, and labels zeros as no recorded
connection, not no real-world service. Flight dates/attributes scope edges;
airport-code predicates scope catalogue rows. Paging, source/session/owner/revision
binding, persistence and bounded full-listing CSV reuse the existing listing path.
The updated authoritative intent schema is generated from the strict models.

Actual supplied-data verification, without provider calls:

| Check | Result |
|-------|--------|
| Independent outgoing SQL `GROUP BY origin, COUNT(DISTINCT dest)` | EWR 82, JFK 65, LGA 68 |
| All catalogue rows returned by the new bidirectional pipeline | 1,458 |
| Airports with at least one observed neighbour | 103 |
| Airports with zero recorded neighbours | 1,355 |
| Pages at 500 rows/page | 3, without duplicate or missing catalogue identities |
| Independent Python CSV graph comparison | Exact count equality for every catalogue code |

V2 report definitions, scope, missingness and pair/density details now use
readable native tables in labelled expanders instead of raw JSON. Pending
interpretations show labelled section summaries. Exact saved numerical values and
CSV field IDs remain unchanged; readable UI table headers do not mutate evidence.

New tests cover reverse-edge/repeated-flight deduplication, self-edge exclusion,
unknown neighbour references, zero-preserving airport/flight/date scopes, more
than 500 catalogue rows across pages and complete CSV, saved connection evidence,
provider projections for all three adapters, and JSON-free readable report UI.

Final full regression: **444 passed, 1 skipped in 94.56 seconds**.
Ruff passed, all 113 Python files passed formatting, and `git diff --check`
passed. Focused Pylance diagnostics reported no errors in changed report rendering,
compiler, metrics, models or app (existing unused cache-key/re-export hints remain).

The previously shared browser page reports failed server health checks; it is a
disconnected page, not evidence of the updated UI. UI verification in this change
is Streamlit AppTest, not a new successful live-browser or assistive-technology
audit. No additional live provider requests were made for this extension.

Catalogue version changes intentionally change semantic context binding. Existing
saved reports retain their original evidence; start a new explicitly worded
connection request rather than expecting an older outgoing-only report to change
meaning or resume against a different context.

## Recurring Groq missing-field failure: approved transport change

On 2026-10-18 UTC the user supplied another provider `json_validate_failed`
response explicitly identifying missing root `selection_reason`. This supersedes
the earlier prompt-only correction's reliability claim: one successful synthetic
probe did not eliminate the failure.

The user approved a Groq V2-specific compatibility trade-off: best-effort
`json_schema` transport with `selection_reason` optional on the wire. Only when
the envelope status is `proposed`, `needs_clarification` or `unsupported`, absence
of that field is converted to null. The complete authoritative local schema and
Pydantic validation then run unchanged, and a content-free log records the
compatibility event only after successful validation. Initial requests and
clarification requests share this boundary. Missing analytical fields, unknown
fields, invented measures, and absent selection-required reasons remain errors.
Other providers and V1 remain unchanged. No automatic retries or switches.

Offline provider/failure/clarification/budget validation: **93 passed in 14.53
seconds**; focused lint/format passed. The real ChatOpenAI HTTP adapter mock
checks `strict: false`, the single optional wire field, and a provider response
omitting that field, then verifies the fully validated canonical envelope.
Additional tests cover all three eligible statuses, invalid payload rejection,
one-dispatch behavior, content-free normalization logging and unchanged other
provider requirements.

No live request was authorized or made during this correction. This addresses
the specific missing-unused-field rejection structurally, but does not guarantee
that Groq best-effort generation will never fail for a different schema defect.

## Hosted V2 token deduplication (2026-10-18 UTC)

Removed duplicate embedded schema text from hosted V2 system prompts; the schema
is still sent in `response_format`. Removed nested schema `title` annotations
while retaining the root adapter name. Descriptions, catalogues, behavioral
instructions, clarification examples/context, limits and local validation remain
unchanged. Ollama and V1 retain their existing prompts.

Offline measurement used `o200k_harmony` on the same synthetic distinct-destination
question, with no follow-up context and no provider calls:

| Component | Before | After |
|-----------|-------:|------:|
| System and user message tokens | 3,730 | 1,613 |
| Separately supplied schema tokens | 2,126 | 1,814 |
| Combined content tokens | 5,856 | 3,427 |
| Conservative preflight total including unchanged 1,088-token allowance | 6,944 | 4,515 |

This is 2,429 fewer estimated tokens per request: approximately 41.5% of content
or 35.0% of conservative preflight total for this example. Actual provider billing
and model interpretation quality were not measured. Per-request maximum token
reservations remain unchanged; successful calls settle using reported usage.

Focused provider/context/clarification/failure/budget regression: **100 passed in
13.04 seconds**. Tests verify exact structural schema equivalence after removing
only title annotations, unchanged local prompts, preserved semantics/catalog
instructions and at least 30% reduction in this representative conservative
token estimate. Existing HTTP adapter mocks verify wire behavior. No live model
call was authorized or performed, and no capability or output limit was removed.

## Accumulated departure-delay month interpretation (2026-10-18 UTC)

One explicitly authorized Groq GPT-OSS 20B diagnostic for the user's monthly
accumulated-delay question failed local validation: the envelope's sections array
violated the non-selection minimum of one section. No analytical query executed.
This establishes the structural failure, not the provider's internal reasoning.

The prompt now explicitly requires 1..4 sections for all non-selection statuses,
including unsupported and clarification outcomes, and maps accumulated departure
delay to `departure_delay_total` / `positive_delay_minutes`. Highest/lowest month
uses ranking by `flight_month`, descending/ascending total and bound one.
Explicit net totals remain distinct; no invalid output is repaired or retried.

Offline regression: **77 passed in 13.24 seconds**; focused lint/format passed.
A numerical fixture verifies that positive accumulated delay picks January while
net delay picks February, preserving missingness disclosure and preventing a
mean/net substitution. Prompt tests verify mapping guidance and unchanged rejection
of empty-section envelopes.

A second, separately authorized Groq request using the corrected prompt returned
a locally validated proposed ranking: `departure_delay_total`,
`positive_delay_minutes`, `flight_month`, descending measure order and bound one.
This is one successful interpretation probe, not a corpus accuracy claim.

## Weather correlation interpretation: unresolved live failure (2026-10-18 UTC)

One explicitly authorized Groq GPT-OSS 20B diagnostic reproduced invalid local
intent validation for the weather/departure-delay question: section zero's
`measure_ids` violated its maximum item count. No analytical query executed.
The raw generated response was not persisted.

Added explicit prompt guidance for one `weather_relationship` /
`numeric_relationship` section, `mean_departure_delay` as the sole measure,
`pairing=null`, the fixed four weather outputs, origin-hour grain and optional
explicit origin grouping. No catalogue, local schema, provenance or numerical
safeguard was relaxed.

Offline provider/pair-metrics/airport-question regression: **53 passed in 10.60
seconds**; focused lint/format passed. This includes the independent weather
numerical tests and a regression retaining rejection of excess measures.

**Not fixed end-to-end:** a second separately authorized Groq verification still
returned `invalid_plan`. That verification recorded only the safe error category,
not the failing field; it does not establish that the second failure has the same
structural cause. No further request or retry was made. The prompt improvement
is persistent, but must not be represented as successful live acceptance.

The user then authorized one additional diagnostic request. It identified a
different malformed field: `pairing` contained `departure_delay` versus
`weather_precipitation_band`, which is not an allowed same-flight numeric pair.
Weather operations require null pairing because the fixed origin-hour pipeline
owns the weather variables.

Added field-level descriptions directly to the provider's `pairing` and
`measure_ids` schema properties, plus explicit weather-pair exclusion guidance
in the prompt. These are annotations, not relaxed constraints or repairs.
Regression tests reject both observed malformed shapes. The final focused run
was **53 passed in 10.21 seconds**, with lint, formatting and whitespace checks
passing. Three individually authorized live requests were made in this weather
investigation; none produced successful live interpretation. No request was made
after the last field-level guidance change, so live success remains unverified.

## Provisional Pearson with unverified weather units (2026-10-18 UTC)

The analyst could not confirm this local snapshot's physical units and approved the
proposed provisional correlation-only path. No reviewed unit declaration or evidence
was fabricated. Missing, invalid or stale provenance now permits the fixed four-variable
Pearson panel on recorded numeric values, with explicit unverified weather-axis labels,
a prominent UI warning and saved narrative/limitations. Unit-dependent precipitation-band
comparisons are omitted. Valid snapshot-bound provenance retains the original physical
labels and precipitation comparisons. Catalogue 2.4 binds this intentional behavior
change to a new semantic context.

Pearson remains dimensionless; positive linear unit conversions do not affect the
coefficient. This does not verify consistent source scales, missing-value semantics,
causality or significance. Existing pair counts, minimum sample/variance checks,
missingness partitions and full-population pair/density bounds remain unchanged.

Focused validation: **113 passed in 28.34 seconds** across weather numerical tests,
source provenance, summary/composite reports, persistence, CSV/PDF/ZIP exports,
provider/context/result contracts and headless Streamlit summary/composite UI tests.
Tests independently verify positive-linear-conversion invariance, provisional evidence
round-trips, unknown axis labels, omitted precipitation comparisons, verified/stale
declaration behavior and a visible four-coefficient panel without raw JSON.
Focused Ruff checks/formatting passed; Pylance reported no errors in the inspected
implementation files (the models module retains existing unused-reexport hints).

No hosted model call was made. This validates local execution/rendering with synthetic
provider responses, not live provider interpretation reliability. External acceptance
gates remain unchanged.

## Weather answer interpretation and report hierarchy (2026-10-18 UTC)

The analyst's supplied PDF contained four numerical coefficients but its answer only
described the weather operation. Findings were buried after extensive technical metadata.
Added deterministic evidence-derived findings: readable variable names, signed coefficients,
valid origin-hour counts, direction of association and the largest absolute available
coefficient, including ties. Unavailable/constant evidence and zero correlations receive
explicit wording; airport breakdowns retain separate populations. No unsupported significance,
causal, predictive or threshold-based strength claim is generated.

New reports persist these findings as their narrative. UI and PDF derive them from saved
weather evidence as well, so older reports with a generic narrative benefit without changing
their calculations or stored content. Weather PDF findings and coefficient table precede
technical metadata; omitted precipitation comparisons no longer render as an empty list.

Focused regression: **47 passed in 18.20 seconds**, covering numerical/weather evidence,
summary UI, summaries/composites and PDF exports. Tests reproduce the supplied coefficients,
their signs, largest association, ties, unavailable/zero wording and visible UI findings.
Ruff formatting/lint passed; Pylance reported no diagnostics for the findings implementation.
No provider call was made; browser validation used headless Streamlit AppTest.

## Calendar month versus pooled month-of-year (2026-10-18 UTC)

The analyst identified a missing semantic distinction: the catalogue only offered separate
calendar year-month groups, while the prompt unconditionally mapped highest accumulated
delay by month to that role. Added reusable `month_of_year` grouping (01-12 codes and month
names) and its persisted grain. This pools like-named months across the selected years,
preserves filters and works for compatible summary counts, means and totals. Existing
`flight_month` continues to mean YYYY-MM. Prompt guidance distinguishes explicit pooled
wording from unqualified calendar-month rankings and unsupported per-year winner requests.
This is not a fixed-question matcher. Catalogue 2.5 changes the semantic context.

Read-only inspection found the actual flight source contains 277,977 records, all in 2013.
Therefore the winning numerical total can legitimately coincide for these two questions
on this snapshot; the grouping identities and explanation must still differ.

Regression uses synthetic 2013/2014 data where February 2013 wins the calendar-month
ranking at 100 positive delay minutes, but January pooled across years wins at 120.
It also checks year filtering, missing and early delays, pooled count/mean definitions,
month ordering, preserved grain, saved history, CSV/PDF and headless UI. Provider mocks
exercise both structured grouping values and check the distinction in the prompt; they
do not prove live model interpretation.

Final focused regression: **119 passed in 20.19 seconds**. Ruff lint/format and whitespace
checks passed; inspected compiler, interpretation and generation files have no Pylance
diagnostics. The authoritative intent schema was regenerated from the closed models and
its equality regression passed. No live provider request was authorized or made.
