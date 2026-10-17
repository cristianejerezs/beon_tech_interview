# Feature Specification: Automatic Visual Reporting

**Feature Branch**: Not created; specifications are independent of branch names.

**Created**: 2026-10-17

**Status**: Draft - awaiting owner review; no implementation authorized by this document.

**Input**: User accepted automatic, data-appropriate graphs alongside evidence tables, compatible chart switching, honest labels and bounds, and visual PDF exports. Keep two linked specifications and validate them together from ordinary wording through analysis, visualization and export.

## Clarifications

### Session 2026-10-17

- Q: Should visual reporting remain English-only or expand into full localization? A: Retain an English-only interface with consistent formatting and faithful source labels; defer translated interfaces, locale-specific sorting and right-to-left layouts.
- Q: What accessibility commitment should PDF exports have alongside a WCAG 2.2 AA web report? A: Require tagged headings/tables, logical reading order, chart descriptions and actual screen-reader review in PDFs; no PDF/UA certification claim.
- Q: Should rendering deadlines be imposed now or measured first? A: Measure browser/PDF baselines first; retain explicit size bounds, loading/failure behavior and privacy-safe metrics without new numerical product deadlines or a background-job requirement.
- Q: Should five analysts remain a formative usability gate or should release require a larger study? A: Retain five representative analysts per formative round with predefined unassisted tasks; repeat after material usability fixes and make no population-level statistical claim.
- Q: Should chart thresholds be fixed release defaults or operator-configurable limits? A: Fix and boundary-test this release's defaults; analysts may select smaller subsets, but raising ceilings requires a reviewed requirement change.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Receive an appropriate visual automatically (Priority: P1)

An analyst obtains a useful graph without asking for a specific chart type or knowing visualization terminology.

**Why this priority**: A correct table should not be the only presentation when a graph makes the comparison or trend easier to understand.

**Independent Test**: Present verified result examples for each supported shape and check the default view, plotted values, labels, and accompanying evidence.

**Acceptance Scenarios**:

1. **Given** distinct destination counts per origin, **When** the report opens, **Then** a categorical bar chart compares the origins and an exact table remains available.
2. **Given** monthly flight counts, **When** the report opens, **Then** a historical line chart orders months chronologically and identifies the unit and period.
3. **Given** monthly counts for multiple origins, **When** the report opens, **Then** the visual separates origins through labelled series or small multiples without combining them silently.
4. **Given** one overall flight count, **When** the report opens, **Then** a labelled summary card and evidence appear, not a meaningless fabricated trend.
5. **Given** a unique destination list or paginated flight listing, **When** it opens, **Then** the table remains the default and the absence of a meaningful numeric chart is explained.

### User Story 2 - Explore compatible views without changing the answer (Priority: P2)

An analyst switches between suitable presentations without rerunning question interpretation or changing the underlying measure.

**Why this priority**: Different tasks benefit from alternative views, but a visual control must not secretly alter the analysis.

**Independent Test**: Switch chart types and series views on an existing report and compare the scope, source, table, and values before and after.

**Acceptance Scenarios**:

1. **Given** a categorical bar chart, **When** the analyst selects a dot plot, **Then** the same categories and exact values appear, without another model request or charge.
2. **Given** a time-and-category result, **When** the analyst switches from lines to small multiples, **Then** periods, series and units remain unchanged.
3. **Given** an incompatible request such as a scatter plot for a single count, **When** chart choices are displayed, **Then** that option is unavailable with an understandable reason.
4. **Given** a chart choice and an owned saved report, **When** the analyst reopens it, **Then** its saved compatible view and disclosures are preserved; older reports without visual preferences still open.

### User Story 3 - Understand distributions, changes and relationships (Priority: P2)

An analyst sees visual forms appropriate to richer questions, without confusing aggregation, missingness or association with causation.

**Why this priority**: New analytical request types need more than generic bars to communicate their meaning.

**Independent Test**: Use independently reconciled distribution, period-change, and paired-variable results; verify the visual displays those exact analytical definitions.

**Acceptance Scenarios**:

1. **Given** validated departure-delay bins, **When** visualized, **Then** a histogram uses those exact interval boundaries and shows missingness separately rather than re-binning values.
2. **Given** two periods and a mean-delay comparison, **When** visualized, **Then** the period values appear in a labelled comparison, with absolute and relative change distinguished from the underlying minutes.
3. **Given** paired departure/arrival delays for at most 5,000 valid flights, **When** visualized, **Then** a scatter plot uses same-flight pairs and discloses paired/excluded counts.
4. **Given** more than 5,000 valid pairs, **When** visualized, **Then** a full-population density view replaces individual points, labels cell counts, and reconciles those counts without representing a sample as the full population.

### User Story 4 - Export and access the same evidence (Priority: P1)

