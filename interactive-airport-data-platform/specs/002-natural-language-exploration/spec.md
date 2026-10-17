# Feature Specification: Natural-Language Exploration and Grouped Analysis

**Feature Branch**: Not created; specifications are independent of branch names.

**Created**: 2026-10-17

**Status**: Draft - awaiting owner review; no implementation authorized by this document.

**Input**: User requested a combination of flexible interpretation, visible scope defaults, conversational clarification, bounded listings, and paraphrase evaluation, expanded to all ten proposed request types. Create two linked specifications first and implement only after review.

## Clarifications

### Session 2026-10-17

- Q: Should one question support multiple independent analyses? A: Support up to four analyses in a single composite report, with an individually defined result and scope for each analysis.
- Q: How should composite requests handle clarification and section failures? A: Resolve all ambiguities before execution, retain successful sections after runtime failures, and require explicit acknowledgement to save/export an incomplete report; PDF rendering failures still produce no partial PDF.
- Q: Should aggregate exports match the bounded report result or introduce a separate larger export? A: Export the selected aggregate result with at most 500 groups per section; keep the separate 10,000-row entity/flight listing export ceiling.
- Q: How many unresolved clarification turns are allowed before guided correction? A: Three answered turns per analysis section, then editable structured correction, restart or cancel; preserve resolved choices, exclude provider failures from the count, and never automatically retry.
- Q: What numerical tolerance applies to independent non-integer calculations? A: Exact discrete evidence; finite computed non-integer results pass only if absolute error is at most max(1e-9, 1e-12 times the absolute expected value). Record errors, never compare rounded strings, and preserve stored values faithfully in visuals; align 003.

**Airport-question extension decisions**

- Q: Which dates contribute to daily destination averages? A: All verified calendar days, including verified zero-flight days; unknown coverage is not zero. Average daily distinct counts by weekday for weekday results. Unqualified rounded averages use nearest whole number, half-up, while retaining unrounded evidence.
- Q: What does unqualified accumulated departure delay mean? A: Sum positive delay minutes with early departures contributing zero; signed net delay is a separately named explicit alternative.
- Q: How should departure-delay/weather correlation be calculated? A: Support descriptive comparisons plus Pearson correlation using equal-weighted matched origin-hours, pairing hourly mean departure delay with temperature, wind speed, precipitation and visibility; require at least three valid pairs and varying values, disclose exclusions and make no causal/significance claim.
- Q: What does ranking by daily seat availability mean? A: Rank by average daily recorded-flight seat capacity, retaining daily totals and missing-seat coverage; it is not unsold/bookable seats or actual passenger load.
- Q: What is the default frequency basis for the most common manufacturer/model? A: Count distinct observed aircraft tail numbers by default; support flight-activity frequency only when explicitly requested, with missing-reference coverage and manufacturer-qualified model identity.

**Coverage clarification**

- Q: What evidence establishes complete calendar-day coverage for daily averages? A: Require a documented, validated snapshot-specific coverage declaration for origins/dates and known gaps. Without verified coverage, offer an observed-operating-day average only after explicit analyst selection; a click cannot verify coverage.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ask ordinary summary and grouped questions (Priority: P1)

An analyst asks a question without learning metric identifiers or a required sentence format, and receives a correct answer with a visible interpretation.

**Why this priority**: Exact wording currently prevents analysts from reaching calculations the product can already express.

**Independent Test**: Submit independently authored paraphrases and compare the resulting measure, population, grouping, and values with independently calculated expectations.

**Acceptance Scenarios**:

1. **Given** the complete historical flight snapshot, **When** the analyst asks "How many flights are there?", **Then** the report counts all flight records, uses all available dates and origins, and discloses those defaults.
2. **Given** the same snapshot, **When** the analyst asks "How many places can you fly to from each airport?", **Then** the report counts distinct destinations separately for EWR, JFK, and LGA, with supporting routes and no requirement to name those codes.
3. **Given** an explicit "all airports combined" request, **When** distinct destinations are counted, **Then** shared destinations count once across origins rather than summing airport-level distinct counts.
4. **Given** a report for EWR in June, **When** the analyst requests "Now compare all three airports", **Then** the origin restriction is removed, June remains active, and the changed scope is displayed.

### User Story 2 - Resolve ambiguity without rewriting the question (Priority: P1)

An analyst answers a short clarification using a choice or free text and continues the original request.

**Why this priority**: Ambiguity should initiate assistance, not a technical rejection loop.

**Independent Test**: Start an ambiguous request, answer the clarification, and verify only the completed interpretation produces an analysis.

**Acceptance Scenarios**:

1. **Given** no active context, **When** the analyst asks "Show all flights", **Then** the product offers total count, breakdown, or individual-record browsing rather than silently choosing.
2. **Given** "How many destinations does the airport have?", **When** no airport is identified, **Then** the product asks which origin or offers all origins, preserving the requested measure.
3. **Given** a pending clarification, **When** the analyst selects "Individual records", **Then** the original request becomes a bounded flight listing with the inherited scope.
4. **Given** a pending request, **When** the analyst cancels or starts a new question, **Then** stale clarification answers cannot change the new request.
5. **Given** an ambiguous reference such as "Springfield", **When** multiple airport matches exist, **Then** the product presents candidate names/codes rather than choosing an arbitrary airport.

### User Story 3 - Explore entities and individual records (Priority: P2)

An analyst lists airports, destinations, or flight records without confusing entities with aggregates.

**Why this priority**: Exploration supplies useful answers even when the analyst does not yet know what to measure.

**Independent Test**: Reconcile a unique list and multiple record pages with the source population, including exact totals and export bounds.

**Acceptance Scenarios**:

1. **Given** "List all destinations", **When** no reference population is requested, **Then** return unique destinations observed in the filtered flight population, with names where matched, not one row per flight.
2. **Given** "List all airports", **When** no further scope is provided, **Then** list observed departure airports and label that population; explicitly requesting the airport reference dataset instead lists that dataset and labels it separately.
3. **Given** a flight listing larger than one page, **When** the analyst visits successive pages, **Then** stable ordering yields no duplicated or omitted source identifiers within the unchanged snapshot.
4. **Given** more records than the export bound, **When** export is requested, **Then** the product discloses the bound and exported/total counts and requires confirmation of a partial export.

### User Story 4 - Compare, rank, and explore time and distributions (Priority: P2)

An analyst asks richer descriptive questions without having to specify the mechanics of aggregation.

**Why this priority**: The ten request types should be useful analytical journeys, not merely ten labels for counting.

