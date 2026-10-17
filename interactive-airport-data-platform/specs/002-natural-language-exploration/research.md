# Research Decisions: Natural-Language Exploration

**Date**: 2026-10-17
**Scope**: Phase 0 design, not implementation or live-provider acceptance.

## 1. Reuse the application boundary, version the intent contract

**Decision**: Introduce a strict V2 intent envelope and local resolved interpretation rather than stretching V1's single metric/intent record into listings, paired observations and four sections. Keep V1 report parsing and tests; use a typed V2 discriminant for new reports. Reject extra fields, unknown IDs, invalid finite values and unsupported metric/dimension combinations before analytical execution.

**Rationale**: `models.py` currently represents one plan; `plan_schema.py` points at the original schema. `model_client.py` emits one provider-constrained object; a prompt alone cannot add a state machine or two-stage calculations. Existing catalog/parameterized compilation remains the authorization boundary.

**Alternatives considered**: Hardcoded AQ sentence routing loses general language abstraction; arbitrary SQL/tools expose unacceptable scope; duplicating the whole app or keeping two independently evolving runtime paths adds unnecessary complexity. V1 live calls may remain regression-testable while the default interactive flow adopts V2.

## 2. Separate untrusted proposals from trusted resolved scope

**Decision**: Model proposes closed operation IDs, entity mentions, scope edits and clarification intent; application assigns request/section identities, resolves snapshot/coverage, validates catalog matches and records field provenance. Only question text, catalog definitions, approved public entity/alias context and a minimal active interpretation summary enter prompts. Never send analytical rows, numeric report answers, ownership IDs or raw private history.

