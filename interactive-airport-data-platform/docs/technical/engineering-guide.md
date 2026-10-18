# Extension guide, limitations, and glossary

[Documentation home](README.md) | [Previous: Testing, evaluation, and observability](testing-and-observability.md)

Implementation reference: 2026-10-18. See [scope and status](README.md#scope-and-status).

- [Engineering change recipes](#engineering-change-recipes)
  - [Add a metric or operation](#add-a-metric-or-operation)
  - [Add grouping or an entity alias](#add-grouping-or-an-entity-alias)
  - [Add a provider/model](#add-a-providermodel)
  - [Add a chart or persistable preference](#add-a-chart-or-persistable-preference)
  - [Change persistence](#change-persistence)
  - [Review checklist](#review-checklist)
- [Current limitations and implementation gaps](#current-limitations-and-implementation-gaps)
- [Glossary and recommended reading order](#glossary-and-recommended-reading-order)

## Engineering change recipes

### Add a metric or operation

1. Define population, grain, unit, numerator/denominator, weighting, missingness and reference
   requirements first.
2. Extend the local data catalog and operation/family compatibility.
3. Update schema/model invariants if a new contract shape is necessary.
4. Extend proposal resolution and local definitions/provenance.
5. Add deterministic parameterized compiler templates with declared output columns.
6. Add bounded execution/evidence construction, including scope and missingness.
7. Wire generator, renderers, exports and shared-summary eligibility where relevant.
8. Extend visual evidence only if saved results can support the chart without requerying.
9. Add independent oracle tests for numeric meaning, empty/null data, ties, unmatched references,
   invalid combinations and historical bindings.
10. Only then update prompt instructions and live interpretation evaluation.

Do not implement a new analytical capability by letting the model return an arbitrary SQL fragment.

### Add grouping or an entity alias

A grouping change must be reflected in catalog compatibility, typed resolution, SQL output,
evidence labels/statuses, editor options, rendering and exports. Airport origin/destination/any
endpoint roles must remain distinct.

An alias change updates local alias data and its context hash. Test ambiguity and reference-only
entities; never auto-select a fuzzy spelling suggestion.

### Add a provider/model

Implement settings/endpoint validation, adapter construction, supported schema transport,
token counting, disclosure, cost bounds, failure mapping and usage/header extraction.
Test with mocked HTTP transport before authorized live usage.
Never silently fall back to another model when quota or schema validation fails.

### Add a chart or persistable preference

Extend saved evidence/resolution first, then chart specification, accessibility description,
table alternative, export shape and historical-evidence tests. Extend the preference schema,
compatibility validation and repository optimistic update path together.
Changing only the chart-family enum is insufficient.

Presentation must not mutate analytical evidence or silently query fresh data to fill gaps.
Unsupported visuals should preserve usable exact tables with a reason.

### Change persistence

Preserve legacy decoding, unsupported-version errors, ownership, transactionality and private
retention. Add migration/restart tests against an existing database shape. Keep monetary
values decimal-safe. Do not reuse analytical revision numbers for preference concurrency.

### Review checklist

- Is the meaning consistent across prompt, catalog, resolver, compiler, evidence and exports?
- Are grouped/total counts and null/reference cases independently tested?
- Is the current snapshot/context binding preserved?
- Are new provider/tracing costs bounded before dispatch?
- Do failures preserve unsaved evidence and expose explicit safe statuses?
- Can historical reports still be read without source substitution?
- Does documentation distinguish an implemented API from a wired UI control?
- Are release limitations and test exclusions still stated truthfully?
## Current limitations and implementation gaps

These are implementation observations, not additional requested fixes:

1. Full visual preference persistence is unfinished. Table/default updates work; expected
   orientation/weather/evidence-binding preference fields and related tests remain outstanding.
2. Browser visual reporting is an opt-in preview. Cross-view/manual accessibility/full corpus
   acceptance is not established by ordinary local unit/integration tests.
3. Default-on acknowledgement/consent choices need production policy review; persisted default
   selections are not affirmative click evidence.
4. Interpretation cache and rate pacing are process-local and not identity/account-isolated or
   distributed. Concurrent provider traffic can still exceed quota.
5. Rate waits above 30 seconds are not proactively slept; the provider can reject the call.
   The retry gate is duration-based, including short-wait daily 429s.
6. Paid cached-input discounts are not separately calculated by the ledger. Cache telemetry is
   stored, but cost/quota treatment remains conservative under configured rates.
7. Unknown accepted/cost reservations have no automatic reconciliation workflow or expiry.
8. Some UI captions, environment-example comments, setup text and evaluator metadata lag
   implemented retry/visual/unit/authentication behavior. This guide explicitly distinguishes it.
9. Runtime schemas depend on the repository layout; no standalone-wheel deployment contract
   or fully locked build has been established.
10. Native Pango is an external prerequisite outside the supplied Docker runtime.
11. Daily calendar completeness and unit-sensitive weather comparisons depend on reviewed
    local evidence; observed activity alone is insufficient.
12. Shared copies survive private pruning/deletion and consent withdrawal. Production retention,
    backup expiry and deletion propagation remain unapproved.
13. There is no general-purpose public API, scheduled analysis service, distributed job runner,
    implemented HA setup, or concurrency/latency SLA.
14. Deterministic local calculations do not guarantee a language model chooses the intended
    interpretation on its first attempt. Inspect definitions and use clarification/corrections.

See the [V2 acceptance record](../../specs/002-natural-language-exploration/acceptance-results.md),
[visual acceptance record](../../specs/003-visual-reporting/acceptance-results.md) and
[retention checklist](../privacy-data-retention.md) for feature/release status. Specification
targets are not automatically completed implementation.
## Glossary and recommended reading order

| Term | Meaning |
|---|---|
| Proposal | Model-produced structured analytical intent, not yet executable authority |
| Resolved interpretation | Locally validated meaning bound to source/context and provenance |
| Grain | Unit represented by a record/value: flight row, date, airport-hour, aircraft, etc. |
| Population | Set of records/entities the operation measures |
| Weighting | How observations contribute: per flight, per day, per airport-hour, unique aircraft |
| Coverage | Evidence establishing whether calendar periods are complete |
| Missingness | Unknown values, absent references and eligibility exclusions |
| Evidence | Saved numerical results plus definitions/scope/provenance sufficient to explain them |
| Snapshot | Content-identified source dataset |
| Context | Snapshot plus relevant catalog/rule/alias/coverage/unit semantics |
| Revision | Version of analytical meaning/scope, not merely chart styling |
| Preview | Bounded saved subset; not necessarily the full matching population |
| Shared artifact | Separately retained consent-authorized reduced copy |
| Reservation | Pre-dispatch maximum exposure held in the usage ledger |
| Uncertain acceptance | The app cannot prove whether the provider consumed a failed request |

For an engineer's first pass:

1. Read [app.py](../../app.py) startup and submission flow.
2. Read [models.py](../../src/airport_analytics/models.py) alongside the two runtime schemas.
3. Trace [generation.py](../../src/airport_analytics/reports/generation.py) through local
   interpretation, compiler and executor.
4. Compare [catalog.py](../../src/airport_analytics/data/catalog.py) definitions to independent
   [test oracles](../../tests/exploration_oracles.py).
5. Read provider/budget/disclosure modules before enabling hosted requests.
6. Read report repository, consent service, visual evidence and export modules before
   changing persistence, sharing or presentation.
7. Run focused tests, then review acceptance records before making release claims.

---

[Documentation home](README.md) | [Previous: Testing, evaluation, and observability](testing-and-observability.md)
