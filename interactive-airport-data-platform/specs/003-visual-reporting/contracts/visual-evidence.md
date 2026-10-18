# Contract: Visual Evidence and Deterministic Chart Preparation

**Version**: Visual Evidence 1, selection rules `003.1`  
**Status**: Design contract; no public HTTP API is introduced.

## 1. Boundaries

Inputs are an owner-loaded `SavedReport`, section ID, and optional applied typed preference.
The report-level preference counter is a separate concurrency/export-binding token,
not part of the immutable analytical evidence fingerprint or selection-rule version.
Output is a `PresentationResolution` over immutable Visual Evidence as defined in
[data-model.md](../data-model.md). Adapters/builders are pure: no model/client, DuckDB
executor, source directory, mutable catalogue lookup or network resource is available.

Suggested internal boundaries:

- `prepare_visual_evidence(report, section_id)`: validate/adapt saved facts.
- `resolve_presentation(evidence, preference)`: validate subset and compatibility/defaults.
- `build_chart(resolution)`: produce an application-owned Vega-Lite specification.
- `describe_visual(resolution)`: produce name, data-grounded explanation and disclosures.

Exact Python signatures belong to implementation. These functions must not accept
arbitrary analyst-authored Vega/HTML, SQL, renderer options or asset URLs.

## 2. Classification Precedence

Validate the common evidence contract first. Apply first matching shape:

| Order | Evidence/intent | Required outcome |
|-------|-----------------|------------------|
| 1 | Listing | Paginated/saved-preview table; incidental numeric columns do not chart |
| 2 | Distribution | Exact-bin histogram; no renderer-side bin operation |
| 3 | Relationship or declared weather bundle | Scatter/density; weather includes four-coefficient overview and selected pair plot |
| 4 | Period change | Two-period comparison plus separate absolute/relative summaries |
| 5 | Ungrouped aggregate/daily mean | Summary card or unavailable summary |
| 6 | One temporal role, optional category, without ranking intent | Chronological line/markers or series view |
| 7 | Explicit ranking with one grouping role | Ranked categories, including date labels |
| 8 | One/two categorical or ordered-category roles | Bars/dots or grouped bars/heatmap |

Reject contradictory metadata rather than selecting by label appearance. A one-row grouped
result stays grouped. Two unrelated numeric columns do not form paired evidence.
An unsupported two-dimensional ranking receives an explicit table/refinement explanation;
do not silently erase a role to fit one-dimensional ranked bars.

## 3. Default/Compatibility and Bounds

| Shape | Default | Alternatives / fixed restrictions |
|-------|---------|-----------------------------------|
| Scalar | Named summary card | Table; no fabricated bar/trend/scatter |
| Single category | Vertical bars | Horizontal/vertical bars, dots, table; at most 20 categories |
| Ranking | Horizontal bars | Dots/vertical bars/table; validated rank order and ties |
| Time | Chronological lines with markers | Chronological bars/table; one finite period is an isolated marker |
| Time plus category | <=8 selected series: lines; 9..20: small multiples | Small multiples allowed for 1..20; lines disabled above 8; table |
| Two categories | <=8 series AND <=20 primary categories: grouped bars | Otherwise heatmap; both compatible only when grouped-bar thresholds pass |
| Period change | Side-by-side values plus visible text/value change summary | Paired dots/table retain the same summary; no separate change chart; percentages separate from base-unit axis |
| Distribution | Adjacent exact-width numeric bin bars | Exact bin table; <=100 stored bins |
| Relationship | <=5,000 complete pairs: scatter; above: saved complete density | Corresponding exact table; no scatter/density toggle requiring unavailable pairs |
| Weather | Four coefficients/findings plus selected variable scatter/density | Selected airport/variable, table; coefficient dots use fixed [-1,1], not physical units |
| Listing | Table | No automatic numeric alternative |

Null values remain unavailable with reasons and exact table entries. One finite value is
eligible for its actual shape. All-zero marks retain labels and an explicit all-zero note.
Negative-only/constant measures remain plottable where analytically valid. No arbitrary
minimum two-observation rule; Pearson retains its separate saved three-pair/variance checks.

### Selection rules

- For one-dimensional ranked results above 20 categories, default to first 20 returned
  groups in validated order; disclose both analytical and visual omissions/cutoff ties.
  Do not expand the chart past 20 to include ties; disclose tied omitted values instead.
- Unranked one-dimensional results above 20 require explicit selection; never choose an
  arbitrary top subset. More than 20 returned time series likewise require selection.
- Selected identities are existing evidence only. UI input order cannot reverse canonical
  rank, chronological, ordinal or stable-code order.
- In two categorical dimensions, grouping[0] is primary and grouping[1] is series.
  The heatmap represents exactly the returned sparse cells. Unreturned combinations are
  absent, known-null cells unavailable, and observed zeroes actual numeric zeroes.
- Persisted preference IDs that are absent, duplicated or over limit fail validation.
  An invalid draft does not replace the last valid applied view.
- Explicit table view retains the selected population and discloses a broader saved
  evidence table separately. Reset returns the deterministic default; it does not recompute.

## 4. Time and Ordered Categories

Known temporal roles are `flight_date`, `flight_week`, `flight_month`; use numeric/date
bucket keys, Monday weeks and original recorded calendar dates. Set time-zone applicability
to "not applicable - recorded departure date". Do not apply viewer/UTC conversion.

