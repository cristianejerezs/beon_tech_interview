# Analytical Evidence, Report Persistence and Export Contract V2

Companion to the [domain model](../data-model.md) and [003 visual specification](../../003-visual-reporting/spec.md). This is the shared handoff, not implementation of 003's renderer.

## 1. Required common evidence

| Field | Meaning |
|-------|---------|
| evidence_version | Literal 2; stable payload schema, separate from report/intent versions |
| report_id, section_id, snapshot_id, context_id | Common report/source/semantic identity |
| analytical_definition | Approved operation/measure versions, population, grain, numerator/denominator, weighting and additivity |
| scope | Requested filters/entities/period, observed bounds, coverage status, verified/unknown/observed/eligible day counts and selected denominator basis |
| fields | Stable field IDs, category/code/display labels, units, numeric/date/category/ordinal roles, unit provenance |
| order | Category/series/time order, direction and deterministic code/source tie keys |
| values | Typed ordered selected aggregates, bins, pairs or cells; finite unrounded numbers/null with explicit reason |
| missingness | Named grain-specific populations and disjoint exclusion partitions where applicable |
| selection | Available/selected/displayed/omitted counts, exact total, bounds, tie flags and completeness |
| format | English number/date conventions, units, default computed2 decimals and requested half-up rounding override |
| limitations | Application-owned safe statements derived from evidence, including partial coverage/provisional capacity/no causality |

Category identity uses stable codes, not display text. Duplicate names show code; plane models use manufacturer+model. Category grouping retains unmatched/missing categories with explicit statuses; these are not aliases for an observed zero.

Do not store redundant independently calculated chart values: evidence values are the single analytical source for chart/table/export. Presentation subsets refer to stable identities within selected evidence and disclose shown/available counts. Neither switching chart type nor reopening invokes interpretation or changes scope.

## 2. Reconciliation and missingness

- Counts/identities/order/bin membership are exact. Finite computed values pass only when `abs(actual-expected) <= max(1e-9, 1e-12*abs(expected))`; unavailable reasons/nulls exact. Validate unrounded values.
- Flight summaries show filtered flight count, applicable known/missing measure count and reference-match coverage before match-only exclusions. A known zero stays zero; no known observations produce null/reason.
- Aggregate group evidence includes `scoped_count`, known `sample_size` and `missing_count`; known plus missing must equal that group's scoped population. These optional fields are supplied together; legacy/other result evidence does not invent unavailable group populations.
- Daily means compute complete eligible date evidence first, then select supporting rows<=500. Keep requested/verified/unknown/observed/eligible and per-weekday denominators, including verified zero-flight dates. Unknown coverage does not become zero.
- Capacity tracks known/unknown seat flights, daily known sums, complete/incomplete days and no-flight zero days. An operating airline with no known seat contributions is unavailable; incomplete known sums are lower-bound proxy evidence with provisional rank, not a full-capacity winner.
- Flight pairs partition scoped rows into both-known / x-missing-only / y-missing-only / both-missing. Nonfinite invalid source values fail validation.
- Weather first forms distinct scoped origin-hours and counts contributing flights/known delays. Partition hours into weather-unmatched, weather-matched-without-known-delay, and weather-matched-with-known-delay; the last partitions per variable into known/missing weather. Separately disclose no-known-delay hours across matched/unmatched populations without adding overlapping totals as if disjoint. Each coefficient's pairs are unique equal-weighted origin-hours.
- Weather panels persist `weather_units_status` (`verified` or `unverified`). Unverified panels provide provisional dimensionless Pearson coefficients on recorded numeric values, label weather axes `recorded units (unverified)`, include explicit limitations and omit unit-dependent precipitation comparisons. Do not infer physical units or manufacture provenance. Positive linear unit conversions leave Pearson unchanged; consistent scales and valid numeric semantics remain assumptions. The verified path retains snapshot-bound local evidence checks. Legacy panels predate this extension and required verified units, so a missing status defaults to `verified`. Catalogue 2.4 binds the changed behavior to a new semantic context; old report evidence remains readable.
- Precipitation comparisons retain a matched-but-missing-precipitation category; weather unmatched is disclosed separately. This descriptive comparison uses the approved weather-context flight mean, clearly labelled flight-weighted rather than the coefficient's hour-weighted grain.
- Distinct-aircraft frequencies disclose unmatched/null tail references and missing raw manufacturer/model labels independently of known ranked categories; do not merge raw manufacturer spellings.
- Rankings compute exact total groups, visible/cutoff ties and complete maximum equality before LIMIT. For AQ monthly/aircraft winners, identify tied maxima. If the entire winner identity set itself exceeds500, require explicit narrower scope before claiming a complete winner list; never silently call a single selected row the winner.
- A valid-empty result preserves exact zero matching records and scope; source failure or absent historical rows is not a valid empty result.

