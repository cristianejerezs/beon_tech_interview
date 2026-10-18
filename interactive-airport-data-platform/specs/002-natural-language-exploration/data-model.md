# Domain Model: Natural-Language Exploration V2

Domain contract. Foundational request/interpretation/result/report types are implemented;
browsing/export-selection, detailed coverage/evaluation types and lifecycle integration remain
scheduled in their story tasks. All serialized objects reject unknown properties. IDs and hashes
are opaque identifiers, never user-supplied SQL or filesystem paths. UTC timestamps apply to
application events only; flight calendar dates retain their recorded meaning.

## 1. Trust layers and relationships

```text
Session -> RequestDraft -> 1..4 RequestedSection -> ResolvedInterpretation
                                  |                        |
                            ClarificationChoice      Snapshot + Coverage
                                                           |
                                                  SectionOutcome + Evidence
                                                           |
                        Owned CompositeReport <-------------+
                                  |
                         SectionPresentationPreference (003)
```

The model supplies only `IntentProposalV2`; application-owned types below must not be accepted as provider output. A ready proposal is not an executable plan until catalog, entity, scope, coverage and consistency validation completes.

## 2. RequestDraft (session-only)

| Field | Type / rule |
|-------|-------------|
| request_id, session_binding | Application-generated random IDs; session binding never placed in prompts |
| revision | Positive integer; increments for new submitted interpretation/correction, never reused |
| original_question | Trimmed string, 1..2,000 Unicode code points; original submitted wording retained |
| state | unresolved / clarification_pending / guided_correction / resolved / executing / completed / incomplete / failed / cancelled / superseded |
| sections | 1..4 stable requested identities in original order after valid decomposition |
| shared_scope | Explicit common scope only; per-field provenance and section overrides |
| removed_sections | Explicitly removed identities/labels and reason category; preserves acknowledged omission without an answer |
| snapshot_binding | Validated data hash and semantic context hash, or null before binding |
| last_failure | Safe category/code; no provider body or credential content |

An oversized undecomposed request remains unresolved with its original text and an over-limit notice until the analyst selects a valid subset or explicitly confirms a partition. It is not a four-section report with silently dropped instructions.

### RequestedSection

`section_id` (app-assigned), `position`, `original_clause`, `status`, candidate/resolved interpretation, `answered_turns` (0..3), unresolved field, offered choices and resolved semantic choices. Raw clarification text stays only in the draft and is not a retained transcript.

An answer event carries session binding, request ID/revision, section ID, current question/choice ID and answer. All must match before consuming a turn or invoking a provider. Free-text answer validation matches question length/Unicode rules. A failed provider dispatch preserves state and does not consume the answered turn; a validated but still ambiguous answer does.

### Transitions

| From | Event | To / invariant |
|------|-------|----------------|
| unresolved | All sections validate | resolved; no SQL run during resolution |
| unresolved | Material ambiguity | clarification_pending for first unresolved section |
| clarification_pending | Valid answer, still ambiguous | pending if turns<3; guided_correction at 3 |
| guided_correction | Apply typed field correction | unresolved then revalidate; no fourth free-text turn |
| any editable state | Cancel / fresh unrelated question | cancelled / superseded; invalidate all pending answer IDs |
| resolved | All gates/snapshot still valid | executing; one common immutable snapshot |
| executing | Every active section completed or valid empty | completed |
| executing | At least one success/valid empty and one runtime failure | incomplete; no auto-save/export before acknowledgement |
| executing | All active sections fail | failed; not saveable as a successful report |
| any pre-execution state | Provider/source/disclosure/budget fault | failed; preserve choices and explicit permitted retry only |

Explicit analytical retry/correction creates a new revision and revalidates all affected scope. Runtime successes remain visible in the old incomplete draft; do not silently merge results computed on different snapshots or stitch unrelated retry runs.

## 3. ResolvedInterpretation (trusted)