**Independent Test**: Validate each request family against fixed source-derived expected results and definitions, independently of visual presentation.

**Acceptance Scenarios**:

1. **Given** "Which airlines have the longest average departure delays?", **When** ranked results are returned, **Then** each airline has a mean, non-missing observation count, and tie/limit disclosure.
2. **Given** "Compare flights from JFK and LGA by month", **When** interpreted, **Then** both origins share the same monthly periods and definition; one origin is not silently discarded.
3. **Given** "How did flight volume change from June to July 2013?", **When** calculated, **Then** show both totals, absolute change, and percentage change using June as the denominator.
4. **Given** "How are departure delays distributed?", **When** reported, **Then** show labelled, non-overlapping delay intervals, counts, missing observations, and the selected population.
5. **Given** "How do departure and arrival delays relate?", **When** reported, **Then** pair observations from the same flights, disclose pairwise missingness, and make no causal claim.

### User Story 5 - Ask several related analyses in one report (Priority: P2)

An analyst submits up to four independent analyses and receives one report with individually labelled sections rather than losing parts of the question.

**Why this priority**: The owner explicitly expanded the feature to cover a composite analytical answer.

**Independent Test**: Submit four independently checkable analyses, clarify one section, and inject a runtime failure in another; verify execution gating and truthful partial-report handling.

**Acceptance Scenarios**:

1. **Given** four supported analyses sharing June at JFK, **When** one has an explicit LGA override, **Then** the report has four sections with the shared scope and override correctly identified, using one common validated snapshot.
2. **Given** a fifth independent analysis, **When** submitted, **Then** ask the analyst to select up to four or split the request before execution.
3. **Given** one unresolved section, **When** other sections are ready, **Then** none executes until clarification completes or the analyst explicitly removes the unresolved section.
4. **Given** a section runtime failure, **When** other sections succeed, **Then** the incomplete result preserves section identities and safe failure notices; saving/exporting requires explicit acknowledgement and never claims complete success.

### Edge Cases

