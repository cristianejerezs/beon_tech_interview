# Data Model: Automatic Visual Reporting

**Date**: 2026-10-18  
**Authority**: [spec.md](./spec.md), especially FR-024 and the logical Visual Evidence table.  
**Status**: Foundation types/adapters implemented; downstream presentation/export work
remains pending. See [execution record](./acceptance-results.md).

## 1. Ownership and Source of Truth

`CompositeReportV2` remains the persisted analytical source of truth, with up to four
`ReportSection` objects and their typed outcomes. A visual section is derived from one
successful or valid-empty outcome; a failed outcome produces a failure notice, not a chart.
The analytical `revision`, `snapshot_id`, `context_id`, definitions, scope, values,
denominators and acknowledgement never change on a presentation action.

Visual Evidence is an immutable, typed in-memory projection, rebuilt from the owned
saved report and its applied preference. Do not persist a duplicate population of raw
pairs or renderer-specific JSON in the report. Persist only typed view preferences and
their evidence/rule bindings. Export manifests carry these bindings for reproducibility.

Implementation stores nested facts as canonical immutable `FrozenDocument` snapshots,
not mutable dictionaries inside a superficially frozen model. The source payload is
validated using the existing discriminated `ExplorationResult` union; `typed_result()`
returns a detached instance of that same shape-specific type. This preserves the complete
existing contract without duplicating eight analytical schemas or exposing mutable
references to the saved report. Legacy payloads remain version one.

## 2. VisualEvidence (version 1)

| Field/group | Type/meaning | Validation |
|-------------|--------------|------------|
| `visual_evidence_version` | Literal 1 | Closed contract |
| `selection_rule_version` | Fixed version string, initially `003.1` | Resolve known versions explicitly |
| `report_id`, `section_id`, `analytical_revision` | Saved identities | Match owning section; not log payload |
| `snapshot_id`, `context_id`, `source_evidence_version` | Saved provenance | Never use current source fingerprints as replacements |
| `evidence_fingerprint` | SHA-256 of canonical analytical interpretation and result | Stable across preferences; excludes narrative/presentation timestamps |
| `shape` | Discriminant described below | Declared form/roles determine it |
| `definition`, `measure`, `population`, `grain` | Existing definition and measure semantics | Unit/weighting/additivity/exclusions preserved |
| `dimensions` | Ordered `VisualDimension` list | At most two aggregate roles; no inferred temporal labels |
| `scope` | Saved filters/requested/observed period/coverage | Unknown remains unknown |
| `coverage` | Known bucket intervals/gaps or explicit unavailable reason | No verified calendar from observed min/max |
| `selection` | `VisualSelection` | Returned, analytical total and chart subset are separate |
| `missingness`, `limitations` | Saved count partitions and disclosures | Preserve unknown and overlapping counts without double-counting |
| `format` | Existing locale/rounding plus English rendering rules | Unrounded values drive calculations/order/ties |
| `payload` | Shape-specific union | Finite numbers; explicit unavailable values and reasons |

### Identity and precision

Category identity is `(field_id, code, reference_status)`, not a label. Encode this tuple
as canonical JSON for opaque selection tokens; it distinguishes null/missing/unmatched
from literal names like "Missing category". A multi-dimensional cell identity is the ordered
tuple of its dimension identities. Codes and raw display names remain available separately.
Do not build identities by joining text with a delimiter that source strings may contain.

Numeric fields use the existing `NumericValue`/`NumericEvidence` conventions. Reject booleans,
infinities and invalid numeric text, not coerce them into values. Keep original integers and
full saved numeric precision; display rounding is separate. Canonical fingerprint serialization
uses sorted keys, deterministic existing numeric serialization and disallows NaN/Infinity.
Its format/version is fixed and tested. It is not sent to providers or used as an auth token.

### VisualDimension

Fields: `field_id`, display label, `role` (`category`, `ordered_category`, `time`),
stable identities and declared order. Date roles identify recorded calendar date,
Monday-start week or calendar year-month. `weekday` is Monday-Sunday; `month_of_year`
is January-December pooled across scope years. A ranking can retain temporal labels while
presenting them as ranked categories. Raw string patterns never change the role.

### VisualSelection

Fields:

- Ordered applied category and series identity tokens.
- `shown_groups`, `returned_groups`, `available_groups` (nullable when unknown).
- Selected/returned/available series counts (unknown total is not inferred).
- Analytical selection/cutoff-tie information copied from the result.
- Visual omitted count relative to returned evidence; omitted identities when known.
- `selection_required` and machine-readable reason; `subset_origin` is default ranking,
  explicit analyst selection or all returned.
