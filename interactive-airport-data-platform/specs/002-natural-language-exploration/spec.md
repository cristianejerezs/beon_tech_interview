# Feature Specification: Natural-Language Exploration and Grouped Analysis

**Feature Branch**: Not created; specifications are independent of branch names.

**Created**: 2026-10-17

**Status**: Draft - awaiting owner review; no implementation authorized by this document.

**Input**: User requested a combination of flexible interpretation, visible scope defaults, conversational clarification, bounded listings, and paraphrase evaluation, expanded to all ten proposed request types. Create two linked specifications first and implement only after review.

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

### Edge Cases

- Airport names/codes, case variations, everyday synonyms, punctuation, and minor spelling errors; ambiguous matches require clarification.
- "New York" means the available NYC-area origins when explicitly used as an origin region; other geographic meanings require clarification.
- "All" changes only the named restriction; an explicit new question does not inherit unrelated old scope.
- Empty results, unmatched reference names, missing measures, zero baseline, negative delays, tied ranks, and incomplete periods.
- An explicit date outside coverage must not be replaced silently with 2013 or described as zero observed activity.
- Month-to-month comparisons across different-length months disclose exposure; counts and per-day rates must not be conflated.
- Multiple requested analyses must not be silently reduced to one; explain the supported boundary and offer a choice.
- Source changes between pages require a visible refresh/restart of browsing, not a mixture of snapshots.
- Provider failures remain distinguishable from ambiguity and unsupported analysis; no fabricated answer or unapproved retry.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Support all ten request families in the request taxonomy below through ordinary English, including synonyms, short phrases, and question forms, without requiring internal identifiers.
- **FR-002**: Show an interpretation summary identifying request type, metric or listed entity, output grain, filters, period, population, and any applied defaults before or alongside every answer; allow correction without reconstructing the original question.
- **FR-003**: For new questions without period or airport restrictions, default to all available snapshot dates and observed origins. Distinguish full-snapshot scope from worldwide/live coverage. Do not require optional filters to obtain an answer.
- **FR-004**: Distinguish "each/per/by" grouping from "all combined" aggregation. Distinct counts must be recomputed at the requested grain, never obtained by summing overlapping distinct groups.
- **FR-005**: Resolve unambiguous airport names, airport codes, supported airline names, and everyday metric synonyms to available entities. Present candidate choices for ambiguous matches; disclose unresolved names and unsupported concepts.
- **FR-006**: Ask one focused clarification at a time only when materially different plausible interpretations remain. Offer labelled choices plus free text, preserve the request and already resolved scope, and never execute an unresolved request.
- **FR-007**: Make pending clarification cancellable and session-isolated. A new unrelated question replaces pending context; clarification responses may not modify a different request.
- **FR-008**: Follow-ups inherit only the active report's relevant scope. Explicit replacements and removals take precedence, including expanding from one airport to all origins; display retained and changed constraints.
- **FR-009**: Support grouped summaries with one or two compatible dimensions for flight count, distinct destination count, departure/arrival delay means, mean distance, distinct aircraft count, mean seats, and weather-context departure delay. Aircraft/reference/weather measures retain their defined grain, weighting, and match requirements. Explain unsupported combinations rather than silently dropping a dimension.
- **FR-010**: Unique entity lists must identify whether they represent observed origins, observed destinations, observed airlines, or an explicitly requested airport reference population. Provide codes and matched names where available, exact total entity counts, and unmatched-name disclosure.
- **FR-011**: Individual-flight browsing must show a deterministic, snapshot-bound order, unique source-row identity, active scope, exact matching count, and page position. Default to 100 rows per page, permit 25/50/100/500, and never load the full population into a single report page.
- **FR-012**: Listing exports are bounded to 10,000 rows per export, include stable ordering, scope/snapshot identification and exported/total counts, and must not claim completeness when partial. Require explicit confirmation for partial exports; allow further filtering instead. Exporting individual records must not transmit them to a model.
- **FR-013**: Aggregate/grouped results remain bounded to 500 displayed groups, with a default top ten for ranking requests and all groups up to the bound for explicit "each/all" requests. State total groups, displayed groups, ordering, omitted groups, and cutoff ties; no silent truncation.
- **FR-014**: Rankings and category comparisons must use consistent definitions, units, periods and weighting, show observation counts, preserve ties, distinguish highest/lowest direction, and avoid unsupported significance claims.
- **FR-015**: Historical trends support daily, calendar-week, and calendar-month grain, defaulting to month when unspecified. Weeks start Monday; labels state calendar convention. No observation must remain distinguishable from an observed zero.
- **FR-016**: Period changes compare the same metric and population over two explicitly identified periods, returning both values, absolute change (comparison minus baseline) and percentage change (100 times that difference divided by the baseline). A zero or unavailable baseline makes percentage change unavailable with an explanation; a negative baseline retains the signed formula with a warning that percentage direction is not an improvement/worsening judgment. An unqualified "previous period" uses an adjacent equal-length date window; "previous month/year" uses the preceding calendar period. Disclose partial coverage and unequal exposure.
- **FR-017**: Distributions initially support flight-level departure delay, arrival delay, and distance. Use reproducible equal-width bins starting at the largest whole multiple of the width not exceeding the observed minimum. Intervals include the left endpoint and exclude the right; extend the final interval beyond the maximum so every non-missing observation belongs to exactly one bin. Display exact boundaries, count missing observations separately, and reconcile non-missing bin counts to the filtered source population. Default widths are 15 minutes for delays and 250 miles for distance; all widths, including defaults, are allowed only with at most 100 bins. Explain a limit violation and offer coarser bins rather than silently changing width.
- **FR-018**: Relationships initially support any distinct pair of flight-level departure delay, arrival delay, and distance, using paired non-missing values from the same source rows. Disclose paired and excluded counts and units. Do not imply causation or add forecasting, significance testing, or fitted regression as part of this feature.
- **FR-019**: Analytical results must be based on validated source data and approved definitions, not model-generated numbers or executable instructions. Preserve existing identity, ownership, disclosure, budget, consent, and source-integrity protections; explain unsupported requests safely.
- **FR-020**: Save the resolved interpretation, definitions, result grain, scope, snapshot, completeness information and relevant clarification choices with the private report, under existing retention/ownership rules. Do not introduce indefinite conversational transcript retention.
- **FR-021**: Validate natural-language interpretation with a fixed, independently labelled corpus of at least 100 unambiguous requests, ten per request family, plus at least 20 ambiguous/unsupported requests. Include short wording, synonyms, names/codes, and follow-up expansion; do not evaluate by supplying expected analysis instructions in place of user wording.
- **FR-022**: Run the shared end-to-end acceptance cases below with the linked visual-report feature, checking the interpretation, numbers, visualization, saved report, and exports against the same scope. Document actual outcomes; do not substitute mocked provider results for live interpretation acceptance.

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
| E2E-06 | How do departure and arrival delays relate? | Paired same-flight observations and excluded count | Scatter or density view with sampling/binning disclosure |
| E2E-07 | Top ten destinations by number of flights | Ordered counts, total groups, tied cutoff and bound | Ranked chart with identical displayed values/table/export |
| E2E-08 | How many flights are there? | Overall count with disclosed full-data defaults | Summary card plus evidence; no fabricated comparison |