- Airport names/codes, case variations, everyday synonyms, punctuation, and minor spelling errors; ambiguous matches require clarification.
- "New York" means the available NYC-area origins when explicitly used as an origin region; other geographic meanings require clarification.
- "All" changes only the named restriction; an explicit new question does not inherit unrelated old scope.
- Empty results, unmatched reference names, missing measures, zero baseline, negative delays, tied ranks, and incomplete periods.
- An explicit date outside coverage must not be replaced silently with 2013 or described as zero observed activity.
- Month-to-month comparisons across different-length months disclose exposure; counts and per-day rates must not be conflated.
- Multiple requested analyses must not be silently reduced to one; support up to four in one composite report and ask the analyst to choose or split requests above that limit.
- Source changes between pages require a visible refresh/restart of browsing, not a mixture of snapshots.
- Provider failures remain distinguishable from ambiguity and unsupported analysis; no fabricated answer or unapproved retry.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Support all ten request families in the request taxonomy below through ordinary English, including synonyms, short phrases, and question forms, without requiring internal identifiers. AQ-01 through AQ-10 are required acceptance examples, not a sentence whitelist or replacement for general exploration. Resolve new wording and supported combinations of approved measures, dimensions and filters through the same reusable analytical definitions; do not restrict a capability to its example question or introduce arbitrary unapproved calculations.
- **FR-002**: Show a per-section interpretation summary following the logical contract below before or alongside every answer. Provide labelled editable fields for resolved entities, metric/listing type, filters, dates/grain and bounds, with Apply/Cancel and validation; editing does not change the current report until explicitly submitted as a new analysis revision. Preserve the original wording and visibly identify analyst corrections, defaults and inherited fields; do not require reconstructing the question.
- **FR-003**: For new questions without period or airport restrictions, default to all available snapshot dates and observed origins. Distinguish full-snapshot scope from worldwide/live coverage. Do not require optional filters to obtain an answer.
- **FR-004**: Distinguish "each/per/by" grouping from "all combined" aggregation. Distinct counts must be recomputed at the requested grain, never obtained by summing overlapping distinct groups.
- **FR-005**: Apply the entity-resolution policy below to names/codes, approved aliases and candidate spelling matches. Exact valid codes take precedence; an unresolved/ambiguous entity that changes the requested scope blocks that section and therefore composite execution until resolved or explicitly removed. Do not execute a broader population with only a warning in place of the requested entity.
- **FR-006**: Ask one focused clarification at a time only when materially different plausible interpretations remain. Offer labelled choices plus free text, preserve the request and already resolved scope, and never execute an unresolved request. Permit at most three answered clarification turns per analysis section; if the third answer remains ambiguous, offer structured correction of unresolved fields, restart or cancel instead of another free-text clarification loop. Provider failures do not consume an answered turn. Composite requests clarify sections in request order and execute only after all sections resolve.
- **FR-007**: Make pending clarification cancellable and session-isolated. A new unrelated question replaces pending context; clarification responses may not modify a different request.
- **FR-008**: Follow-ups use the explicit field-level inheritance rules below. Explicit replacements/removals take precedence, including expanding one airport to all origins; show retained, added, replaced and removed constraints separately. In a composite report, require a target section or an explicit all-sections instruction before applying an ambiguous follow-up. New unrelated questions inherit nothing.
- **FR-009**: Support grouped summaries with one or two compatible dimensions for the measures in the analytical-definition table, including FR-032 through FR-036's daily averages, weekday summaries, accumulated delays, seat-capacity ranks and aircraft frequencies. Aircraft/reference/weather measures retain their defined grain, weighting, and match requirements. Explain unsupported combinations rather than silently dropping a dimension.
- **FR-010**: Unique entity lists must identify whether they represent observed origins, observed destinations, observed airlines, or an explicitly requested airport reference population. Provide codes and matched names where available, exact total entity counts, and unmatched-name disclosure.
- **FR-011**: Individual-flight browsing must show a deterministic, snapshot-bound order, unique source-row identity, active scope, exact matching count, and page position. Default to 100 rows per page, permit 25/50/100/500, and never load the full population into a single report page. Default order is ascending validated source-row identifier; an explicitly requested supported order appends source-row identifier as a stable tie-breaker. Unique entity lists order by stable entity code. Changing page size, filters or sort resets to the first page and updates the displayed total; an out-of-range page request shows a notice and resets to the first valid page (or empty state). Source changes invalidate continuation and require explicit refresh/restart against a newly validated snapshot, never mixed-snapshot pages.
- **FR-012**: Listing exports are bounded to 10,000 rows per export, include stable ordering, scope/snapshot identification and exported/total counts, and must not claim completeness when partial. Require explicit confirmation for partial exports; allow further filtering instead. Exporting individual records must not transmit them to a model.
- **FR-013**: Aggregate/grouped results and their data exports remain bounded to 500 selected groups per analysis section, with a default top ten for ranking requests and all groups up to the bound for explicit "each/all" requests. State exact total groups, selected/displayed groups, ordering, omitted groups, and cutoff ties; no silent truncation. Rank order uses the requested metric direction with stable dimension-code secondary order; unranked "each/all" uses declared dimension order and selects the first 500 when necessary. A requested top-N above 500 requires correction before execution. Keep the requested count at a tied cutoff, disclose omitted ties and do not expand beyond the bound. Aggregate exports contain the selected analytical result, not an undisclosed larger group set; chart subsets may be smaller and must be labelled separately. Aggregate table pagination may navigate those selected groups but never bypass the 500-group ceiling. The 10,000-row listing export rule does not apply to aggregate results.
- **FR-014**: Rankings and category comparisons must use consistent definitions, units, periods and weighting, show observation counts, preserve ties, distinguish highest/lowest direction, and avoid unsupported significance claims.
- **FR-015**: Historical trends support daily, calendar-week, and calendar-month grain, defaulting to month when unspecified. Weeks start Monday; labels state calendar convention. An absent observation must remain distinguishable from an observed zero. Use recorded departure calendar dates without UTC/viewer-time-zone conversion; intraday/time-zone analysis remains out of scope.
- **FR-016**: Period changes compare the same metric and population over two explicitly identified periods, returning both values, absolute change (comparison minus baseline) and percentage change (100 times that difference divided by the baseline). A zero or unavailable baseline makes percentage change unavailable with an explanation; a negative baseline retains the signed formula with a warning that percentage direction is not an improvement/worsening judgment. An unqualified "previous period" uses an adjacent equal-length date window; "previous month/year" uses the preceding calendar period. Disclose partial coverage and unequal exposure.
- **FR-017**: Distributions initially support flight-level departure delay, arrival delay, and distance. Use reproducible equal-width bins starting at the largest whole multiple of the width not exceeding the observed minimum. Intervals include the left endpoint and exclude the right; extend the final interval beyond the maximum so every non-missing observation belongs to exactly one bin. Display exact boundaries, count missing observations separately, and reconcile non-missing bin counts to the filtered source population. Default widths are 15 minutes for delays and 250 miles for distance; all widths, including defaults, are allowed only with at most 100 bins. Explain a limit violation and offer coarser bins rather than silently changing width.
- **FR-018**: Relationships support any distinct pair of flight-level departure delay, arrival delay, and distance, using paired non-missing values from the same source rows, plus the explicitly defined origin-hour weather analysis in FR-034. Keep these grains distinct and disclose paired/excluded counts and units. Descriptive Pearson coefficients are authorized only for FR-034; do not imply causation or add forecasting, significance testing or fitted regression.
- **FR-019**: Analytical results must be based on validated source data and approved definitions, not model-generated numbers or executable instructions. Preserve existing identity, ownership, disclosure, budget, consent, and source-integrity protections; explain unsupported requests safely.
- **FR-020**: Save the resolved interpretation, definitions, result grain, scope, snapshot, completeness information and relevant clarification choices with the private report, under existing retention/ownership rules. Do not introduce indefinite conversational transcript retention.
- **FR-021**: Validate natural-language interpretation with a fixed, independently labelled corpus of at least 100 unambiguous requests, ten per request family, plus at least 20 ambiguous/unsupported requests. Include short wording, synonyms, names/codes, and follow-up expansion; do not evaluate by supplying expected analysis instructions in place of user wording.
- **FR-022**: Run the shared end-to-end acceptance cases below with the linked visual-report feature, checking the interpretation, numbers, visualization, saved report, and exports against the same scope. Document actual outcomes; do not substitute mocked provider results for live interpretation acceptance.
- **FR-023**: Support up to four independent analyses in one composite report. Identify each section's request family, interpretation, scope, measure, evidence and outcome; a comparison, period change or numeric relationship is one analysis, not one per variable/period. Shared scope applies only where explicitly common, and section overrides remain visible. Requests above four require selection/splitting before execution; do not silently omit sections. Simultaneous means one submitted composite request, not a requirement for parallel provider/query execution. Preserve existing budget/disclosure gates and report section failures explicitly rather than presenting a partial success as complete.
- **FR-024**: Resolve every section's ambiguity before any composite execution. Unsupported/invalid sections require correction, explicit removal or cancellation before execution; removal is disclosed rather than silently reducing the request. After runtime failures, retain successful sections with independent statuses and explanations. Empty-but-valid sections are completed empty outcomes, not failures. Require explicit acknowledgement before saving/exporting an incomplete composite report and retain the original requested section identities and failure notices in every representation. An acknowledged incomplete analytical report can be exported only as a complete rendering of its successful evidence and failure disclosures; a technical PDF rendering failure never permits a partial file.
- **FR-025**: Implement the request-state and outcome contracts below, including stale-answer rejection, structured correction after the clarification bound and session/request/section isolation. Distinguish unsupported, ambiguous, invalid scope, valid empty, provider failure, invalid provider output, unavailable source, execution failure and budget/disclosure refusal; do not translate operational faults into claims that the analyst's wording is unsupported.
- **FR-026**: Follow the analytical-definition table and period/binning rules below. Unsupported dimension/metric combinations require an explanation naming the unsupported combination and an available correction; do not drop a field, alter weighting or average already aggregated means.
- **FR-027**: Preserve the saved-report contract below, with original snapshot provenance and saved interpretation on reopening. A composite counts as one report under existing ten-report retention, contains up to four sections on the same validated snapshot, and owns its section-level visual preferences/evidence. Do not create a separate indefinite retention path for drafts or failures.
- **FR-028**: Apply the corpus methodology below to live candidate interpretation. Record frozen corpus/snapshot versions, provider/model/settings, actual outcomes and safe failure categories; do not count provider failures as excluded successes or silently replace them through retries.
- **FR-029**: Apply 003's English number/date/unit formatting and faithful code/name presentation to interpretation summaries and saved/exported evidence. Preserve unrounded numbers for validation. Use the shared date-only calendar convention and never invent a canonical UTC time zone for source date fields.
- **FR-030**: Treat the page/export/group/bin and four-section ceilings as fixed release bounds. State counts and completeness per section and for the composite; those limits do not multiply within a section or authorize an unbounded composite export. A combined listing export has at most 10,000 data rows across its listing sections, allocated by an explicit analyst choice; partial selection requires confirmation. Separate listing exports remain independently bounded. Aggregate evidence retains its separate 500-group ceiling per section.
- **FR-031**: Pass the cross-spec consistency/release rules below. Maintain actual dated execution records rather than treating draft checklists as proof of acceptance. Performance remains baseline measurement with visible loading, recoverable errors and safe content-free metrics; no numerical product latency target or background-job feature is added here.
- **FR-032**: Support average daily distinct destinations through two stages: compute each date's distinct non-missing destination count, then take the equal-day arithmetic mean over verified calendar days in the requested scope. Include verified zero-flight days; exclude dates with unknown coverage from the verified-day mean and disclose excluded/verified/requested day counts and incompleteness. With no verified days, return unavailable, not zero. Support the same calculation grouped by departure-date weekday, ordered Monday-Sunday with a separate eligible-day denominator per weekday; no eligible occurrence is unavailable. An unqualified "rounded average" displays nearest whole-number half-up rounding, while preserving the unrounded calculation and explicit requested precision. This is an approved two-stage mean over daily counts, not a shortcut that averages incompatible already-aggregated metrics. Never substitute period-wide distinct count divided by days or distinct destinations across all Mondays combined.
- **FR-033**: Support calendar-month rankings by flight count and accumulated departure delay. Unqualified accumulated departure delay is the sum of max(departure delay, 0) for known delays, in minutes; early departures contribute zero, missing values are excluded and counted, and a group with no known delays is unavailable. Explicit "net departure delay" instead sums signed known minutes and must be labelled separately. Show flight and known-delay counts, period/coverage and ranked monthly totals, identify all equal maxima in the selected scope, and preserve ties and bounded-result disclosures. Do not describe raw accumulated totals as a delay rate or evidence of worse typical performance.
- **FR-034**: Support the weather-correlation question with descriptive precipitation-band delay comparisons and a four-variable Pearson summary: temperature, wind speed, precipitation and visibility. Match flights to weather by validated exact origin/time_hour. First compute each origin-hour's mean of known departure delays, then pair that mean with the hour's weather value, weighting each eligible origin-hour equally, not each flight. Compute separate valid-pair and excluded counts per variable; require at least three pairs and positive variation in both variables or return an unavailable coefficient with reason. Preserve weather units from the validated source definitions and show paired origin-hour evidence, flight counts and match/missingness coverage. Explain that coefficients describe association, not causation, independence or statistical significance; no p-values, regression or causal claims. Broad weather wording maps to this disclosed predefined analysis; arbitrary weather variables, alternate weighting and weather forecasts are not silently substituted.
- **FR-035**: Support airline rankings by flight count and average daily recorded-flight seat capacity. For capacity, match unique plane reference rows by tail number, sum known nonnegative seats once per recorded flight per calendar date and airline, then average those daily totals over a common set of verified scope dates across airlines, using FR-032's date-coverage policy. A verified day with no airline flights contributes zero; missing plane/seat data is unknown, never a zero-seat flight. Expose known-capacity sums, daily supporting totals, known/unknown flight counts and complete/incomplete day counts. When missing seats make an estimate incomplete, label it known-seat capacity only and the ranking provisional, not a definitive full-capacity winner; with no known contributing seat values for an operating airline, return unavailable rather than zero. Do not call this unsold seats, ticket availability, actual load or a verified historical seat configuration.
- **FR-036**: Support most-common manufacturer/model rankings using distinct non-missing tail numbers observed in filtered flights by default, matched to unique plane references. Count each aircraft once per requested group regardless of repeated flights; do not rank the entire unfiltered plane reference file. Identify models by manufacturer plus model, retain raw reference labels without silently merging aliases and expose missing/unmatched manufacturer/model aircraft counts separately from ranked known categories. Identify tied maxima and the coverage limitation. Explicit flight-activity frequency instead counts matched flight records and is labelled differently; never silently substitute it for the distinct-aircraft default.
- **FR-037**: Calendar-day coverage must come from a snapshot-specific declaration identifying covered origin/date intervals, known gaps, supporting source documentation, validation results and declaration provenance/version. Validate applicability to the exact snapshot and origin scope before using it to establish verified zero-flight days or equal-calendar-day denominators. Observed min/max dates, the existence of some flights on a day, an analyst acknowledgement or an operator flag alone do not establish complete coverage. Missing, stale, conflicting or inadequately supported declarations leave affected dates' coverage unknown; do not carry declarations automatically to a changed snapshot. If no eligible calendar-day denominator is established, explain the limitation and offer an observed-operating-day alternative only after explicit analyst selection, with its different population, denominator and incomplete-coverage notice saved/exported. Do not silently replace the requested calendar-day result.