| Field | Type / rule |
|-------|-------------|
| interpretation_version | Literal `2` |
| request_id, revision, section_id, original_clause | Identity and submitted section wording |
| family | overall_summary / grouped_summary / unique_entity_list / individual_records / ranking / category_comparison / historical_trend / period_change / distribution / numeric_relationship |
| operation_id, measure_ids | Closed catalog IDs; compatibility matrix in [interpretation contract](contracts/interpretation.md) |
| entities | Kind, code, reference label/null, observed/reference-only status, resolution method, alias-map version |
| population | flights / observed_origins / observed_destinations / observed_airlines / airport_reference |
| filters | Typed catalog filters; max 12, no contradictions; normalized values validated by field |
| grouping | Ordered distinct roles, max two; no redundant carrier/name or simultaneous date grains |
| date_scope | Requested inclusive start/end or all-snapshot; resolved observed bounds separately |
| grain, calendar | scalar / flight / entity / category / date / week / month / weekday / bin / flight_pair / origin_hour; recorded-date calendar, Monday week start |
| denominator_basis | not_applicable / verified_calendar_days / observed_operating_days; alternative requires explicit selected choice |
| definition | Unit, numerator/denominator, weighting, non-additivity and match/exclusion rules from catalog, never free model prose |
| comparison, binning, pairing | Operation-specific validated options or null |
| order, selection | Typed keys/direction/tie policy and group bound/page defaults; stable source/code keys appended locally |
| display_rounding | null or explicit decimal places 0..12 and half_up; unspecified rounded daily mean means 0; no effect on stored calculation |
| field_provenance | Each material field -> explicit / correction / clarification / inherited / default, source revision and safe semantic choice |
| snapshot_id, context_id | Data content hash; context hashes coverage declaration status/content, unit/catalog/alias/rule versions |

Context ID prevents changed coverage/definitions from altering continued analyses under the same data hash. Missing declaration is a stable explicit context state, not verified coverage. Older saved interpretation remains immutable even if context later changes.

## 4. CoverageDeclaration and CalendarEligibility

Declaration fields/shape: [coverage.schema.json](contracts/coverage.schema.json). The application's configured coverage file is local only, never fetched from model-supplied URLs. Documentation references identify reviewed provenance; they are not executable fetch instructions.

Semantic validation additionally requires:

- Exact complete snapshot hash, known origin codes, valid inclusive date bounds, compatible/nonoverlapping coverage intervals and gaps inside coverage.
- Documentation that supports completeness for the declared transformed subset, not merely upstream dataset identity; recorded checks and reviewer identity/version.
- Validation against loaded source/provenance; a valid JSON `passed` value is an assertion to verify, not proof.
- Scope union requirements: an all-origin combined date is verified only when every selected origin is covered without a gap; per-origin results validate that origin's scope independently. Capacity comparisons share the applicable date set across airlines within each comparison population; never choose each airline's own denominator.
- Unknown dates and known gaps remain unknown for complete-day denominators. Observed rows do not upgrade their status. A stale/malformed/conflicting declaration emits a safe visible warning and contributes no unsupported verified days.