- Weather variable and airport selections, separately labelled from category/series limits.

All selected identities must exist in stored evidence. Persisted selections are never
queries for additional groups. Single-category charts cap at 20 identities, time series
cap at 20 selected series and grouped bars enforce their 8-series/20-primary thresholds.
Two-dimensional heatmaps retain the at-most-500 returned analytical cells; layout holes
are absent display cells, not additional evidence records or observed zeroes.

## 3. Shape-Specific Payloads

| Shape | Existing source | Required visual payload |
|-------|-----------------|-------------------------|
| `listing` | `ListingResult` | Saved columns/rows, page identity, total/completeness; no numeric chart from incidental values |
| `scalar` | `ScalarResult` or ungrouped `DailyMeanResult` | One value/reason, counts, denominator and requested rounding |
| `category` / `ranking` | `GroupedResult`, grouped `DailyMeanResult` | Ordered identities, exact values/reasons/counts, ties and provisional flags |
| `time` / `time_series` | Grouped result with declared time role and no ranking intent | Bucket keys/grain, optional series identity, exact known values and explicit gaps/coverage states |
| `two_category` | Grouped result with two non-time roles | Primary/series identities, sparse exact cells, distinct absent/null/zero states |
| `period_change` | `PeriodChangeResult` | Both saved periods/values/counts, day exposure, absolute and relative change/reasons |
| `distribution` | `DistributionResult` | Exact lower/upper boundaries, inclusion flags, counts, missing/excluded population |
| `relationship` | `RelationshipResult` | Both variables/units, pairing grain, pair count/partition/extents and all pairs or full density |
| `weather` | `WeatherPanelResult` | All returned coefficient populations, selected airport's four coefficients, selected variable's pairing, unit status and optional verified precipitation comparison |

An empty/invalid/unsupported chart state is carried by the presentation resolution, not
by fabricating a new analytical payload. Daily values retain eligible/known/unknown/
complete/incomplete-day fields; capacity retains lower-bound/provisional ranks and aircraft
models retain manufacturer-qualified identities. No extra averaging is permitted.

### Time evidence

Use saved requested/observed bounds separately. If exact verified bucket coverage was
not stored, set coverage unavailable/unknown with an explanation. Existing reports are
not backfilled from a newly loaded coverage declaration. Missing calendar adjacency can
break a line without claiming why a bucket is absent; inferred gap markers carry no
invented numerical value or source completeness.

For new analytical reports, if a verified bucket-coverage result is needed for partial/
complete flags, persist that bounded metadata at analytical generation time with its
snapshot/declaration reference. This is a directly coupled 002 handoff extension, not
a new analytics implementation inside the chart adapter. Old payloads decode with
coverage unknown. Do not store an unbounded origin/date coverage calendar in chart preferences.

The additive `ResultEvidence.bucket_coverage` defaults to `None` for old reports.
New temporal reports may save `SavedBucketCoverage` version 1 with snapshot/context IDs,
the verified declaration's SHA-256, and at most 500 non-overlapping per-origin closed
date intervals compressed from verified days. Gaps and dates outside those intervals
remain unknown, never zero. Only the existing generation path reads the already verified
declaration; the projection never loads it. The requested interval clips saved coverage,
not observed event extrema. An overflowing handoff stays unknown with an explicit saved
limitation; it is never silently truncated. This bound is on optional coverage metadata,
not a new analytical or displayed-group limit.

### Pair and density evidence

Preserve `source_id`, exact x/y, x/y units and extents for all stored pairs. Pair partition:
`pair_count + x_missing_only + y_missing_only + both_missing = scoped_count`.
For density, each cell uses stored edge indices and count; sum equals pair count.
Absent occupied-cell entries can become zero-count cells only when the saved full grid
and population reconciliation establish that zero. Keep endpoint inclusivity and actual
constant-axis extents distinct from the positive-width display interval. No sample/rebin.

### Weather evidence

Retain four variables (`temp`, `wind_speed`, `precip`, `visib`) per returned airport.
Coefficient is centered Pearson on unrounded pairs with no rank/other transformation,
dimensionless with pair count, unavailable reason and no significance claim.
Selected plots use the recorded weather variable on x and origin-hour mean departure
delay in minutes on y. Strongest-association ties use exact unrounded absolute coefficients.
`weather_units_status=unverified` preserves the recorded-unit axis label, provisional notice
and no precipitation bands. Verified evidence preserves its original physical labels.
Default selected variable is temperature and default airport is first in stable code order.
If its plot evidence is unavailable, retain temperature and explain why; selection of a
different variable is explicit. Coefficient unavailability does not itself invalidate pairs.
Airport `null` in an ungrouped panel means combined scope, not a missing airport category.