**Logical Interpretation contract**

Each section records request/section identity, original wording, one canonical request family, declared analytical form, resolved entity codes and reference names, measure(s)/units, output grain, dimension roles/order, aggregation/weighting/additivity, snapshot and source population, filters, requested and observed/verified periods, calendar grain, bounds and clarification/correction choices. Each scope field identifies its source: explicit wording, analyst correction, clarification, inherited scope or fresh default. Requested dates and verified coverage are not interchangeable.

The summary and evaluation labels use this same contract. Composite metadata identifies shared scope and per-section overrides and retains one outcome per requested section. Relevant clarification choices persist with a saved report, not a permanent transcript of all exchanges. Concrete field types, serialization, schema versioning and validation mechanics belong in planning/contracts, not this logical requirement.

**Request state and outcome contract**

| State | Trigger and permitted next action |
|-------|----------------------------------|
| Unresolved | New/revised request; validate bounds and section identities, then resolve or ask a focused question |
| Clarification pending | One identified ambiguity in one section; await answer, cancellation or superseding request; no analytical execution |
| Clarification answered | Analyst choice/free text; increment that section's answered-turn count and revalidate; resolve, ask the next permitted question, or enter guided correction after turn three |
| Guided correction | Third answer remains ambiguous; edit unresolved structured fields or restart/cancel; Apply revalidates, without reopening an unlimited free-text question loop |
| Resolved | All section interpretations valid; authorize existing provider/budget/disclosure gates as applicable, then execute the composite |
| Executing | Compute application-owned results; retain per-section outcomes; no background/parallel execution promise |
| Completed / incomplete | All sections completed (including valid empty), or at least one runtime failure; incomplete save/export requires acknowledgement and disclosures |
| Failed | Whole-request provider/source/authorization failure before results; preserve input/resolved choices and offer correction or explicit permitted retry |
| Cancelled / superseded | Analyst cancels, signs out/session ends, or starts an unrelated question; old answers cannot resume or modify the replacement request |