An analyst can understand a report without relying on color, hover interactions, or the browser, and can export the chart they see.

**Why this priority**: Visual reports must remain accessible and trustworthy when saved or shared as documents.

**Independent Test**: Operate controls with a keyboard, inspect accessible labels, and compare a PDF with the current report and its exported evidence.

**Acceptance Scenarios**:

1. **Given** a current selected chart, **When** the analyst downloads the PDF, **Then** the actual chart, legends, units, dates, scope, limitations and supporting table appear without clipping.
2. **Given** a chart that uses color for series, **When** viewed without distinguishing those colors, **Then** text labels, symbols or patterns still identify the series and the table supplies exact values.
3. **Given** a chart export failure, **When** export is attempted, **Then** an explicit failure is shown; a table-only document is not silently presented as a successful visual export.
4. **Given** a reopened older report, **When** a visual is possible from its stored evidence, **Then** any generated view uses that report's original snapshot and definitions rather than current source data.

### Edge Cases

- Empty results, one category, all-null measures, all-zero measures, and values below zero.
- Tied ranks, long category labels, large category sets, omitted groups, and truncated analytical results.
- Missing dates versus true zero activity; partial first/last periods and different sample sizes.
- Duplicate category labels with different codes; unmatched or missing names.
- Two grouping dimensions that are not time; many time series; incompatible or mixed numeric units.
- Overlapping scatter points, very large populations, constant-valued axes and extreme outliers.
- PDF page breaks, portrait/landscape layouts, long legends, grayscale use and unavailable rendering resources.
- Charts and listing exports with different completeness bounds must identify those separate populations clearly.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Classify each validated result using its declared analytical form and dimension roles, required evidence, and the ordered decision table below. Do not infer temporal meaning from category-label text or require the analyst/interpreting model to supply a chart instruction. Contradictory or incomplete shape metadata must produce an explicit missing/invalid-evidence explanation with available tables, not a guessed chart.
- **FR-002**: Use the numeric-eligibility rules below rather than an unspecified minimum sample size. A valid numeric value is finite, non-null, and consistent with its analytical definition; zero and negative values are valid where the measure permits them. Never fabricate a summary from a grouped result simply because one group remains. Explain empty/all-null/ineligible results while retaining scope, counts and available evidence.
- **FR-003**: Retain an exact supporting table and concise, data-grounded interpretation beside every graph. Tables and charts must refer to the same report scope, definitions, source snapshot and material exclusions; a displayed chart subset must be disclosed.
- **FR-004**: Every chart must identify the measure, units, period, relevant grouping/series and active scope; include observation counts and missingness in the adjacent evidence or caption. Distinguish full-snapshot provenance from the filtered population.
- **FR-005**: Category charts default to horizontal bars for rankings and vertical bars otherwise. Offer compatible horizontal/vertical bars and dot plots; sort rankings by their measure with stable secondary labels, retain tie disclosures, and do not imply an exclusive winner when tied.
- **FR-006**: Time-series charts order periods chronologically, distinguish missing from observed zero, label the chosen daily/weekly/monthly grain, and visibly mark partial periods. Missing values create visible gaps, not invented connecting observations or silently substituted zeroes.
- **FR-007**: For time plus category, default to labelled lines with at most eight series and small multiples for nine through twenty. Use consistent scales across comparable panels. With more than twenty series, retain the table and require an explicit subset of at most twenty before plotting; do not select arbitrary series. Combining categories is a separate analytical refinement requiring a newly validated definition and recalculated evidence, not a chart switch.
- **FR-008**: For two categorical dimensions and one numeric measure, default to grouped bars when there are at most eight series and twenty primary categories; otherwise use a labelled heatmap of the returned groups with absent/null cells distinguished from zero. Explain any upstream result truncation.
- **FR-009**: A chart with one categorical dimension displays at most twenty categories. For larger results, rankings initially show the first twenty in the validated rank order (or fewer if the analytical result bound is smaller), explicitly marking omitted categories and any cutoff tie; unranked results require an explicit selection before plotting. Provide labelled category/series multi-selection by stable code plus name, current-selection counts, apply/reset controls and a table-view option. Reject over-limit selections without losing the prior valid view. Persist applied subsets with the owned report. This release never synthesizes "Other"; even additive regrouping is a separate analytical refinement.
- **FR-010**: Distribution charts must use the analysis's exact bins, units, inclusion boundaries and counts; adjacent bars indicate numeric intervals, and missingness is separately labelled. Rendering must not choose different bins from those in the evidence.
- **FR-011**: Period-change reports must show both period values, baseline/comparison labels, and distinctly labelled absolute and relative changes. Do not plot percentages on the same unlabelled scale as counts or minutes; preserve unavailable percentage-change explanations.
- **FR-012**: Relationship charts must use paired variables with their respective units and source-row grain. Up to 5,000 valid pairs, show a scatter plot of all pairs; above that, default to a density view of all pairs with twenty equal-width intervals per varying axis and one interval per constant axis. Publish exact cell boundaries/counts and reconcile their sum with the paired population; there are at most 400 cells, not necessarily 400 nonempty cells. Intervals include the lower endpoint and exclude the upper except the last, which includes the observed maximum. A constant-axis interval includes its sole value explicitly. Do not sample silently, fit regression, or imply causation.
- **FR-013**: Axis choices must not distort conclusions: bars start at zero and retain negative values, quantitative axes are linear by default, and units remain explicit. No 3D effects, broken axes, or dual-axis charts are included in this feature. Small multiples for the same measure share a comparable scale.
- **FR-014**: Provide a compatible-view selector including table view according to the compatibility matrix below; switching views must not invoke a model, consume model budget, change analytical scope, or recompute a different metric. Preserve stable identities, semantic order, units, periods, missingness and selected population. Show incompatible choices disabled with a visible, programmatically associated reason; do not expose dead unexplained controls. Changing measures, units, bins, time grain, grouping or full-population aggregation is an analytical refinement, not a presentation switch.
- **FR-015**: Persist the selected compatible view and its population/subset disclosures with an owned saved report under existing retention rules. Older reports without those preferences must open safely with a deterministically selected compatible view, or an explicit missing-evidence explanation.
- **FR-016**: PDF exports must contain the current selected chart as an actual graphic plus all exact plotted evidence, scope, definitions, legends, limitations and population/subset disclosures. Plotted evidence means the visible category/time values, histogram bins, scatter pairs or density cells, not an unbounded underlying source table. Additional report/supporting-route tables retain their declared analytical bounds and completeness notices. Explicit table view exports its selected evidence table without requiring a chart, but does not omit material scope/definitions. Use the PDF presentation and failure rules below; never silently downgrade a promised visual export.
- **FR-017**: CSV exports remain data, not chart images. Exported chart evidence must identify columns, units, scope, snapshot and completeness, including any category subset or density/bin transformation; expose exact aggregated cells/bins for distribution and density views. Individual-record exports retain the linked exploration specification's bounds.
- **FR-018**: Web reports and controls must meet WCAG 2.2 AA, with programmatic chart names, adjacent textual explanations, keyboard-operable controls, visible unobscured focus and no essential meaning dependent only on color or hover. PDF exports must include tagged headings and tables, logical reading order, selectable text and chart descriptions, verified with an actual screen-reader review. Exact values and missingness remain accessible in both formats. Do not claim PDF/UA certification.
- **FR-019**: Chart, saved-report and download ownership checks must remain unchanged. Plotting/exporting must not send source rows, chart data or report content to an external inference/rendering service or introduce unapproved retention or model charges.
- **FR-020**: Automated checks must compare every plotted value/cell/bin with independently verified report evidence, including scope, chronological/category order, negative/null/zero behavior, ties and displayed bounds. Separately inspect actual browser and PDF rendering for labels, legends, readability, clipping and accessibility; numerical checks alone do not prove usability.
- **FR-021**: Pass E2E-01 through E2E-09 defined in [002-natural-language-exploration](../002-natural-language-exploration/spec.md#shared-end-to-end-acceptance-cases), covering ordinary wording, analytical results, automatic view, saved report and export, including up to four sections in a composite report. Record actual integrated outcomes only after execution.
- **FR-022**: Use English interface/chart/accessibility labels, comma thousands separators, a decimal point, unambiguous `YYYY-MM-DD` dates and `YYYY-MM` month labels. Retain full-precision evidence; display counts as integers, computed measures to two decimal places and percentages to two decimal places, consistently across browser and PDF. CSV evidence preserves unrounded numeric values. Preserve source names and codes without transliteration or silent character replacement; disambiguate duplicate names with codes. Category sorting uses declared numerical/time/ranking order or, otherwise, stable code order rather than locale-dependent collation.
- **FR-023**: Record browser chart-ready and complete-PDF export durations separately from model/query time, with environment, cold/warm conditions, evidence size, chart family and safe failure category. Show loading and explicit recoverable failure states; preserve the report after a failed render/export and allow an explicit retry without another model request. A technical timeout or missing rendering resource must not produce success-shaped or partial output. Log no report contents, values, labels, filters, source rows, questions or credentials. Measure representative timings before proposing numerical product deadlines; this feature does not require queued exports.
- **FR-024**: Follow the required logical Visual Evidence contract below across browser, saved report, accessible explanations and exports. Missing required evidence must be identified explicitly; never reconstruct unavailable historical evidence from current source data or substitute guessed missingness.
- **FR-025**: Use the missingness/coverage rules below consistently across chart families and formats. Chart preparation must not convert absent/null evidence into zeros or describe min/max observed event dates as proof of complete calendar coverage.
- **FR-026**: Enforce the inclusive boundary table as fixed release defaults rather than operator-configurable ceilings. Store the rule/evidence version with saved preferences; if a historical preference is incompatible, explain the change and offer a compatible view without changing evidence.
- **FR-027**: Apply the dependency/release table below. Existing charts may be tested independently, but no integrated feature-release claim is valid until both 002 and 003 pass all nine shared cases and the numerical, visual, export, accessibility and formative-usability gates. Maintain dated executed-outcome records with environment, method, actual result, failures and evidence references; planned/not-run cases are never passes.
- **FR-028**: A composite report under 002 contains up to four independently labelled analysis sections on a common validated snapshot. Apply visual classification, evidence/subset limits, compatible preferences, accessibility and scope explanations per section, never by combining unrelated measures on one chart. An analytically incomplete report may be saved/exported only with 002's explicit acknowledgement and visible section failure notices. Its PDF must completely render the successful evidence and required disclosures; a technical rendering failure still permits no partial file. Section preferences follow the one parent report's ownership and retention; combined listing exports follow 002's aggregate row bound.

### Default Presentation Rules

| Analytical result | Default | Compatible alternatives |
|-------------------|---------|-------------------------|
| One overall number | Labelled summary card and evidence | Table |
| One category dimension and one measure | Bar chart | Horizontal/vertical bars, dot plot, table |
| Ranked categories | Horizontal bars | Dot plot, vertical bars, table |
| Time and one measure | Historical line with observed points | Time-ordered bars, table |
| Time, category and one measure | Lines or small multiples according to series count | Compatible series view, table |
| Two categorical dimensions and one measure | Grouped bars or heatmap according to cardinality | Compatible grouped bars/heatmap, table |
| Two-period change | Side-by-side period comparison and labelled change summary | Dot comparison, table |
| Numeric distribution | Histogram of validated bins | Table of the same bins |
| Paired numeric measures | Scatter or full-population density according to pair count | Table of pairs or density cells within export bounds |
| Unique entity or individual-record list | Table with appropriate pagination | No automatic numeric chart |

**Result-shape taxonomy and deterministic precedence**

Validate the common evidence contract first, then evaluate the following rows in order and select the first matching shape. The declared analytical form is one of listing, distribution, relationship, period-change or aggregate; ranking is an explicit aggregate ordering intent, not inferred merely because values happen to be sorted. Conflicting forms/roles or an unsupported dimension count are invalid evidence, not a tie to resolve by guessing.

| Precedence | Shape and required fields | Classification rule |
|------------|---------------------------|---------------------|
| 1 | Entity/record listing: entity/source identity, columns, population and page/completeness | Declared listing, even if rows contain numeric identifiers or incidental measures |
| 2 | Distribution: numeric variable/unit, exact bins/counts and missing/excluded totals | Declared distribution; never infer bins from arbitrary category labels |
| 3 | Relationship: two numeric variables/units, same-row pairing grain, paired/excluded totals, pairs or complete density cells | Declared relationship; two unrelated numeric columns do not qualify |
| 4 | Period change: baseline/comparison periods, values, counts, absolute/relative change definitions | Declared period-change; two dates in a generic result are insufficient |
| 5 | Scalar: one defined measure, no grouping dimensions, at most one result row | Ungrouped aggregate; zero rows is empty, not an invented scalar zero |
| 6 | Time series: exactly one declared temporal dimension and optionally one category series, one measure | Temporal role and calendar grain control classification; order chronologically even if a metric sort was requested. A time-bucket ranking must be an explicit ranked-category analysis, with temporal labels retained, not both intents simultaneously |
| 7 | Ranked categories: one categorical/ordered-category dimension and explicit ranking intent | One measure, validated rank direction and tie policy |
| 8 | Categorical comparison: one or two categorical/ordered-category dimensions, one measure | Two ordered categories remain categorical unless explicitly defined as temporal. Preserve declared ordinal order rather than inferring a time series |

Labels such as "2013-01", "Monday" or "1" do not override the declared role. A grouped result filtered to a single category stays grouped; an ungrouped one-row result is scalar. Mixed-unit measures or unsupported shapes require an explicit explanation and evidence table rather than a guessed shared axis.

**Numeric eligibility and no-data behavior**

Observation counts communicate evidence volume, not statistical significance. No arbitrary two-observation minimum is imposed on descriptive counts or comparisons. Invalid infinities/non-numeric values are invalid evidence and cause an explicit validation error.

| Shape | Minimum plottable evidence and degenerate behavior |
|-------|---------------------------------------------------|
| Scalar | One finite value: summary card, including zero/negative when valid. Null/empty: unavailable card/message and counts, not zero |
| Category/ranking | One finite category value: one bar/dot with its category label, not a scalar card. Null-valued groups remain in the table with unavailable markers |
| Time series | Two finite time buckets permit connecting lines only across consecutive known buckets. One finite point is a labelled isolated marker with "one observed period; no trend established"; no fabricated segment |
| Time plus series | Apply time-point eligibility per series; retain all selected series in legends/captions including unavailable series, without drawing fictional marks |
| Two categorical dimensions | One finite cell permits one mark/cell; absent/null combinations are explicitly unavailable, not zero |
| Period change | Both finite period values permit comparison and defined change fields; one unavailable period produces labelled available/unavailable evidence without a complete-change claim |
| Distribution | At least one valid underlying observation and validated bins; empty bins within the verified population have observed count zero. No valid observations: no histogram and explicit missing/excluded totals |
| Relationship | One finite pair permits one point with "one paired observation; no relationship established". Constant axes remain valid; density is selected by population size, not apparent variance |
| Listing | Always table/pagination, even if numeric columns exist; empty list explains scope and exact zero matched records when verified |

All-zero finite measures are plotted at zero with an explicit all-zero note; zero-height bars retain labelled categories and values. Constant nonzero values and negative-only valid measures remain plottable with appropriate axes and no variation/trend claim. All-null groups retain available labels, counts and a no-plottable-data message.

**Inclusive boundaries and rendering limits**

| Boundary | Exact rule |
|----------|------------|
| 8 / 9 selected time series | 8: labelled lines by default; 9: small multiples by default |
| 20 / 21 available time series | 20: small multiples; 21: selection required, no automatic subset. An explicitly applied selection of at most 20 then follows the 8/9 rule |
| 20 / 21 categories in one dimension | 20: all plotted; 21: ranking shows first 20 with omission/cutoff disclosure, unranked comparison requires selection |
| 8 series and 20 primary categories in two categorical dimensions | Both ceilings inclusive: grouped bars; 9 series or 21 primary categories: labelled heatmap of the returned groups |
| 5,000 / 5,001 valid pairs | 5,000: full scatter; 5,001: full-population density, never first-5,000 truncation |
| Density grid | Both varying axes: 20 by 20, at most 400 cells; one constant axis: 1 by 20; both constant: 1 by 1; zero-count cells remain distinguishable from unavailable evidence |
| Maximum finite aggregate/time/category cells | 500 returned analytical groups in total, not 500 per series; analytical truncation must be disclosed before visual subsetting |
| Distribution | At most 100 validated bins, including zero-count bins, plus separate missing/excluded counts |
| Scatter and listings | At most 5,000 plotted pairs; listing pages/export retain 002's separate 500-row maximum page and 10,000-row export ceiling |
| One/zero valid point, group or pair | Use the numeric-eligibility table; no automatic minimum-volume suppression or fabricated values |

These limits do not authorize hiding rows beyond 002's analytical bounds. Density requires evidence covering all valid pairs, not a density computed from a truncated listing. If complete required evidence is unavailable, explain that limitation and offer a supported refinement; do not label a partial density as full population.

For unsupported/over-limit shapes, present the available evidence table and an explicit selection/refinement action. For a browser rendering fault, retain evidence and state that the chart failed; table availability is not chart success. If the table also cannot render, retain the saved report, present an accessible error and explicit retry; offer exports only if independently generated and validated. A PDF failure produces no downloadable partial artifact.

**Compatibility matrix**

All permitted switches keep report/snapshot, definitions, population, selected subset, measure units, periods, category/series identities, missingness, bounds and semantic order unchanged. Orientation/layout may change; it may not silently change ranking direction, chronological or ordinal order.

| Existing evidence | Permitted views within the fixed limits | Forbidden presentation-only switches |
|-------------------|----------------------------------------|--------------------------------------|
| Scalar | Summary card, table | Bar/scatter/trend manufactured from one ungrouped value |
| One categorical dimension/ranking | Horizontal bars, vertical bars, dots, table | Time series inferred from labels, new rankings, pie/Other aggregation |
| One temporal dimension | Lines/isolated markers, time-ordered bars, table | New calendar grain or filled/interpolated observations |
| Time plus series | Lines for at most 8 series, small multiples for at most 20, table; small multiples also permitted for 1-8 | Combining series, changing periods, exceeding series limits |
| Two categorical dimensions | Grouped bars only within 8-series/20-category limits, heatmap up to the returned-group bound, table | Re-aggregation, dropped dimension, mixed-unit overlay |
| Period change | Side-by-side bars, paired dot comparison, table and unchanged change summary | New baseline/period, new relative-change formula |
| Distribution | Histogram, exact bin table | Re-binning, a fabricated smooth density curve |
| Relationship | Scatter for at most 5,000 pairs or density above 5,000, plus the corresponding evidence table | Density/scatter switching that requires unavailable evidence, sampling, regression or a different variable pair |
| Entity/record list | Paginated table | Automatic charting of identifiers or incidental numeric fields |

Moving from scatter to density is not exposed as a presentation switch in this release. Default density preparation is permitted as a deterministic, evidence-preserving count transformation over all paired observations; it does not authorize new model calls or arbitrary aggregation.

**Missingness, periods and subset semantics**

- Track the filtered source-row population and the measure's non-missing observation count separately. For categories, null dimension values use a distinct "Missing category" identity/label, and unmatched references use "Unmatched reference"; neither merges with a literal source string of that name.
- Distinguish an absent group (no established result cell) from a present group with a null measure and a present group with an observed zero. Do not assert why a group is absent without coverage evidence. Unavailable cells use a labelled missing pattern/marker in heatmaps/tables, not a quantitative zero color.
- For time series, a missing bucket is an explicit gap per series; the selected series remains in the legend and evidence table even when entirely unavailable. Distribution missing counts refer to nonnumeric/null source measurements and are separate from valid zero-count bins. Pair exclusions are the union of rows lacking either variable; also report x-missing, y-missing and both-missing counts so overlapping exclusions are not double-counted.
- Derive expected time buckets from the requested range intersected with verified source coverage. Mark a bucket partial when the requested/verified interval does not cover its full calendar interval, or documented source coverage has a gap. If coverage completeness is unknown, say "coverage completeness unknown", not complete/partial based only on observed events. Calendar-boundary partiality and measure missingness remain separate disclosures.
- Date-only buckets use recorded departure calendar dates, Monday-start weeks and calendar months from 002. Their time-zone field is "not applicable - recorded departure date", not UTC or the viewer's time zone. Intraday/time-zone conversion remains out of scope.
- Category selection changes the displayed subset of existing evidence, not the full analytical population or stored totals. Show selected, returned and total available group/series counts; if upstream totals are unavailable, mark them unknown rather than infer them from a truncated table.
- Browser, saved preferences, PDF and CSV must identify the same applied subset and separately identify underlying analytical truncation. A table may show more groups than the chart only with explicit chart-subset labels. No "Other" bucket is synthesized, including for additive measures.
- Analytical definitions declare additivity: a count can be summed only over disjoint exhaustive groups; distinct counts and means are non-additive. Missing/unknown additivity prohibits combining groups. Any requested regrouping returns to analysis and independently recalculates the result.
- Preferences have no separate retention lifetime: they follow their owning report's access, ten-report pruning and deletion rules and any later approved retention/backup policy. This feature neither invents a retention duration nor waives the existing production approval gate.

**PDF presentation and failure behavior**

- All rendering executes locally within the deployment; no hosted rendering service or report-data transmission is allowed. Specific libraries, process isolation and font packaging are planning decisions, subject to the tagged-PDF and privacy requirements.
- Default to A4 portrait. If content cannot meet the legibility rules, use A4 landscape; if still insufficient, split labelled panels/legends/tables across pages, repeat headers and preserve shared scales. Do not shrink chart labels or evidence-table text below 10 points.
- Include full category names/codes in evidence and a readable chart mapping. Wrap or place long labels/legends in linked numbered keys; do not silently truncate labels or overlap legends. Grayscale meaning must remain distinguishable through labels, patterns, symbols or directly annotated values.
- Use embedded fonts covering the actual document text. Preserve selectable text, tags, reading order and table headers through font fallback; never silently replace unsupported characters. Missing glyphs, fonts or rendering resources produce an actionable export error instead of a corrupt/partial PDF.
- Make the complete validated PDF available only after all required charts, evidence, tags and pages have been generated. No partial PDF download is allowed. Explain failure and preserve the browser report; an explicit retry must not reinterpret the question or incur model charges. Automatic retry is not required.

**Accessible chart explanations and interaction**

- Name pattern: "[chart family]: [measure and unit] by [dimension/series or numeric pair], [period]". The associated description states scope, shown/available population, missing/excluded observations, partial periods and material limits. Do not insert claims of significance, causation or an unobserved trend.
- Category/ranking explanations identify verified maxima/minima and ties within the displayed subset, not an unsupported global winner. Time explanations describe observed endpoints/gaps only; distribution explanations identify bins/counts; relationship explanations state the variables, paired population and scatter/density encoding without inventing correlation.
- Derive text from the same Visual Evidence used for plotting; presentation-only descriptions must not request another model call. Counts and described extrema must reconcile with evidence and its selected subset.
- Reading/focus order is report title and interpretation, chart/view and subset controls, chart explanation, evidence access, then export actions. Preserve focus after applying a view; keyboard users can leave the chart without a trap. Each independently interactive chart element/control has an accessible name; a decorative mark is not a required focus stop.
- Every categorical series must have an explicit code/name mapping and at least one distinguishing non-color cue: line dash/marker plus legend for lines, labelled panel for small multiples, hatch/shape/direct labels for bars/dots. Quantitative color scales in heatmaps/density require a labelled numeric legend, cell-value evidence and distinct missing-cell patterns.
- Screen readers encounter the chart name/description and can navigate the exact table with headings, row/column relationships and labelled missing values, without having to visit every graphical mark. Any interactive legend must expose its selected state and keyboard operation; changes announce the updated view/subset without reading the whole table again.

**Dependency status and release decisions**

| Dependency or gate | Status at this specification review | Independent validation / release implication |
|--------------------|-------------------------------------|-----------------------------------------------|
| 001: source validation, ownership, persisted reports, aggregate results | Core implementation exists; original external release gates remain pending | Existing verified aggregate fixtures can test scalar/category/monthly visuals; this is not certification of the parent release |
| 002: scope/clarification, entity/record browsing, two-dimensional results | Draft; not implemented by this specification | Browser/listing/clarification integration awaits actual supported evidence |
| 002: daily/weekly buckets, period changes, bins and paired populations | Draft; no execution evidence for the extension | Isolated chart/evidence fixtures can test presentation; real end-to-end claims remain blocked |
| 003: visuals, compatibility, tagged PDF, accessibility | Requirements only; not implemented/tested by this review | Existing charts do not establish compliance with the strengthened requirements |
| Shared E2E-01 through E2E-09 | Not run for these extensions | Both features must pass the same authoritative cases in 002 before integrated release, including four-section composite and partial-outcome handling |
| Numerical/visual/PDF/accessibility/performance study records | Not run for these extensions | Record actual separate outcomes, environment, versions, dates and failures during implementation; baseline timings are measurements, not a latency threshold |
| Five-participant comprehension gate | Not run | Requires actual unassisted per-task results and repeat rounds after material usability fixes |

The clarification answers above are the product decision log. Implementation choices such as the renderer and concrete serialized evidence schema are deferred to the plan/contracts, not unresolved product permissions. Executed outcomes belong in dated acceptance records when tests actually run; no review checklist or configuration flag substitutes for them.

### Key Entities *(include if feature involves data)*

- **Visual View**: Chart family, compatible alternatives, axes/series, ordering, units, period and linked analytical evidence.
- **Presentation Preference**: An owned report's selected compatible view and category/series subset; not a new calculation.
- **Visual Evidence**: The logical report-owned contract described below, containing exact plotted aggregates, bins, pairs or density cells and all interpretation/completeness information needed to reproduce the view.
- **Accessible Explanation**: Programmatic chart name, plain-language interpretation, non-color series cues and exact table.
- **Export Representation**: Selected visual and associated scope/evidence preserved in a document or tabular export.

**Required logical Visual Evidence contract**

This specifies information and invariants, not a technology-specific serialized schema; field types, storage representation and migration mechanics are defined in planning/contracts.

| Required information | Invariant |
|----------------------|-----------|
| Report identity, snapshot identity, evidence/selection-rule version | Every chart, table, explanation, preference and export refers to the same owned evidence version |
| Declared analytical form, output grain and dimension roles | Scalar, categories, ordered categories and temporal dimensions are explicit; stable codes/identifiers remain distinct from display names |
| Analytical definition and measure metadata | Include unit, source population, weighting, additivity, numerator/denominator where applicable, exclusions and approved change/bin/pair definitions |
| Active scope and period | Filters, requested dates, verified coverage bounds/completeness, observed bounds, bucket grain and calendar/time-zone applicability remain separately identified |
| Dimension/series identities and order | Codes and names, temporal/ordinal/rank direction, stable secondary order and tied-cutoff policy are reproducible; duplicate names cannot collapse distinct codes |
| Finite numeric evidence | Unrounded aggregates with counts; exact distribution bins; source-row-paired values or full-population density cells, according to the declared shape |
| Boundaries and transformations | Exact lower/upper limits, endpoint inclusion, constant-axis convention and density/bin counts; identify the complete input population for each transformation |
| Coverage/missingness | Filtered rows, valid observations, dimension missing/unmatched groups, absent versus null versus zero cells, partial/unknown coverage and pairwise exclusion breakdowns |
| Selection and completeness | Selected identities, shown/returned/total available counts, analytical bounds, visual bounds, upstream truncation and cutoff ties; unknown totals remain explicitly unknown |
| Formatting and accessible explanation inputs | Counts/units and unrounded values support FR-022's identical browser/PDF display; rounding never drives sorting, ties, bin membership or numerical reconciliation |

When shape-specific fields do not apply, mark them not applicable; when necessary historical evidence is unavailable, state unavailable with a reason. Do not substitute zero/default completeness. Exact values remain available in evidence even when display rounding makes two values look equal; analytical ties use the validated tie definition, not rounded labels.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All ten presentation-rule rows have at least three independently checked examples, including a boundary/degenerate case; every eligible example receives the required default or explicitly specified no-data/boundary explanation rather than an unexplained table fallback.
- **SC-002**: Every plotted numeric value and exported cell faithfully preserves the stored analytical evidence without new rounding-driven calculations. Counts, identities, bin membership and order are exact. For independently recomputed finite non-integer values, absolute error must be at most max(1e-9, 1e-12 times the absolute expected value), matching 002; record errors and never compare rounded display strings. Null/unavailable outcomes, units, scope, interval boundaries and completeness must agree in every acceptance example.
- **SC-003**: All nine shared end-to-end scenarios preserve the same interpretation, scope and numeric meaning across chart, table, saved-report reopening and PDF/CSV evidence, including per-section views and acknowledged incomplete composite reports.
- **SC-004**: At least twelve PDF examples spanning all chart families, negative/null values, long labels and category/series limits show the selected chart and mandatory scope with no clipped axes, unreadable legends or missing series. Document actual visual inspection results.
- **SC-005**: Every compatible view switch in acceptance testing makes zero additional model requests, leaves analytical values and scope unchanged, and survives saved-report reopening.
- **SC-006**: A documented WCAG 2.2 AA assessment of web reports and controls must include actual keyboard/screen-reader checks: every control is named, reachable and operable, and every chart has an accessible name, explanation and exact evidence alternative. PDF review must verify tags, reading order, chart descriptions and table navigation with a screen reader. Record the tested browser, reader and document-viewer versions and outstanding failures; no essential comparison may require color or hover alone and no PDF/UA certification is claimed.
- **SC-007**: Recruit five real participants who use tabular reports or operational/business analysis, not feature implementers. Preassign every participant a category/ranking task, a time-trend task and a distribution/relationship task using fixed reports, questions and independently established answer keys. Each task asks for one evidence-backed observation and one material scope/missingness/subset limitation. For each task separately, at least four of five participants must answer both components correctly without moderator instruction, hints, corrections or task-specific coaching; built-in report explanations and accessibility tools are allowed. Score the first unaided attempt, record assistance separately, and report de-identified per-task results independently of automated correctness. This is a formative usability release gate, not an estimate of population-wide accuracy. After material usability changes or a failed round, repeat the scored round with five new representative participants; retain earlier failures and outcomes.
- **SC-008**: Record separate browser/PDF timings and failures for all twelve PDF acceptance examples and the chart-boundary cases, including environment and cold/warm conditions. Fault tests for resource unavailability and an imposed technical timeout must show an explicit recoverable error, preserved report data, no partial download, no report-content telemetry and zero extra model requests. There is no numerical product latency pass/fail target in this draft.
- **SC-009**: All rows of the shape, numeric-eligibility, boundary and compatibility tables must have acceptance cases, including ambiguous time-like labels, conflicting shape metadata, one category/point/pair, all-null/zero/negative/constant measures, 8/9 and 20/21 series/categories, 5,000/5,001 pairs and all constant-axis grid cases. Every forbidden switch is explained and no test silently changes analysis or mislabels a partial/failed visual as complete.
- **SC-010**: Browser/PDF/CSV/saved-report checks for missing/unmatched categories, absent/null/zero cells, unknown coverage, partial periods, rounded near-ties and duplicate names must preserve the logical evidence contract with zero undisclosed population, ordering or precision changes.

## Assumptions

- This extends [001-airport-analytics-platform](../001-airport-analytics-platform/spec.md) and consumes the request shapes and verified evidence defined by [002-natural-language-exploration](../002-natural-language-exploration/spec.md).
- Existing compatible grouped results can demonstrate this feature independently. New distributions, changes, paired values, two-dimensional outputs and composite reports depend on the exploration feature; integrated release requires both to pass the nine shared cases.
- Series/category limits, the 5,000-point threshold and density-grid bounds are fixed release product defaults by owner clarification, not measured performance limits. Changing them requires reviewed requirements and boundary tests; analyst subsets may be smaller but not exceed ceilings.
- Full-population density is a presentation aggregation, not a random sample; counts must reconcile with valid pairs. Density cells have at most 400 groups and do not waive analytical/export bounds.
- Maps, pie/donut charts, forecasts, statistical inference, regression fitting and arbitrary custom chart authoring are outside this feature.
- PDF is the visual export format; CSV remains tabular. Interactive hover details must not be the only place material meaning appears.
- The interface is English-only. Translated labels, locale-dependent formatting/sorting and right-to-left layouts are deferred by owner decision; faithful rendering of source names remains required.
- No chart implementation, live interpretation acceptance, PDF visual review or analyst study has been performed for this draft. Existing release gates remain in force.