## 4. PresentationResolution

Fields: shape, `state`, effective view, compatible options, disabled reasons, Visual Evidence,
chart specification when eligible, accessible name/description and safe issue details.

State is one of:

- `ready`: valid graphical or scalar presentation.
- `table_selected`: explicit table, not a render failure.
- `selection_required`: evidence exceeds an automatic-selection rule.
- `no_plottable_data`: retained evidence but no eligible numeric marks.
- `missing_evidence`: historical shape cannot be reconstructed from saved facts.
- `invalid_evidence`: contradictory identities, metadata or count reconciliation.
- `render_failed`: preparation was valid but the local renderer failed.

Only ready graphical states promise chart output. Empty/all-null/constant/negative values
follow the spec's shape rules, not a generic sample-size threshold. Constant coefficients
can be unavailable while their paired scatter/density remains plottable.

## 5. SectionPresentationPreference Extension

Extend the existing closed model with backward-compatible defaults:

| Field | Meaning |
|-------|---------|
| `preference_schema_version` | New version 1; missing in old reports means legacy normalization |
| `chart_family` | Existing names retained; add `dot` and `grouped_bar` |
| `orientation` | `horizontal` or `vertical` for bar views, null elsewhere |
| `category_ids`, `series_ids` | Stable identity tokens; canonical order comes from evidence |
| `weather_variable`, `weather_origin_id` | Optional typed selections, valid only for weather |
| `visual_evidence_version`, `selection_rule_version` | Bound to known adapter/rule versions |
| `evidence_fingerprint` | Bind selections to this saved analytical evidence |

`default` resolves deterministically, `summary` only for scalars, `line` only for temporal
roles, `dot` for compatible category/period comparisons, `grouped_bar` only within thresholds.
`small_multiples`, `heatmap`, `histogram`, `scatter`, `density`, `table` retain their actual
shape meaning. Reject irrelevant orientation/selection fields and duplicate/unknown tokens.
The old model's max-length 500 list bound is not permission for a 500-category chart.

The persisted parent `preference_version` remains the transaction counter. It is different
from analytical revision, schema version and selection-rule version. Saving preferences
must not change report order, creation time, retention rank, question or analytical evidence.

## 6. Lifecycle and Conflict Rules

1. Owner loads report; decode and validate. Normalize old default/table preferences in memory.
2. Resolve shape/default, then apply any compatible version-bound preference. If stale/
   incompatible, explain the issue and offer a compatible view without rewriting storage.
3. Draft controls live in session state keyed by owner/report/section. Applying validates
   shape, identity and limits before replacing the last valid local view.
4. Save through existing owner-checked repository using expected parent preference version.
   Repository validates the full preference map against all targeted sections.
5. Conflict leaves the newer stored preferences intact and preserves the draft. Reload
   presents latest state; reapply is a separate explicit save after review. No automatic merge.
6. Export uses the effective applied selection bound to its version/fingerprint, not draft
   controls. A changed/deleted/pruned report requires reload or fails ownership validation.
7. Pruning/deletion removes preferences with the existing ten-report policy. Shared copies
   contain only the existing consented summary fields; do not add raw pairs, selection tokens
   or rendered assets to shared history.

## 7. V1 and Historical Compatibility

V1 `ReportContent` remains readable. Adapt only stored metric IDs, grouping roles, values,
source/scope and counts that are present. Map a known legacy metric through a versioned
legacy definition mapping; do not reinterpret it with the current catalogue silently.
Unknown fields needed to plot honestly produce an explicit missing-evidence table.
No writes or invented V2 analytical sections on read. Extend V1 `ReportContent` with
default-empty typed `presentation_preferences` and `preference_version=1`, using reserved
presentation section ID `legacy`. This is an additive decoding change, not a conversion
to V2. Extend the same owner/CAS repository method to return either saved-report type and
validate V1 preferences against its conservative adapter. Persist only on explicit save.
Known V1 evidence must support view/subset save and reopen under FR-015; unavailable
historical analytical facts still receive an honest missing-evidence explanation.
Keep analytical fields byte-equivalent in canonical decoded form across preference saves.

Historical V2 without visual preferences receives deterministic defaults; new fields have
backward-compatible absent meanings. Do not manufacture weather verification, coverage
completeness, omitted-group totals or pair populations. Future unsupported schema versions
produce a safe missing/unsupported presentation error, never permissive arbitrary rendering.
An unavailable original snapshot does not invalidate sufficient saved bounded evidence:
show it with a source-unavailable notice and disable historical paging/recalculation.
Absent saved plotting facts produce an explicit missing-evidence state, never a backfill.