Bind each answer to the analyst's current session, request revision and section identity. A stale/tab-delayed answer is rejected with a notice rather than applied to the current request. Pending state is session-only and clears at sign-out/session end; this feature adds no separate wall-clock expiration duration. Runtime mechanism for identifiers and isolation belongs in planning.

| Outcome | Required response |
|---------|-------------------|
| Ambiguous | Focused choices/free text for the unresolved distinction, with already resolved scope retained |
| Unsupported | Name the unsupported concept/combination, preserve input, offer supported alternatives without executing a replacement |
| Invalid scope | Identify invalid dates, contradictory filters, unresolved entity or over-limit request, and provide an editable correction |
| Valid empty | State that no verified records match the shown scope; show verified matching count and provenance. Do not present unavailable averages as zero |
| Provider unavailable / invalid output | Distinct safe operational message; no raw provider body/credentials, no guessed plan; preserve input and resolved choices |
| Source/execution failure | Explicit unavailable/failed-analysis message; no stale snapshot or success-shaped substitute |
| Disclosure/budget refusal | Explain the unmet gate and permitted next action, not a promise that rewriting will fix it |

Never automatically retry or switch providers. An analyst may explicitly retry a failed call only after existing authorization and disclosure checks; a possibly accepted paid call remains blocked until its uncertain cost is reconciled under 001. Safe diagnostic events may include request correlation, outcome category, durations and model/budget metadata, but not wording, clarification text, source rows, entity labels, filter values or report content. Failed-only requests are not successful saved reports or exports; acknowledged partial composites retain failure category and safe explanation, never raw errors.

**Follow-up inheritance and entity resolution**

- A clearly marked follow-up inherits the target section's measure/request family, nonconflicting filters, date restriction, grouping/time grain, population, sort and result bound unless the wording replaces/removes them. An explicit change of request family drops incompatible measure/group/sort fields and asks about any remaining material ambiguity. Listing page position never inherits; restart at page one.
- "All airports" removes origin restrictions only; "all destinations" removes destination restrictions only; "all dates" removes the time restriction only. Explicit add/replace/remove actions supersede inherited/default values. Fresh all-data defaults are recalculated only for a new request or an explicitly refreshed snapshot, and labelled as such.
- For an older saved report or changed snapshot, show the original and currently available snapshot identifiers/coverage. Reopening preserves old evidence; follow-up recomputation requires explicit acknowledgement of the new snapshot and revalidated entities/scope. If historical source rows are unavailable, do not pretend to browse/recompute them.
- Match explicit valid airport/airline codes case-insensitively before names; match normalized reference names/approved aliases next. Normalize surrounding whitespace, case and punctuation without collapsing different entity codes. Exact unambiguous approved names/aliases may resolve automatically; spelling-similarity suggestions require analyst confirmation even when only one candidate is suggested. Alias contents and fuzzy matching mechanics are planning decisions and must be versioned/tested.
- Candidate choices show code, reference name, region where known and observed/reference-only status; order exact name/alias matches first, then spelling candidates, with stable code tie-breaks. A valid exact code resolves directly, while multiple name candidates require a choice. "New York" used explicitly as an origin region means EWR/JFK/LGA via a documented region alias; other meanings require clarification.
- Observed origins/destinations/airlines come from filtered flight rows, enriched by reference names through validated non-fan-out joins. Keep unmatched codes and label missing reference names; do not exclude flights because enrichment failed. "List all airports" defaults to observed departure origins, while an explicit airport-reference listing belongs to the unique-entity family and uses all airport reference entries, not only observed flight origins.
- Airline references enrich observed airlines; arbitrary full reference browsing is not implied. Planes and weather are supporting references/context, not new listing families. An entity present only in a reference dataset may validly yield no flight matches; distinguish that verified empty population from an unresolved code.

**Analytical definitions and supported dimensions**

In this table, common flight dimensions are origin, destination, carrier/airline name, tail number, aircraft manufacturer/model, precipitation context and daily/weekly/monthly departure-date bucket. A grouping uses at most two distinct dimension roles; do not duplicate carrier and airline name or two calendar grains as separate dimensions. Reference requirements apply even when introduced only by a filter. For measures not requiring a successful weather match, precipitation grouping retains a distinct unmatched-weather category rather than applying the weather-delay measure's exclusion.

| Measure | Calculation, grain and exclusions | Allowed dimensions |
|---------|---------------------------------|--------------------|
| Flight count | Count matching source flight-row identities, including valid repeated observations with different IDs | Common flight dimensions |
| Distinct destinations | Unique non-missing destination codes among filtered flights, recomputed independently within each group; non-additive | Origin and one date-bucket grain |
| Mean departure/arrival delay | Sum of that non-missing flight-level delay divided by its non-missing count, in minutes; negative means early | Common flight dimensions |
| Mean distance | Flight-weighted mean of non-missing scheduled route miles | Origin, destination, carrier/airline name, tail number, precipitation context, one date-bucket grain; aircraft manufacturer/model grouping unsupported in this release |
| Distinct aircraft | Unique non-missing tail numbers among filtered flights, not a count of plane-reference entries; non-additive | Common flight dimensions |
| Mean seats | Mean matched reference seat value once per matching flight observation with known seats; flight-weighted, not one vote per aircraft | Common flight dimensions; validated unique tail-number reference match |
| Weather-context departure delay | Mean non-missing departure delay among exact origin/time-hour weather matches; precipitation context is none (0), light (>0 and <0.1 inch), at least 0.1 inch, or missing precipitation within matched weather | Precipitation band, origin and one date-bucket grain, at most two |
| Average daily distinct destinations | Distinct destinations per verified date, then equal-day mean; zero/unknown dates and rounding follow FR-032 | Overall, origin, weekday Monday-Sunday, or origin plus weekday; daily evidence remains available |
| Accumulated / net departure delay | Positive-minute sum by default; signed sum only explicitly requested; known/missing counts follow FR-033 | Common flight dimensions, including monthly rank |
| Average daily recorded-flight seat capacity | Known seats summed per flight/date/airline, then equal-day mean with common date denominator and missing-capacity flags | Carrier/airline identity, optionally origin; supporting date totals are not an extra requested analysis |
| Manufacturer/model frequency | Distinct observed tail numbers by default; explicitly requested flight frequency uses source flight counts | Manufacturer or manufacturer-qualified model, optionally origin or one date-bucket grain |
| Weather Pearson correlation | Pair hourly mean departure delay with one of four weather variables at equal-weighted origin-hour grain | One coefficient per variable with optional origin breakdown; no flight-level replication or arbitrary extra grouping |

