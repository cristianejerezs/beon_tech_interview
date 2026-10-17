# Interpretation and Interactive State Contract V2

Normative design for the existing Python/Streamlit interface; not a new HTTP API. Companion [domain model](../data-model.md) defines trusted fields.

## 1. Model output: IntentProposalV2

The implementation must generate a strict Draft 2020-12 schema/Pydantic representation from this contract and test each provider projection against it. Every object forbids additional properties. Provider subsets may make optional fields required-nullable, but may not broaden local semantics. No SQL, expression, computed answer, script or source-row payload is an allowed field.

| Field | Type / constraints |
|-------|--------------------|
| intent_version | Integer literal 2 |
| status | proposed / needs_clarification / unsupported / requires_selection |
| shared_scope | Proposed scope edits explicitly common to sections; empty object if none |
| sections | Ordered array, 0..4 section proposals; exactly 1..4 for proposed/needs_clarification/unsupported outcomes |
| selection_reason | Null except requires_selection, where a safe over-four explanation is required and no plan executes |

`requires_selection` preserves original wording and asks for selection or explicit partition. It never quietly reports only the first four. Model-chosen status/reasons are validated against the actual section proposals; application may still detect ambiguity or invalidity in a `proposed` result.

### Section proposal

Required keys: `position` (unique 1..4), `original_clause` (substring or faithful section wording; cannot add a requested task), `status` (proposed/needs_clarification/unsupported), `family` (domain enum/null), `operation_id` (closed enum/null), `measure_ids` (approved IDs), `population` (approved enum/null), `entity_mentions` (typed kind/text/code candidate), `scope_edits`, `grouping` (ordered dimension-role IDs, max two), `comparison`, `binning`, `pairing`, `order`, `bound`, `rounding`, `clarification`, `unsupported_reason`. Inapplicable keys are explicitly null/empty, not arbitrary dictionaries.

`scope_edits` contain only allowlisted field ID, action add/replace/remove and typed value. Dates use inclusive ISO date boundaries; null side represents open boundary resolved against the pinned snapshot, never a wall-clock default. Values are finite scalar/validated lists (max100 items) appropriate to each field; at most12 final predicates. Entity mentions resolve through the application, not provider authority.

`clarification` = unresolved field ID, focused question, 2..8 offered labelled semantic choices or an empty choice set for a genuinely open unresolved field; free text is always available. Each candidate is locally validated before display. `unsupported_reason` identifies a concept/combination, not an operational exception. Neither field may carry raw provider errors.

## 2. Closed analytical operations

Operation names below are V2 contract IDs; they do not assert these identifiers already exist in V1.

| Operation ID | Accepted measure(s) and form | Result / key compatibility |
|--------------|-----------------------------|----------------------------|
| aggregate | flight_count, distinct_destination_count, mean_departure_delay, mean_arrival_delay, mean_distance, distinct_aircraft_count, mean_seats, weather_context_departure_delay | Scalar/grouped/ranking/comparison/trend; approved measure dimensions from spec table |
| entity_list | observed_origins / observed_destinations / observed_airlines / airport_reference population | Stable entity codes/names and exact total, not a reference-plane/weather browser |
| flight_records | Approved flight listing columns and scope | Stable source ID order/pages, no groups |
| period_change | One approved aggregate measure | Same population/definition, two date scopes, values/absolute/relative change; no unapproved daily normalization |
| distribution | departure_delay / arrival_delay / distance | One variable, width/bounds; <=100 bins; no grouping that silently changes the distribution population |
| flight_relationship | Two distinct variables from departure_delay / arrival_delay / distance | Same-flight pairs, no Pearson coefficient/regression |
| daily_distinct_mean | distinct_destination_count | Overall, origin, weekday, origin+weekday; complete daily counts then equal-day means |
| departure_delay_total | positive_delay_minutes / net_delay_minutes | Common dimensions including year-month rank; net must be explicit |
| daily_capacity_mean | known_reference_seats | Carrier, optionally origin; per-flight sum->date->equal-day mean; common denominator |
| aircraft_frequency | distinct_tailnums / explicit_flight_frequency | Manufacturer or manufacturer-qualified model, optionally origin OR one date grain |
| weather_relationship | mean_departure_delay with fixed temp/wind_speed/precip/visib | Four-variable origin-hour panel + precipitation comparison, optionally origin breakdown |