`CalendarEligibility` stores requested, verified, unknown, observed and eligible counts, inclusive bounds, per-weekday counts, coverage version/hash/status, denominator basis and partial flags. Supporting daily rows share one separate 500-row pool per section across all categories/collections, ordered by date then stable category codes under the [evidence-bound table](spec.md#evidence-bound-table); counts/means use the complete eligible date set.

## 5. AnalyticalResult union

Every variant has `result_version=2`, section identity, interpretation/context reference, definition/units, scope/coverage, missingness, exact counts, unrounded finite values or null-with-reason, and selection/order completeness.

| Variant | Additional evidence |
|---------|---------------------|
| scalar | Value, numerator/denominator where relevant, supporting route summary when needed |
| grouped | Typed category/code identities and ordered measures; exact total/selected/omitted groups, ties, sample sizes; aggregate groups include scoped_count and missing_count, with sample_size + missing_count = scoped_count |
| listing | Stable identity columns, exact total, BrowsePage and explicit population kind |
| period_change | Baseline/comparison scope, values/counts/day exposure, absolute/relative change and unavailable/warning flags |
| distribution | Variable/unit, anchored width, ordered lower/upper/count bins, missing/known counts and exact reconciliation |
| relationship | Flight pair variables/units/grain; paired/missing partition; complete pairs or full density evidence |
| daily_mean | Unrounded numerator/eligible-day denominator, bounded daily evidence, weekday/airline categories, known/unknown/complete-day counts |
| weather_panel | Four variable summaries (and optional origin groups), precipitation-band descriptive comparison, origin-hour pairing/exclusions and pair/density evidence per variable |

Numerical absence is typed: no_matching_records / no_known_values / no_verified_days / insufficient_pairs / constant_axis / unknown_capacity. Nulls may be intentional components of a completed result; unavailable components are not silently zero or operational errors. Nonfinite source numbers are invalid data, not missing.

`SectionOutcome` = completed(result) / valid_empty(evidence) / failed(safe category/message). Unsupported/ambiguous/invalid proposals do not reach execution. All-failed requests produce no successful report object.

## 6. BrowsePage and export selection

`BrowsePage` fields: snapshot/context identity, scope/order hash, page_size in {25,50,100,500}, page_index (1-based), total_rows, total_pages (0 when empty), first/last identity and bounded rows. A continuation is application-generated validated state bound to owner/session/request/section, not an arbitrary client SQL cursor. Stable ordering supports deterministic offset pages on immutable loaded tables; SQL count and page share identical predicates.

Refresh source fingerprints before continuation/recomputation. A changed source/context invalidates continuation with an explicit restart action; do not substitute cached old or newly loaded rows. Scope/order/page-size changes reset page one; out-of-range page resets with a notice.

`ExportSelection` stores selected sections, kind, requested allocation per listing section, exact exported/total counts, partial confirmation bound to snapshot/context/revision/allocation, and acknowledgement of any incomplete report. Combined listing rows<=10,000; aggregate selected rows<=500/section independently. Scope changes invalidate confirmations.

## 7. CompositeReportV2 and compatibility

| Field | Type / rule |
|-------|-------------|
| report_version | Literal `2`; absent discriminator means legacy V1, never guessed from rows |
| report_id, analyst_id, session_id | Existing owner/session identities; one parent retention slot |
| parent_report_id | Optional previous report ID; link only, never ownership inheritance |
| question, created_at | Original wording and UTC report-result creation time |
| snapshot_id, context_id, versions | Common snapshot and semantic versions; unit/coverage provenance stored |
| shared_scope, removed_sections | Explicit shared fields and acknowledged removals |
| sections | 1..4 ordered requested section identities, saved interpretations, definitions, bounded evidence and outcomes |
| completeness | complete / incomplete; empty valid sections count as completed |
| incomplete_acknowledgement | Required for incomplete save/export; analyst/session, report revision, exact failed-section IDs and acknowledgement UTC time |
| presentation_preferences | Per-section validated 003 preferences, preference_version; no analytical edits |

Never synthesize a top-level V1 first-section metric/plan/rows proxy for a V2 report. Consumers dispatch by version and use common label/section adapters. Older reports lack evidence not saved originally: preserve that limitation rather than inferring retrospective completeness.

Ownership, deletion and ten-parent pruning cascade through embedded sections/preferences. Existing shared artifacts remain under their consent/lifecycle rules; do not invent a report-delete cascade over historically separately retained shared artifacts without the retention owner's policy.

## 8. Evaluation records

`CorpusCase` stores synthetic text, version, family and independent gold interpretation/outcome/result references; AQ/composite cases have separate identities. `ReviewRecord` stores independent labels, agreement/disputes/adjudication and freeze provenance. `EvaluationRun` stores corpus/source/context/compiler/schema/catalog/alias versions, provider/model/settings, timing environment, attempted case IDs, status/comparison categories and exact absolute errors. No raw provider bodies or private questions/filters in operational telemetry. Synthetic corpus content remains in explicitly managed fixtures, not routine logs.