Aircraft joins use unique tail number; weather joins use exact origin/time_hour and validated context keys. Expose filtered pre-match denominator, matched/unmatched rows and non-missing measure counts, before match-only exclusions; unknown reference/category values remain distinguishable. Weather-unmatched rows are excluded from the weather-delay calculation, while matched rows with missing precipitation retain a labelled missing-context group. Weather is associative, never causal. Existing mean values must not be summed/averaged to change grain: recompute from source-level numerators/denominators. Distinct-count non-additivity applies to both destinations and aircraft; weather context is not a separate distinct-count metric.

**Distribution and period arithmetic**

- For width w, first-bin lower boundary is floor(minimum/w) times w, including negative minima. Include successive left-closed/right-open intervals through a final upper endpoint strictly greater than the maximum; a constant-valued population produces one positive-width interval, never zero width. Include zero-count intervals between endpoints. Bin counts sum exactly to the filtered population minus missing measurements; pair/distribution invalid numeric data fail validation rather than being silently dropped.
- If the proposed/default width requires more than 100 bins, do not execute that distribution silently. Offer the smallest positive integer multiple of the requested/default width yielding at most 100 bins under the same anchored-boundary rule. Show proposed width/bounds and ask for acceptance, an explicit different valid width or cancellation. No assumption about global/transcontinental range bypasses the bound. Bin definitions are immutable visual inputs; 003 must not re-bin.
- Date ranges have inclusive calendar-date endpoints. For current range [s,e] with d calendar days, unqualified previous period is [s-d,s-1], also d days. "Previous month/year" for a complete calendar period means the full previous calendar period; for a partial range shift endpoints by that calendar unit, clamp invalid dates to the last valid day, and disclose changed day counts. If no current/comparison period is resolvable, ask rather than defaulting to the wall-clock date.
- Absolute change is available whenever both values are finite, including a zero baseline. An unavailable baseline/comparison makes absolute and relative change unavailable. A zero baseline shows "Percentage change unavailable: baseline is zero." A negative baseline retains the signed formula and shows "Negative baseline: percentage direction does not indicate improvement or worsening." Preserve flags/explanations in tables, saved evidence and exports.
- Distinguish requested interval, verified source coverage/completeness, observed bounds, missing measure rows and calendar buckets. Mark clipped intervals/partial calendar buckets explicitly; unknown coverage remains unknown. No-row dates do not establish source completeness. Use recorded calendar dates, not an invented time zone or DST arithmetic.
- Unequal calendar exposure is disclosed with day counts; do not automatically add a normalized per-day rate or infer improvement from a raw-count change. Only FR-032's daily-destination and FR-035's daily-capacity definitions authorize equal-day averaging here; other per-day rates require a separately approved analytical definition.

**Required airport-question support**

The following are mandatory supported questions, not a replacement for the ten request-family taxonomy. "The airport" still requires a resolved origin or explicit all-origin choice; omitted dates use disclosed historical coverage. Each is one analysis, including the predefined weather panel with four variable summaries. Ten independent questions exceed the four-section composite ceiling: offer separate submissions or an explicitly confirmed partition such as 4/2/2/2 by the headings below, not one silently truncated report.

| ID / area | Question | Required definition and result |
|-----------|----------|--------------------------------|
| AQ-01 Overall | Determine the number of distinct destinations connected to the airport | Observed outbound distinct destination codes in the selected flight scope; scalar plus supporting routes |
| AQ-02 Overall | Calculate the rounded average of distinct destinations for each day | Resolve wording as average daily distinct destinations under FR-032 and disclose the two stages; if the analyst instead means one count per date, allow that correction |
| AQ-03 Overall | Calculate the average number of destinations per day of the week | Daily distinct counts averaged within Monday-Sunday, separate eligible-day denominators and unrounded evidence |
| AQ-04 Overall | Identify the month with the highest number of flights | Flight counts per calendar year-month, descending rank, all tied maxima disclosed |
| AQ-05 Delays | Identify the month with the highest accumulated departure delay | Positive delay minutes per year-month by default; signed net only as an explicit alternative |
| AQ-06 Delays | Analyze the correlation between departure delay and weather conditions by cross-referencing the departure delay data with the weather dataset | FR-034 origin-hour Pearson summary for four variables, descriptive precipitation comparison, matching and excluded evidence |
| AQ-07 Airlines | Create a ranking of airlines based on the number of flights they operate | Count filtered source flight records per carrier, enriched names and rank ties |
| AQ-08 Airlines | Create a ranking of airlines based on the daily availability of seats | FR-035 average daily recorded-flight known-seat capacity, common date denominator, daily evidence and provisional ranking flags where incomplete |
| AQ-09 Airplanes | Determine the most common plane manufacturer | Distinct observed aircraft per matched manufacturer by default, tie/missing-reference disclosures |
| AQ-10 Airplanes | Identify the most common plane model | Distinct observed aircraft per manufacturer-qualified model by default, tie/missing-reference disclosures |

Weather correlations use the centered Pearson definition: sum of paired deviations' products divided by the square root of the product of the two sums of squared deviations. Use unrounded pairs and return an unavailable value for insufficient/constant evidence. The three-pair threshold is an eligibility rule, not statistical sufficiency or significance. Unmatched hours, hours without known delays, and per-variable missing weather values are reported separately; complete-pair denominators may differ across variables.

Verified-day eligibility must be grounded in validated source coverage, not inferred from a missing flight row. When completeness is unknown, a partial verified-day mean is labelled as such and may be unavailable if no days can be verified. For incomplete seat days, known seat sums are a lower-bound proxy only for recorded-flight reference capacity, not evidence of actual offered/bookable seats. Negative seat values are invalid data, not contributions to the capacity sum.

For the explicitly selected observed-operating-day alternative, destination means use dates with at least one matching flight; weekday means use those operating dates within each weekday. Airline-capacity comparisons use one common set of dates with at least one matching flight across the selected airlines, not each airline's own operating dates; no-flight airline dates in that observed-date set contribute zero recorded-flight capacity, while unknown seat contributions remain unknown under FR-035. Label this as recorded activity on observed dates, not verified complete-day availability. Preserve requested/verified/observed-date counts and the selected denominator basis in Interpretation and Visual Evidence. Changing denominator basis is an analytical revision, never a chart preference.