## 3. Bounds and 003 handoff

The authoritative analytical evidence bounds are defined in [002's evidence-bound table](../spec.md#evidence-bound-table). Primary aggregate results have one 500-group ceiling per section. Daily supporting evidence has one separate 500-row pool per section across all dates, airlines, origins and weekdays, never a new allowance per category or supporting collection. Supporting routes have a separate 500-row pool. These explicitly distinct evidence kinds do not increase the selected primary result, create export-listing allowances or change a calculation's denominator. Counts, omissions and deterministic order are disclosed independently for each pool. No pagination or split export bypasses a pool's ceiling. Composite<=four sections.

Relationships use all valid pairs if count<=5,000. For larger populations, build full-population counts on at most20x20 cells, with one positive-width interval for a constant axis. Define min/max-anchored equal-width cells, left-closed/right-open except final cell includes max, explicit edges and counts; do not sample or truncate first. Store exact pair count, excluded partition, axis extents, boundaries and reconciliation. Constant axes still permit pairs/density but make Pearson unavailable. Each weather variable uses its own valid population.

003 receives semantic roles and complete available evidence, not an authoritative model-selected chart. Its visual family thresholds, selection requirements and alternatives remain in 003. It must not re-bin distributions, aggregate non-additive metrics into "Other", switch denominator basis or mix numeric units on one axis.

Evidence for all four weather variables is one predefined panel. Optional origin breakdown shares the same definitions/units and preserves per-origin missingness; no arbitrary regrouped coefficient is inferred. Tables reveal coefficients/counts/reasons and precipitation summaries alongside associated pair/density evidence, not a fabricated overall weather coefficient.

## 4. Snapshot-bound browsing and exports

Page and count compilation use identical predicates over loaded immutable snapshot tables. Only fixed application-owned order/column definitions are allowed; values are bound parameters. Recheck source/context fingerprints on continuation. A change disables old paging/recomputation and requires explicit restart, even if a process still has cached rows.

Record/list export is a separate explicit action, not the visible page download:

1. Bind selection to report revision/owner/snapshot/context and count available rows.
2. Choose explicit per-listing-section allocations for a combined file, sum<=10,000.
3. Require confirmation whenever any selected listing population is partial.
4. Query deterministic bounded slices locally, never send rows to models.
5. Build the complete export before offering download; source/compilation/rendering failure yields no partial artifact.

CSV preserves the existing UTF-8 BOM, RFC-style quoting and wide result-table layout. Single-section files add reserved `_meta_` columns for section/snapshot/context identity, serialized scope/definition, denominator basis, completeness and exported/total counts; a labelled metadata-only row covers empty/failed sections. Reserved names cannot collide with catalog columns. Full-precision finite numbers and ISO dates are preserved; a `_meta_null_fields` list distinguishes null from an empty text value. Spreadsheet text cells are reversibly escaped against formula execution without changing stored evidence; disclose/test the transport rule.

For a composite, prefer one local ZIP download containing per-section CSVs plus `manifest.json`, using standard-library support rather than a new flattened analytical format. The manifest retains every requested section/status, common identity, allocations, row counts, omissions/ties/failures, field types and escaping/null rules. The sum of listing data rows across the files remains<=10,000 for that export; a ZIP container is not a loophole to multiply the bound. Aggregate exports contain selected analytical rows<=500/section, not an undisclosed larger population. Both standalone CSV and composite manifest must preserve scope/partial disclosures; the download is clearly labelled as a CSV bundle rather than falsely named one CSV.

Incomplete analytical reports require acknowledgement independently of partial-listing confirmation. Retain all requested section identities/statuses and safe failure notices in every representation. Table-only export remains available under 002; do not label it a chart-complete 003 PDF. Actual graphics, tagged structure/font/layout/reader evidence and technical all-or-nothing PDF failures are 003 gates.

## 5. Persistence and legacy adapter

SQLite report row ownership remains authoritative; JSON analyst IDs cannot override it. Decode absent `report_version` using existing V1 validation; literal2 using strict V2. Unsupported/corrupt versions produce safe explicit load errors, never first-section fallback. No destructive bulk migration or source-dependent recomputation on open.

V1 adapters preserve existing single report/table/export behavior and disclose evidence unavailable in historical payloads. A V1 follow-up may produce V2 only after translating supported scope and, where source/context differs, explicit current-snapshot acknowledgement. Legacy reports do not silently acquire 003's new chart/PDF guarantees.

V2 saves require all original active sections' outcomes, one common snapshot, validated bounded evidence and acknowledgement when incomplete. One parent is one retention slot; no all-failed reports or permanent drafts. Report generation time stays immutable when acknowledgement arrives; consent eligibility is checked against original content creation/session and existing exclusions, not reset to the later acknowledgement timestamp.

Report insertion and its associated ten-report retention pruning must commit atomically. An interrupted or failed transaction must preserve previously committed reports, roll back any associated pruning and never show save success. Keep unsaved results in the current session where possible and provide an explicit retry action; session/process loss does not imply that uncommitted results were durably saved.

Shared FAQ/improvement artifacts use their own versioned safe section summary: section label, analytical definition, scope, approved narrative, bounded existing summary evidence and outcome category. Successful summaries may be published only under applicable pre-existing consent/retention gates. Incomplete artifacts retain failure disclosures and never present failed sections as answers. FAQ selection injects question wording through the existing form path, not a privileged precomputed plan or bypass of interpretation/disclosure.

003 preferences are keyed to owned parent/section ID and preference version; updates cannot edit evidence, interpretation or created_at. Reject stale updates, foreign owner IDs, incompatible chart alternatives or changes requiring recalculation. Analytical correction creates a new report revision. Parent pruning/deletion removes embedded preferences/evidence; separately retained shared artifacts follow existing consent/owner-approved deletion policy.

Preference updates must be atomic and version-checked. A failed, interrupted or stale update leaves the prior committed preferences and analytical evidence unchanged, reports an actionable failure or conflict rather than success, and permits explicit refresh/retry against the current version. It must not silently replace another committed update.

## 6. Operational observability and evidence records

Telemetry may contain random request correlation, schema/catalog versions, provider/model ID, authorized budget metadata, safe outcome categories and durations. It must not contain prompts, entity labels, filter values, source rows, generated content or raw exception bodies. Use local approved synthetic fixture records for numerical comparison details. Record performance under cold/warm conditions; no numerical SLA or queued architecture is implied.

These content exclusions govern application logs, diagnostics, performance events and evaluation telemetry. Optional LangSmith tracing is a separate channel governed by 001's explicit operator configuration, user-facing disclosure/acknowledgement and shared-budget requirements. Its notice must accurately describe transmitted content, including any clarification or interpretation context; it does not authorize sending report evidence to an inference provider. No content-bearing trace may be emitted when tracing is disabled. Ordinary telemetry never inherits the tracing exception.