### Key Entities *(include if feature involves data)*

- **Exploration Request**: Original wording, request family, resolved entities, metric(s), output grain, scope, defaults, and requested bounds.
- **Clarification State**: Pending request, unresolved distinction, offered choices, resolved answers, and session ownership; temporary rather than a new permanent transcript.
- **Result Population**: Snapshot and filters defining records, entities or aggregate groups, including match/missingness rules.
- **Browse Page**: Stable snapshot/order, page size/position, visible source rows, exact total and completeness.
- **Analytical Definition**: Measure and unit, aggregation/weighting, period comparison rules, bins or paired variables, and material exclusions.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: At least 90 of the 100 unambiguous corpus requests produce the independently expected request family, population, metric, filters, grain and bounds, with at least eight of ten correct in every family.
- **SC-002**: All 20 ambiguous/unsupported cases either obtain the needed clarification before execution or clearly explain the unsupported boundary; none silently executes a materially different request.
- **SC-003**: Every generated numeric result in the acceptance corpus agrees with independently calculated expectations: exact integer/list identities and absolute tolerance 1e-12 for unrounded computed numeric values. A single numerical disagreement fails acceptance regardless of interpretation pass rate.
- **SC-004**: Unchanged-snapshot pagination across at least three consecutive pages has zero repeated/missing source identifiers relative to the expected ordered slice; export boundary tests at 9,999/10,000/10,001 records correctly disclose completeness.
- **SC-005**: All eight shared end-to-end cases pass interpretation-to-export agreement, including saved-report reopening, without scope or numeric drift.
- **SC-006**: In five real analyst sessions, at least four analysts complete an ordinary grouped question and a clarified exploration request without consulting a question-writing guide; record actual outcomes separately from automated results.

## Assumptions

- This feature extends [001-airport-analytics-platform](../001-airport-analytics-platform/spec.md); its protections, historical-data limitations, owner-approved session defaults and guarded development exception remain applicable.
- [003-visual-reporting](../003-visual-reporting/spec.md) is the linked presentation specification. This feature remains independently testable through correct answers and tables before charts are implemented; integrated release requires E2E-01 through E2E-08.
- English remains the supported language. Forecasting, live/global flight coverage, arbitrary calculations, statistical inference, maps, and unrestricted bulk extraction are out of scope.
- Default page sizes, export/group bounds, time grains, bin widths and initial numeric-pair coverage are proposed reviewable product choices, not claims about current capabilities.
- Date-only flight analysis follows recorded departure calendar dates. Intraday/time-zone analysis is outside this extension.
- No implementation, live-provider evaluation or real analyst study has been performed for this draft. Existing outstanding release gates are not waived.