`family` classifies the question's requested answer, not its internal algorithm. Ranking daily capacity is family ranking with operation daily_capacity_mean. The weather panel is one numeric_relationship section. Two periods, a pair of variables, supporting route/daily rows or its four weather variables do not independently consume section slots.

Grouped operations have at most two distinct compatible roles. A date bucket is one of date/week/month; carrier code and airline name share one role; manufacturer-qualified model is one identity. Unmatched references are disclosed rather than excluded except where a metric explicitly requires a match.

## 3. Defaults and explicit edits

- Fresh request: all observed origins/all available recorded dates, no unrelated inherited filters. Show finite observed bounds, not worldwide/current-data coverage.
- "List all airports" defaults to observed origins; explicit airport-reference wording selects airport_reference. Ambiguous "all flights" clarifies records versus overall count before execution.
- Ranking default top10; each/all selects up to500 in declared dimension order; topN>500 blocks correction. Limits affect selected outputs, never intermediate numerators/denominators.
- Trend defaults month; Monday-start weeks and ordered Monday-Sunday weekdays. Source calendar dates are not converted to local viewer time.
- Delay bins default15 minutes, distance250 miles. Validate anchored endpoints and <=100 bins using actual filtered min/max before executing the distribution itself; an excessive-bin result requires explicit proposed-width acceptance.
- Scope-only prerequisite queries (e.g. min/max for bin eligibility, coverage/entity checks) cannot create a report result. No section's main analytical execution occurs while any section remains unresolved.
- Unqualified rounded daily mean uses whole-number half-up; exact computed evidence stays unrounded.
- Calendar-day denominators are requested by default for approved daily means. No verified days produces unavailable evidence and offers an explicit observed-operating-day analytical revision; declining preserves the requested unavailable result.
- Follow-ups inherit compatible family/measure/filter/date/group/order/bound fields from an explicitly targeted section; list pages reset. Remove only named restrictions for "all origins", "all destinations", "all dates". Family changes invalidate incompatible fields and surface ambiguity.
- Names/codes/aliases resolve by the policy in research/data model; single spelling suggestions still require confirmation. "New York" only means EWR/JFK/LGA when explicitly used as an origin region.

## 4. User events

| Event | Required payload / behavior |
|-------|-----------------------------|
| submit_question | Trim/validate wording, fresh request or explicit follow-up target/all-sections intent; supersede old pending state |
| answer_clarification | Current session/request/revision/section/question IDs and choice ID or free text; reject stale first |
| apply_interpretation_edit | Typed editable fields, revision and section target; new analytical revision only on Apply, Cancel preserves report |
| remove_section | Current identity/revision and explicit confirmation; disclose removed request, then revalidate all active sections |
| choose_partition | Explicit section grouping <=4/report; never auto-run additional reports or model calls |
| retry_provider | Explicit user action, current revision and existing provider/tracing/disclosure/budget checks |
| change_page | Valid bound page state, page size/order/scope/snapshot/context; no model request |
| refresh_snapshot | Explicit acknowledgement of old/new source/context, reset pages, revalidate scope |
| acknowledge_incomplete | Exact report revision and failed-section identities; not a waiver for technical export failure |
| export_selection | Scoped section allocations/confirmation token; no model request |

All events enforce current owner/session. Session state is per browser session; callbacks use current widget values and clear/replace stale choice IDs before rendering. Session end/sign-out cancels drafts. No extra time-based expiration or transcript retention is introduced.

## 5. Provider and operational gates

One initial submitted request normally invokes one structured translation call; a free-text clarification requiring translation is one separately authorized call. Locally resolved choice/typed correction need not call a model. No call per section solely to make a four-section report; no hidden schema-repair/decomposition retry. If a provider cannot meet the V2 contract within configured limits, report invalid/unavailable output or an explicitly disclosed split option.

Before each call recheck disclosure, provider settings, bounded tokens/price, persisted reservation/free quota and tracing cap. Settle exactly once. A possibly accepted uncertain paid call continues to block until reconciliation across restart/month boundaries; an explicit retry button does not bypass it.

Typed failures: ambiguous, unsupported, invalid_scope, provider_unavailable, invalid_provider_output, source_unavailable, execution_failed, disclosure_refused, budget_refused. Preserve wording/choices in session, emit safe category/ID/duration only. No automatic retry/fallback, silent broadening, synthesized numeric answer or operational error relabelled "unsupported wording".
