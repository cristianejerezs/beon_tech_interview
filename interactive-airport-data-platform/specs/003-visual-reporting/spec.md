# Feature Specification: Automatic Visual Reporting

**Feature Branch**: Not created; specifications are independent of branch names.

**Created**: 2026-10-17

**Status**: Draft - awaiting owner review; no implementation authorized by this document.

**Input**: User accepted automatic, data-appropriate graphs alongside evidence tables, compatible chart switching, honest labels and bounds, and visual PDF exports. Keep two linked specifications and validate them together from ordinary wording through analysis, visualization and export.

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

- **FR-001**: Select a default presentation from the validated result's analytical meaning, grain, dimensions and units according to the selection rules below. Do not require the analyst or interpreting model to supply a chart instruction to obtain a suitable graph.
- **FR-002**: Every supported result shape with sufficient numeric evidence must receive its specified visual. Use a summary card for a scalar and tables for entity/record listings. Empty or all-null numeric results receive an explicit no-plottable-data message and available evidence, not a fabricated graph.
- **FR-003**: Retain an exact supporting table and concise, data-grounded interpretation beside every graph. Tables and charts must refer to the same report scope, definitions, source snapshot and material exclusions; a displayed chart subset must be disclosed.
- **FR-004**: Every chart must identify the measure, units, period, relevant grouping/series and active scope; include observation counts and missingness in the adjacent evidence or caption. Distinguish full-snapshot provenance from the filtered population.
- **FR-005**: Category charts default to horizontal bars for rankings and vertical bars otherwise. Offer compatible horizontal/vertical bars and dot plots; sort rankings by their measure with stable secondary labels, retain tie disclosures, and do not imply an exclusive winner when tied.
- **FR-006**: Time-series charts order periods chronologically, distinguish missing from observed zero, label the chosen daily/weekly/monthly grain, and visibly mark partial periods. Missing values create visible gaps, not invented connecting observations or silently substituted zeroes.
- **FR-007**: For time plus category, default to labelled lines with at most eight series and small multiples for nine through twenty. Use consistent scales across comparable panels. With more than twenty series, require an explicit subset or aggregation choice while retaining the table and explaining the boundary; do not select arbitrary series.
- **FR-008**: For two categorical dimensions and one numeric measure, default to grouped bars when there are at most eight series and twenty primary categories; otherwise use a labelled heatmap of the returned groups with absent/null cells distinguished from zero. Explain any upstream result truncation.
- **FR-009**: A single-category chart displays at most twenty categories by default, with an explicit shown/available count and subset-selection rule when more exist. Let the analyst choose categories or switch to table view. Do not combine omitted categories into "Other" for non-additive measures, or silently discard them from report/export evidence.
- **FR-010**: Distribution charts must use the analysis's exact bins, units, inclusion boundaries and counts; adjacent bars indicate numeric intervals, and missingness is separately labelled. Rendering must not choose different bins from those in the evidence.
- **FR-011**: Period-change reports must show both period values, baseline/comparison labels, and distinctly labelled absolute and relative changes. Do not plot percentages on the same unlabelled scale as counts or minutes; preserve unavailable percentage-change explanations.
- **FR-012**: Relationship charts must use paired variables with their respective units and source-row grain. Up to 5,000 valid pairs, show a scatter plot of all pairs; above that, default to a density view of all pairs in a maximum 20-by-20 equal-width grid. Publish exact cell boundaries and counts; a constant axis uses one interval. Do not sample silently, fit regression, or imply causation.
- **FR-013**: Axis choices must not distort conclusions: bars start at zero and retain negative values, quantitative axes are linear by default, and units remain explicit. No 3D effects, broken axes, or dual-axis charts are included in this feature. Small multiples for the same measure share a comparable scale.
- **FR-014**: Provide a compatible-view selector including table view; switching views must not invoke a model, consume model budget, change analytical scope, or recompute a different metric. Requests needing a new measure, bin width or time grain are new analytical refinements, not presentation-only switches.
- **FR-015**: Persist the selected compatible view and its population/subset disclosures with an owned saved report under existing retention rules. Older reports without those preferences must open safely with a deterministically selected compatible view, or an explicit missing-evidence explanation.
- **FR-016**: PDF exports must contain the current selected chart as an actual graphic plus the same material scope, definitions, legends, limitations and supporting evidence. If table view is explicitly selected, PDF may contain only the labelled table. A visual export failure must be explicit and must not silently downgrade the promised output.
- **FR-017**: CSV exports remain data, not chart images. Exported chart evidence must identify columns, units, scope, snapshot and completeness, including any category subset or density/bin transformation; expose exact aggregated cells/bins for distribution and density views. Individual-record exports retain the linked exploration specification's bounds.
- **FR-018**: Charts must have programmatic names and adjacent textual explanations, all view controls must be keyboard-operable with visible focus, and essential meaning must not rely only on color or hover. Exact values and missingness remain accessible in the supporting table and PDF.
- **FR-019**: Chart, saved-report and download ownership checks must remain unchanged. Plotting/exporting must not send source rows, chart data or report content to an external inference/rendering service or introduce unapproved retention or model charges.
- **FR-020**: Automated checks must compare every plotted value/cell/bin with independently verified report evidence, including scope, chronological/category order, negative/null/zero behavior, ties and displayed bounds. Separately inspect actual browser and PDF rendering for labels, legends, readability, clipping and accessibility; numerical checks alone do not prove usability.
- **FR-021**: Pass E2E-01 through E2E-08 defined in [002-natural-language-exploration](../002-natural-language-exploration/spec.md#shared-end-to-end-acceptance-cases), covering ordinary wording, analytical results, automatic view, saved report and export. Record actual integrated outcomes only after execution.

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

The most specific analytical form takes precedence: period changes, distributions and relationships use their own rule before generic category rules; rankings use the ranking rule. Summary and listing rules apply only to scalar/list results.

### Key Entities *(include if feature involves data)*

- **Visual View**: Chart family, compatible alternatives, axes/series, ordering, units, period and linked analytical evidence.
- **Presentation Preference**: An owned report's selected compatible view and category/series subset; not a new calculation.
- **Visual Evidence**: Exact plotted aggregates, bins, pairs or density cells with boundaries, counts, missingness and completeness.
- **Accessible Explanation**: Programmatic chart name, plain-language interpretation, non-color series cues and exact table.
- **Export Representation**: Selected visual and associated scope/evidence preserved in a document or tabular export.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All ten presentation-rule rows have at least three independently checked examples, including a boundary/degenerate case; every eligible example receives the required default or explicitly specified no-data/boundary explanation rather than an unexplained table fallback.
- **SC-002**: Every plotted numeric value and exported cell agrees with verified analytical evidence, with exact counts and absolute tolerance 1e-12 for unrounded computed values. Chart ordering, units, scope, interval boundaries and completeness must agree in every acceptance example.
- **SC-003**: All eight shared end-to-end scenarios preserve the same interpretation, scope and numeric meaning across chart, table, saved-report reopening and PDF/CSV evidence.
- **SC-004**: At least twelve PDF examples spanning all chart families, negative/null values, long labels and category/series limits show the selected chart and mandatory scope with no clipped axes, unreadable legends or missing series. Document actual visual inspection results.
- **SC-005**: Every compatible view switch in acceptance testing makes zero additional model requests, leaves analytical values and scope unchanged, and survives saved-report reopening.
- **SC-006**: In an actual keyboard and assistive-technology review, all view controls are named, reachable and operable; every chart has an accessible name, textual interpretation and exact supporting evidence. No essential comparison requires color or hover alone.
- **SC-007**: At least four of five real analysts correctly identify the leading category or time trend and one scope limitation in independently assigned visual tasks without help; retain separate actual results from automated correctness checks.

## Assumptions

- This extends [001-airport-analytics-platform](../001-airport-analytics-platform/spec.md) and consumes the request shapes and verified evidence defined by [002-natural-language-exploration](../002-natural-language-exploration/spec.md).
- Existing compatible grouped results can demonstrate this feature independently. New distributions, changes, paired values and two-dimensional outputs depend on the exploration feature; integrated release requires both to pass the eight shared cases.
- Series/category limits, the 5,000-point threshold and density-grid bounds are proposed product defaults for review, not measured performance limits.
- Full-population density is a presentation aggregation, not a random sample; counts must reconcile with valid pairs. Density cells have at most 400 groups and do not waive analytical/export bounds.
- Maps, pie/donut charts, forecasts, statistical inference, regression fitting and arbitrary custom chart authoring are outside this feature.
- PDF is the visual export format; CSV remains tabular. Interactive hover details must not be the only place material meaning appears.
- No chart implementation, live interpretation acceptance, PDF visual review or analyst study has been performed for this draft. Existing release gates remain in force.