Compute all approved two-stage metrics and coefficients over their complete eligible populations before applying evidence-display bounds. Daily supporting aggregates retain the 500-group per-section bound with explicit completeness; bounded supporting rows do not become the mean's denominator. Hour-pair visual evidence follows 003's scatter/full-density bounds, not the flight-list export limit. A weather relationship panel uses the source's exact origin/time_hour match key, not the viewer's time zone; this authorized join grain does not add general intraday time-series analysis. All ten cases require independent source-coverage and weather-unit validation during planning/implementation; no complete-day guarantee is claimed by this draft.

**Corpus and usability methodology**

- Keep a versioned, de-identified synthetic corpus and independent expected labels/results in the repository. Use at least 100 frozen unambiguous acceptance requests (ten per family), plus at least twenty ambiguous/unsupported requests and a separate composite suite. Maintain separate development examples; the acceptance wording/labels must not be injected into the candidate prompt or used to tune it during the scored run.
- Two reviewers independently assign family, entities, metric/definition, population, filters, time/grain, bounds and expected clarification/outcome without reading the candidate output. Reconcile disagreements before freezing; record initial agreement, disputed fields and adjudication. Unresolved gold-label disputes block scoring that version rather than being excluded after results are seen. Review paraphrases as ordinary analyst wording without embedded internal IDs or expected plans.
- Freeze corpus and source versions before candidate evaluation. Gold corrections require a declared version change and full rerun, retaining earlier results. Review or tuning on failed acceptance wording makes it development material; replace the exposed cases with independently authored held-out equivalents before a new acceptance claim. No statistical independence/population-quality claim is implied by this process.
- Per-family eight-of-ten and overall ninety-of-one-hundred interpretation thresholds apply to the unambiguous set only. A family failure fails SC-001 even when overall accuracy passes. Provider/authorization/output failures count as failed attempted cases and are reported separately; aborted/incomplete runs cannot pass, and successes from multiple retries cannot be stitched together as one run.
- Ambiguous cases must preserve known constraints and ask about the actual unresolved distinction; entity ambiguity passes by offering valid candidates and awaiting a choice, never by guessing the expected entity. Unsupported cases pass only through the correct explained boundary without execution. Score numerical correctness for every produced section/result, including results from incorrectly interpreted requests; wrong-scope numbers do not become valid merely because they are internally consistent.
- Composite evaluation includes one through four sections, a five-section boundary, shared/overridden scope, clarification in multiple sections, stale responses, and runtime partial-report acknowledgement. These are additional acceptance cases, not a replacement for any of the ten family quotas.
- Human sessions are separate formative evidence using the participant/task rules in SC-006. Record actual unassisted/assisted outcomes and repeat after material usability fixes; no fabricated participants or population-wide accuracy claims.

**Saved-report contract and cross-spec release consistency**

An owned saved report contains report identity, common snapshot/version, original wording and per-section saved interpretations, definitions, unrounded bounded evidence, state/outcome, scope/provenance/completeness, relevant clarification choices, analyst partial-report acknowledgement where applicable and section-level 003 presentation preferences/Visual Evidence. Reopening displays that saved interpretation/evidence, not a newly model-derived interpretation or current-source calculation.

If historical sources are unavailable, saved bounded results still open with a source-unavailable notice; unavailable historical paging/recalculation is disabled with a reason. Never backfill from corrected/current source rows. Later corrections or fresh follow-ups create a separately identified report revision/snapshot, preserving original provenance. Parent ownership checks, ten-report pruning, deletion and pending retention/backup approval apply to all embedded sections/preferences; session-only drafts are not permanent audit transcripts.

002 owns the shared E2E definitions; 003 references them without redefining them. Its Visual Evidence consumes the resolved Interpretation plus validated analytical results; presentation selection cannot change the approved interpretation. The 500-group bound is per section, chart-category/series bounds are smaller presentation subsets, scatter-to-density uses all valid pairs rather than a truncated listing, and listing page/export ceilings remain separate. Shared missingness, ties, coverage/calendar rules and independent numerical tolerance must agree across both specifications.

No integrated release claim is valid until both specifications pass E2E-01 through E2E-09 and their numerical, error/clarification, pagination, visual/export/accessibility and formative-study criteria. At this review, 002/003 remain drafts with no implementation/live evaluation evidence for these extensions; 001's existing protections and outstanding external release gates are not waived. Rendering libraries, concrete schemas, pagination mechanics and fuzzy-match algorithms are deferred to planning, not implied completed work.

### Request Taxonomy

| # | Request family | Example | Answer grain |
|---|----------------|---------|--------------|
| 1 | Overall summary | How many flights are there? | One value for the selected population |
| 2 | Grouped summary | How many destinations does each airport serve? | One aggregate per origin |
| 3 | Unique entity list | List all destinations | One row per unique observed destination |
| 4 | Individual-record browsing | Show individual flights from JFK in June | One row per source flight record, paginated |
| 5 | Ranking | Top ten airlines by average departure delay | Ordered category aggregates with tie disclosure |
| 6 | Category comparison | Compare monthly flight volume at JFK and LGA | Consistent measure per category and month |
| 7 | Historical trend | Show monthly flight volume | One aggregate per time bucket |
| 8 | Period-over-period change | Compare June and July flight totals | Baseline, comparison, absolute and relative change |
| 9 | Distribution | Show the distribution of departure delays | Count per numeric interval plus missingness |
| 10 | Numeric relationship | How do departure and arrival delays relate? | Paired same-flight observations with coverage |

### Shared End-to-End Acceptance Cases

These identifiers are shared with [003-visual-reporting](../003-visual-reporting/spec.md). Both specifications must pass each applicable case; this is a future validation obligation, not recorded test evidence.

| ID | Analyst request | Required analytical evidence | Required presentation/export agreement |
|----|-----------------|------------------------------|----------------------------------------|
| E2E-01 | How many destinations does each airport serve? | Distinct counts per origin, independently reconciled routes | Categorical chart, exact table and matching PDF scope |
| E2E-02 | How busy was each airport each month? | Monthly flight counts per origin, chronological order | Multi-series trend or small multiples; no dropped origin/month |
| E2E-03 | Show all flights, then select individual records | Clarification followed by snapshot-bound pages and total | Paginated table; honest partial export, no arbitrary chart |
| E2E-04 | Compare June and July departure delays at JFK | Both means, non-missing counts and change definition | Labelled comparison; negative/zero-baseline handling preserved |
| E2E-05 | How are departure delays distributed at EWR? | Exact bins, missing count and population reconciliation | Histogram with matching intervals/table/PDF |
| E2E-06 | How do departure and arrival delays relate? | Paired same-flight observations and excluded count | Full scatter or full-population density with binning disclosure; no silent sampling |
| E2E-07 | Top ten destinations by number of flights | Ordered counts, total groups, tied cutoff and bound | Ranked chart with identical displayed values/table/export |
| E2E-08 | How many flights are there? | Overall count with disclosed full-data defaults | Summary card plus evidence; no fabricated comparison |
| E2E-09 | For JFK in June 2013, count flights, show monthly flight counts, list destinations, and show the departure-delay distribution | Four independently checked sections on one snapshot; clarify distribution coarsening if necessary before execution; test a runtime section failure as a separate fault variant | Four section-appropriate views/evidence in one saved report; acknowledge incomplete outcome in the fault variant; PDF fully renders all successful sections and failure notices or fails without a partial file |