`weekday` and `month_of_year` are ordered categories, not timestamps. Month-of-year
values pool across scoped years and keep that explanation even on a one-year snapshot.
Ranked YYYY-MM values are ranked categories, not a historical trend.

Line segments require consecutive known eligible bucket values within one series.
Null/absent buckets break the segment. Where saved verified coverage establishes an expected
domain, generate unavailable gap placeholders without zero filling; where it does not,
use known bucket adjacency and disclose "coverage completeness unknown". Do not infer
complete/partial coverage from an event's first/last date. Requested partial calendar
boundaries, verified coverage gaps and measure missingness are independent flags.

Entirely unavailable selected series retain labelled legend/evidence presence; no fictional
line or removed identity. Shared-scale panels use comparable ranges for the same measure.

## 5. Distribution, Pair and Weather Invariants

### Distribution

Use exact bin boundaries and inclusion flags; bars meet according to numeric intervals,
not equally spaced invented categorical widths. Zero-count bins stay present. Show
non-numeric/null/missing/excluded counts separately. No valid observations means no
histogram and a clear retained-population explanation.

### Pairs/density

- Scatter uses all stored valid same-flight or origin-hour pairs through 5,000.
- Above 5,000, use the stored full-population density, never first-5,000 points.
- Both varying axes: 20 by 20; one constant: 1 by 20 or 20 by 1 according to axis;
  both constant: 1 by 1. Each varying axis uses 20 equal-width intervals over its
  observed range; each constant axis explicitly includes its sole value.
  Preserve actual extents, positive display intervals, exact edges and counts.
- Cells include lower/exclude upper, except final maximum-inclusive interval. Constant
  intervals explicitly include the sole observed value. Zero cells can be expanded from
  complete grid evidence only; they are distinct from unavailable evidence.
- Sum of cells equals saved valid-pair population. Partition exclusions are disjoint,
  and x/y missing counts do not double-count both-missing rows.
- No automatic new density over unknown pairs; missing evidence is an explicit failure.

### Weather

Use fixed temperature/wind/precipitation/visibility populations, with equal origin-hour
weighting and the saved coefficient for each. Show the overview/findings first. Default
selected variable is temperature; explicit per-airport reports default to stable first
airport. Preserve unavailable variables in the overview. Do not replace a missing variable
with a different one silently.

Coefficient dots may share a dimensionless [-1,1] scale; raw variable plots never share
mixed physical units. Unverified units retain the provisional recorded-value label and
omit unit-dependent precipitation comparisons. Selection changes neither coefficients
nor their pair denominators. PDF includes the overview and selected airport/variable plot;
all returned coefficient evidence remains available in exact tables/CSV.

The coefficient is centered Pearson on saved unrounded pairs, without ranking or other
transformation. Weather is x; hourly mean departure delay in minutes is y. Default
temperature remains selected when its plot evidence is unavailable: show the specific
reason and allow explicit variable selection, without automatic fallback. An unavailable
coefficient does not suppress valid pairs (for example, constant axes or fewer than three
pairs). Compare available absolute coefficients using unrounded saved values and disclose
all equal strongest values within the selected airport; do not infer ties from display rounding.

## 6. Chart Grammar and Accessible Explanation

- Only embedded `data.values` and application-owned scales/marks; reject `data.url`,
  external images, external expressions or user-supplied transforms.
- No Vega aggregation/binning/regression/filter that changes numerical meaning.
  Visual selection is applied by the validated adapter before chart specification creation.
- Bars include zero and negative values; quantitative axes linear. No dual axes, broken
  scales or 3D. Pair x/y axes use their respective units and valid extents.
- Stable code/name mappings and non-color cues: series dash/marker, panel label, direct
  labels or shapes. Static labelled legends rather than inaccessible interactive legends.
  Missing heatmap cells use distinct patterns/markers plus explicit table states.
- Name pattern follows FR-018/accessible explanation rules: chart family, measure/unit,
  dimensions or pair, period. Description gives scope, shown/available counts, omissions,
  missingness and coverage. Source names are data, never markup.
- PDF includes both the visible evidence-derived description and its associated tagged
  figure alternative, generated from the same resolution, not independently authored findings.
- Explain extrema/ties within shown scope; never infer global winners from a subset.
  Period summaries distinguish minutes/counts from percentages. Weather findings use
  saved coefficients without significance, predictive or causal conclusions.
- Browser/PDF share English formatting: integer counts, two decimals for computed values/
  percentages except approved analytical/AQ rounding or explicit saved requested precision.
  Explicit precision overrides an unqualified default. Exact raw values remain in evidence.

## 7. Required Contract Tests

Every row above needs normal, boundary and degenerate fixtures. Explicitly cover:

- 8/9 and 20/21 series; 20/21 categories; 5,000/5,001 pairs; all constant-axis grids.
- One/zero values, null/negative/zero/constant measures, grouped single-row versus scalar.
- Temporal-looking categorical labels, pooled month-of-year, weekday order, ranked dates.
- Duplicate labels with different codes, true missing versus literal "Missing category".
- Null versus absent versus zero cells; unknown totals/coverage; near-ties before rounding.
- Exact sums/edges/inclusivity and pair partition reconciliation against independent fixtures.
- All source results unchanged before/after selection/build/description; provider and query
  call counts remain zero. No use of current source data for legacy saved views.

For finite non-integer independent recomputations use error <=
`max(1e-9, 1e-12 * abs(expected))`; identities, integer counts, selection and boundaries
require exact agreement. Do not accept rounded-label equality as numerical evidence.