**Rationale**: Schema correctness is not semantic correctness. Need explicit changes/removals rather than relying solely on the current regex follow-up cues. SDK projections preserve provider-subset compatibility (especially Groq's date-shape constraints) while full local validation remains authoritative.

**Alternatives considered**: Supplying whole reports to improve interpretation violates data minimization; model-chosen snapshot/coverage is not trustworthy. A second "repair" provider call risks budget/no-retry behavior and is not planned.

## 3. Session-only pure state transitions and native controls

**Decision**: Pure transition functions operate on analyst-session/request-revision/section identity and answered-turn counts. State is held in existing Streamlit session state, never a mutable global/shared cache. Labelled native choice/free-text/correction controls preserve pending scope and respect callback-before-widget lifecycle. Submit-time revision checks reject stale messages. Three answered turns lead to guided correction, not recursive model calls.

**Rationale**: Existing app shows a clarification message but does not complete a pending conversation. Current FAQ callback/form retention patterns are valuable prior art. Provider failure is an operational state, not an answered clarification.

**Alternatives considered**: Persistent conversation transcripts add retention without requirement; background workers and distributed stores exceed single-host scope.

## 4. Resolve entities deterministically, suggest rather than guess typos

**Decision**: Reuse local airport/airline references and validated observed code sets. Exact case-insensitive codes precede normalized names and a versioned hand-reviewed alias map. Standard-library `difflib` may rank spelling suggestions; it never auto-authorizes a fuzzy match. Name normalization preserves distinct codes; candidate order is deterministic and unknown codes block resolution.

**Rationale**: Matching policy can be explained and unit-tested without new dependency, vector database or private-data retrieval. An exact reference-only entity can be resolved but still have zero observed flight matches.

**Alternatives considered**: Edit-distance-only automatic matching is unsafe for short codes. Embeddings and model-only entity choice add unpredictability/cost. Alias entries require source provenance and review; no exhaustive alias quality claim is made.

## 5. Explicit owned multi-stage queries, not generalized model expressions

**Decision**: Reuse filter/date/join compilation for all operations. Add closed templates for count/list/aggregate, daily-distinct mean, daily-capacity mean, period change, bins, flight pairs, origin-hour correlation and manufacturer/model frequencies. The compiler may emit application-owned `WITH ... SELECT` as well as `SELECT`; replace the current text-prefix assumption with a compiled-query kind/ownership boundary. Models cannot supply CTEs, expressions, table names or query text.

**Rationale**: The executor currently rewrites a last LIMIT parameter and assumes all operations share one shape. V2 execution instead uses named compiled-purpose objects (main/evidence/count/page/export), with explicit bound parameters and output schemas. All complete-population calculations precede display limits and reuse identical base predicates.

**Alternatives considered**: Python full-population fetch for convenience violates bounded evidence; interpolating model formulas is unsafe; deriving distinct means by dividing global distinct counts is mathematically wrong.

## 6. Snapshot-specific coverage is a semantic declaration

**Decision**: An optional operator-supplied local declaration follows [coverage.schema.json](contracts/coverage.schema.json), keyed to the full snapshot hash, origins, inclusive intervals/gaps and documentation/validation provenance. Absence is explicitly unknown, not a fatal loss of ordinary observed-record analytics. A supplied malformed/conflicting/stale declaration is visibly rejected; it cannot silently create verified days. No default verified declaration is generated for the supplied CSVs.

**Rationale**: The source directory contains five CSVs and no coverage documentation/declaration. Observed min/max dates or some flights on a date do not prove completeness. Date spines must distinguish verified zero from unknown.

**Alternatives considered**: A boolean environment flag or reviewer click cannot verify data. Always refusing every daily mean is unnecessary because the owner approved an explicitly selected observed-operating-day alternative.

## 7. Calendar and numerical semantics

**Decision**: Use recorded departure dates, ISO weekday 1-7, Monday-start calendar weeks, and year-month identities. Date arithmetic is calendar-based, not viewer-zone/DST conversion. Compute daily sets before equal-day means; use Decimal half-up for requested display rounding without altering stored values. For daily count means, derive display rounding from the retained exact integer numerator/denominator, not an intermediate binary float that could move a half-up boundary. Accumulated delay sums positive known minutes by default; net signed sum is a separate operation. Plane frequency defaults to distinct observed tail numbers, not full-reference fleet or flights.

**Rationale**: A read-only local DuckDB probe confirmed Sunday ISO weekday 7, Monday week-start and `corr` availability. All these operations still require fixture-based independent verification in implementation.

**Alternatives considered**: Locale weekday sorting, summed distinct counts, averaging previously averaged groups, or rounding before calculation all change meaning.

## 8. Weather correlation and source units

**Decision**: Validate exact origin/time_hour keys, aggregate filtered non-missing flight delays to origin-hour means, then pair each mean with temperature/wind speed/precipitation/visibility separately. Use `corr` with explicit n>=3 and nonzero-variance guards, checked against an independent centered-sums oracle. Preserve pair counts and per-variable excluded-hour partitions. Full pairs up to 5,000 or a full-population 20-by-20 density feed 003; no fitting/p-values or arbitrary coefficient targets.

**Rationale**: Repeating one weather observation for many flights changes the selected equal-hour weighting. Upstream [nycflights13 weather documentation](https://nycflights13.tidyverse.org/reference/weather.html), consulted 2026-10-17, defines temperature in F, speed in mph, precipitation inches and visibility miles, with origin/hour merge keys. Local column names match, but that does not alone prove the transformed local files preserve those units.

**Alternatives considered**: Flight-weighted coefficients conflict with the owner decision; causal or significant-language conclusions exceed authorization. Weather-unit provenance is an acceptance prerequisite: invalid/missing provenance blocks the weather calculation's correctly labelled result and offers explicit correction/removal, without disabling unrelated analytics.

## 9. Persist bounded report evidence and retain legacy behavior

**Decision**: Keep one SQLite row per report and version JSON payloads. Decode unversioned rows as V1 and V2 as typed composite content. Read through one compatibility adapter; do not overwrite historical payloads to invent missing coverage/shape evidence. New revisions create new report IDs; section preferences may update only presentation fields with optimistic version checks and owner scope.

**Rationale**: `ReportRepository`, app history, FAQ creation, refinement and exports currently access top-level single-plan/rows directly. Every consumer must use the adapter; adding sections only to generation would leave most surfaces broken. Ten-report pruning and consent timing remain parent-report operations.

**Alternatives considered**: One row per section incorrectly consumes retention slots; indefinite pair/record sidecars create orphan retention risks. Recompute paging/large listing exports only against the matching live snapshot; saved bounded evidence remains usable when source rows disappear.

## 10. Independent evaluation and honest release evidence

**Decision**: Version separate development/held-out suites; canonicalize typed scope deterministically, not with model grading. Two reviewers freeze expected labels. Independent CSV-set/date/Decimal/math oracles do not import production compiler/metrics functions. Report request and section results separately; one failed section fails a composite. Provider failures stay failures, never filtered out or replaced by cherry-picked retries.

**Rationale**: Existing evaluation is fixed at twelve questions and absolute-only tolerance; it must retain its original regression while V2 adds the new gates. A bounded offline research agent recommended independent selection/identity and numeric stages, semantic canonicalization and frozen no-retry runs. Adopted with stricter privacy: do not persist raw provider outputs as routine run evidence; synthetic corpus/expected data and safe comparison categories suffice. Private debugging exports would require separate explicit review, not this plan.

**Alternatives considered**: Exact JSON equality rejects equivalent singleton/date encodings; fuzzy scope equality admits wrong filters. Account terms, genuine provider compatibility, held-out authorship and real participants cannot be fabricated by a passing mocked suite.

## Research boundary

No unresolved implementation-choice placeholders remain. Data provenance, coverage declarations, candidate quota/terms verification, real reviewers/participants and 003 rendering/accessibility are explicit evidence gates. No dependencies were installed and no hosted model call occurred during planning.