### Key Entities *(include if feature involves data)*

- **Exploration Request**: Original wording, request family, resolved entities, metric(s), output grain, scope, defaults, and requested bounds.
- **Clarification State**: Pending request, unresolved distinction, offered choices, resolved answers, and session ownership; temporary rather than a new permanent transcript.
- **Result Population**: Snapshot and filters defining records, entities or aggregate groups, including match/missingness rules.
- **Browse Page**: Stable snapshot/order, page size/position, visible source rows, exact total and completeness.
- **Analytical Definition**: Measure and unit, aggregation/weighting, period comparison rules, bins or paired variables, and material exclusions.
- **Composite Report**: One owned report with one common snapshot and up to four independent section interpretations/evidence/outcomes, shared scope/overrides, section-level visual preferences and explicit incomplete-report acknowledgement.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: At least 90 of the 100 unambiguous corpus requests produce the independently expected request family, population, metric, filters, grain and bounds, with at least eight of ten correct in every family.
- **SC-002**: All 20 ambiguous/unsupported cases either obtain the needed clarification before execution or clearly explain the unsupported boundary; none silently executes a materially different request.
- **SC-003**: Every generated numeric result in the entire acceptance corpus, including all composite sections, agrees with independently calculated expectations. Counts, identifiers, list membership, ordering and bin membership are exact. For finite computed non-integer values, absolute error must be at most max(1e-9, 1e-12 times the absolute expected value); record actual errors and never validate rounded display strings. Null/unavailable outcomes and exclusion definitions must match exactly. A single disagreement outside these rules fails numerical acceptance regardless of interpretation pass rate; chart/table/export views must preserve their stored unrounded values without analytical changes.
- **SC-004**: Unchanged-snapshot pagination across at least three consecutive pages has zero repeated/missing source identifiers relative to the expected ordered slice; export boundary tests at 9,999/10,000/10,001 records correctly disclose completeness.
- **SC-005**: All nine shared end-to-end cases pass interpretation-to-export agreement, including composite failure/acknowledgement and saved-report reopening, without scope or numeric drift.
- **SC-006**: Recruit five real participants who use tabular reports or operational/business analysis, not feature implementers. Preassign a grouped question, a request requiring clarification, and a multi-analysis request with up to four sections, each with independently defined expected scope and outcomes. For each task separately, at least four of five participants must obtain the expected answer/scope, recognize defaults or incompleteness where applicable, and correctly state one scope limitation without moderator hints, corrections, task-specific coaching or a question-writing guide; built-in controls/explanations and accessibility tools are allowed. Score first unaided attempts and record assistance separately from success and from automated results. This is formative evidence, not population-wide accuracy. Repeat after material usability fixes or a failed round with five new representative participants, retaining prior results.
- **SC-007**: State/error tests cover three clarification turns and guided correction, cancelled/superseded/stale/cross-session answers, invalid entities/scope, unsupported sections, valid empty data, provider invalid/unavailable output and budget refusal with zero unintended execution or automatic retries.
- **SC-008**: Boundary tests cover one/four/five independent analyses; 25/50/100/500-row pages and reset/source-change behavior; top-N and 499/500/501 groups with ties; combined listing exports below/at/above 10,000 rows; negative/constant distribution data and 99/100/101 proposed bins. Each result must preserve the declared snapshot, selection order, counts and completeness.
- **SC-009**: Independently verify every supported measure/dimension rule and the unavailable/negative/zero-baseline, inclusive-day, month-end, leap-date and unknown/partial-coverage cases. Counts, missingness, pair exclusions, bin reconciliation and cross-spec stored evidence must meet SC-003 without silent defaulting or altered definitions.
- **SC-010**: Add AQ-01 through AQ-10 and at least three ordinary-language variants of each to an independently labelled acceptance set, separate from the fixed family quotas. Every question must be interpreted to its approved definition (with scope clarification where necessary) and all generated results must meet SC-003. Cover repeated destinations across dates, verified-zero/unknown dates, unequal weekday occurrences, half-up rounding boundaries, tied monthly winners, early/missing delay, repeated weather hours, fewer than three pairs/constant variables, missing seats, aircraft with unequal flight activity, reused model labels and unmatched references. Record live interpretation and independent numerical results; draft requirements are not evidence of a pass.
- **SC-011**: Coverage acceptance cases must include applicable, missing, stale-snapshot, conflicting and gap-bearing declarations, as well as a day with observed flights but no completeness evidence. Only applicable supported coverage may establish verified calendar days. Tests must show that declining the observed-operating-day alternative preserves unavailable calendar-day results, accepting it creates a visibly different analytical revision, and daily/weekday/capacity denominators and saved/visual/export disclosures agree. No acknowledgement alone can change unknown coverage to verified.

## Assumptions

- This feature extends [001-airport-analytics-platform](../001-airport-analytics-platform/spec.md); its protections, historical-data limitations, owner-approved session defaults and guarded development exception remain applicable.
- [003-visual-reporting](../003-visual-reporting/spec.md) is the linked presentation specification. This feature remains independently testable through correct answers and tables before charts are implemented; integrated release requires E2E-01 through E2E-09.
- English remains the supported language. Forecasting, live/global flight coverage, arbitrary calculations, statistical inference, maps, and unrestricted bulk extraction are out of scope.
- Page/export/group and four-section ceilings are fixed release bounds; the defined time grains, bin widths and initial numeric-pair coverage are requirements, not claims about current capabilities. Raising ceilings or expanding measures requires a reviewed requirement change and validation.
- Date-only flight analysis follows recorded departure calendar dates. Intraday/time-zone analysis is outside this extension.
- Establishing a supported coverage declaration is a data-quality prerequisite, not an approval already supplied by this specification. Declaration representation and validation mechanics are planning decisions; no source-completeness guarantee is asserted here.
- No implementation, live-provider evaluation or real analyst study has been performed for this draft. Existing outstanding release gates are not waived.
