# Contract: Presentation Controls, Ownership and Exports

**Version**: 003.1  
**Related**: [Visual Evidence](./visual-evidence.md), [data model](../data-model.md).

**Owner scope amendment (2026-10-18)**: Manual PDF screen-reader/header-navigation
assessment is NOT ASSESSED and is not an implementation or release gate. Keep visual
PDFs, automated tagged-structure/header-relationship/figure-alternative checks, visible
evidence descriptions, selectable text and actual page-quality inspection. Do not claim
verified PDF reader compatibility or PDF/UA certification. All actual web keyboard and
screen-reader requirements remain in scope.

## 1. Browser Interaction

For each successful/empty section, use this reading and focus sequence:

1. Section title, analytical interpretation and findings.
2. View selector and relevant category/series or airport/variable controls.
3. Chart name, adjacent explanation, rendered chart and selection/coverage notices.
4. Exact plotted evidence and separately labelled broader analytical/supporting evidence.
5. Explicit save/export actions and status.

Weather places its four-coefficient overview/findings before the selected variable plot.
Keep default temperature selected with an explained unavailable plot if needed; never
silently switch variables. An unavailable Pearson coefficient alone does not invalidate
otherwise valid paired plotting evidence. Period changes retain a visible text/value
summary of absolute/relative change in every compatible view and PDF, not a separate chart.
Failed analytical sections retain their failure notices and have no chart controls.
Summary cards are meaningful scalar views, not chart failures.

Use native Streamlit controls; no custom styling is required. Compatible view actions
are named and keyboard operable; incompatible actions are disabled with a visible reason
associated through accessible help/description. Use a small bounded group of disabled
buttons/controls if the native selector cannot express per-option disabled reasons.
Do not offer unexplained dead options or an arbitrary user chart grammar.

Subset controls have stable code-plus-name options, current/available counts, Apply, Reset
and Table actions. Draft edits do not alter a saved/applied chart. Validate all identities/
limits on Apply; invalid input preserves the prior applied view and explains the failure.
Selection changes are presentation-only; aggregation, grouping, binning, measures, units
and time grain must use the existing explicit analytical-refinement workflow instead.

View/subset/airport/variable actions invoke no provider, incur no provider reservation and
perform no source SQL. Do not route them through question submission or analytical generation.
Cache only if necessary and bounded; any cache key includes owner, report, section,
evidence fingerprint and applied preference version. Never serve another owner's graphic.

## 2. Preference Save and Conflict

Reuse the existing repository update boundary:

```text
owner identity + report ID + expected preference version + full section preference map
    -> owner check -> decode saved report -> compare version
    -> validate against saved evidence -> transaction/CAS -> increment preference version
```

Do not increment analytical revision or change evidence, creation time, retention order,
question, incomplete acknowledgement or other sections' applied preferences.

| Condition | Required result |
|-----------|-----------------|
| Owner, current version, compatible selections | Persist typed preferences; increment preference counter once |
| Non-owner, removed or pruned report | Existing safe authorization failure; no write or information leak |
| Stale expected version / concurrent CAS failure | Conflict notice; retain newer saved view and local draft |
| Unknown section, stale evidence fingerprint, incompatible family/limit | Explicit preference error; prior valid view retained |
| Reapply after conflict | Analyst first reviews latest state and explicitly reapplies; new version checked again |
| Reset | Return deterministic defaults locally; persist only through explicit save |

No automatic last-write-wins, merge or retry. Normalizing an old preference on read does
not persist a migration. Unsupported rule versions require an explained compatible
replacement, not silent reinterpretation of selection tokens.

Preferences and generated assets inherit report ownership and existing ten-report pruning/
deletion. Do not expand consented shared FAQ/example content to include full charts or raw
pair evidence. Reuse existing sharing projection and owner checks on downloads.

## 3. Accessible Web Presentation

- Programmatic names and visible adjacent explanations for every chart and table.
- Exact plotted values accessible without hover/color and without visiting each graphical
  mark; provide labelled native table navigation with row/column relationships. For large
  pair tables, accessible paging may display bounded chunks while preserving/exporting all
  plotted evidence and its complete count.
- Static labelled legends and non-color series encodings. Missing cells have distinct
  text/markers, not zero coloring.
- Visible unobscured focus, logical order, no keyboard trap; applying a view preserves
  focus at the initiating control/status. Announce concise result/subset changes, not the
  entire evidence table.
- Native behavior is verified in a real browser and reader; AppTest alone cannot establish
  these properties. If a native widget fails, correct or replace it with an accessible
  native alternative; do not waive FR-018.

## 4. Export Binding

Export receives an owner-checked saved report and a validated effective applied presentation
bound to report/section, analytical revision, preference version, evidence fingerprint and
rule version. Pending drafts are not exported. Re-read ownership/version before preparing
download bytes. If an export was prepared for an older preference revision, invalidate the
download when the UI observes that revision changed and require explicit regeneration.
Do not describe an older graphic as the current selection.

A deliberate table view is a valid table export, not a hidden fallback. Selection-required
states must ask for a valid subset or explicit table view before promising a chart.
No-data/missing historical evidence exports retain their explicit explanation and available
table, not a fabricated chart.

### PDF

- Build one complete local document for all report sections. Acknowledged analytical
  incompleteness preserves failed-section notices; a technical renderer failure returns
  no PDF at all.
- Graphical views include actual SVG graphics, legends/labels/units, descriptions, exact
  plotted rows/cells/bins, scope, definitions, coverage, subset and analytical truncation.
  Weather includes its overview, findings and selected airport/variable plot; unverified
  unit status and omitted precipitation comparison are explicit.
- Pairs through 5,000 require all plotted pair rows in the PDF appendix. Density requires
  exact full-grid edges/counts and inclusivity; distribution requires all plotted bins.
  Do not substitute the four weather coefficient rows for selected pair/density evidence.
- Retain bounded daily support, routes and their omitted counts under 002; they do not
  replace the exact plotted appendix. Listing table exports remain previews unless the
  explicit 002 full-listing action is used.
- A4 portrait, then landscape or paginated panels/tables if needed; minimum 10-point text.
  Repeat table headers, preserve comparable scales, wrap names or use linked full-name
  keys. No clipped legends, chart scaling below legibility or silent name truncation.
- Semantic HTML supplies headings, captions, figure alt descriptions, table row/column
  headers and reading order. The actual PDF must retain them and selectable Unicode text,
  embedded fonts and document language. A metadata flag alone is insufficient.
- Include a visible chart explanation AND associated tagged figure alternative derived
  from the same selected Visual Evidence as the web description; neither is optional.
- Preflight text against approved font assets and validate chart SVG text/glyph output.
  Missing glyphs/fonts/native libraries, malformed output, timeout or incomplete tags are
  explicit safe export failures. Do not silently call old ReportLab to make a partial or
  untagged "visual" PDF.
- Only internally generated markup/styles and job-owned local assets. Deny network,
  arbitrary file resources, scripts and attachments; source labels are escaped data.
  A worker and job-scoped temporary storage are cleaned on success, error and timeout.
- Expose bytes only after full composition, required-section/graphic/evidence checks and
  structural validation. Runtime structural checks do not replace human accessibility
  release review and do not assert PDF/UA certification.

### CSV / bundle

Preserve existing analytical CSV and listing export contracts. Add a distinct, clearly
labelled **chart evidence** export rather than silently changing the meaning of the current
full-result CSV. For composites use one bounded bundle with an explicit manifest:

| Metadata | Required semantics |
|----------|--------------------|
| Report/section/snapshot/context/revision | Same saved evidence as the chart |
| Preference/evidence/rule version and fingerprint | Reproduce effective selected presentation |
| Shape, view, variable/airport and axis units | Identify actual plotted population |
| Selected/returned/available and omissions/ties | Visual subset separate from analytical bound |
| Numeric/coverage/missingness status | Null versus empty string versus zero preserved |
| Density/distribution boundaries | Exact edge indices, inclusion flags and counts |
| Unit/denominator/provisional flags | Preserve unverified weather and capacity/daily definitions |

Export raw numeric precision, not display rounding. Reuse existing UTF-8, null metadata
and spreadsheet-formula escaping conventions for source text. CSV never contains a chart
image or interpolated/rebinned values. Empty exports carry metadata/reasons, not fake rows.
Chart pair evidence bounds are not the 10,000-row flight-list allowance: each selected
pair population follows its 5,000/full-density contract. Full-listing exports still obey
002's combined row cap and are not recomputed just to render a chart.

## 5. Failure and Timing Semantics

| Category | Browser behavior | PDF/download behavior |
|----------|------------------|-----------------------|
| Missing/invalid evidence | Explain issue, retain available table, offer refinement | Explain unavailable shape; never invent chart |
| Over-limit without selection | Selection required or explicit table | No promised chart until a valid applied selection |
| Chart renderer failure | Error plus retained report/evidence and explicit retry | Do not reuse stale/wrong chart bytes |
| PDF dependency/font/glyph/layout/tag error | Preserve browser view and actionable safe error | No partial download |
| Technical watchdog timeout | Report remains; explicit retry | Terminate owned job, clean resources, no file |
| Preference conflict | Retain draft, reload/reapply options | Require current validated selection |

Errors use repository-standard typed exceptions and safe messages; log no raw document,
Vega spec, values, labels, filters, questions, user identifiers or secrets. Do not convert
exceptions into successful empty graphics or silently retry.

Measure server visual preparation and complete PDF build separately from model/query time.
Measure browser-ready timing in a browser harness from view action through actual chart
readiness, not by relabelling server time. Record cold/warm condition, environment/version,
shape/family, bounded evidence size, elapsed time and safe failure code. Never emit report
content in telemetry. No numerical product deadline or job-queue requirement is introduced.

## 6. Legacy/Rollout

Introduce an explicit 003 visual-reporting capability gate for rollout; keep it independent
of V2 analytical interpretation. If disabled, clearly identify the existing table/legacy
export and do not claim visual or tagged-PDF support. The gate is not a substitute for
acceptance and must not hide a runtime failure after a visual export was requested.

V1 reports stay readable through their conservative adapter/dispatch and gain additive
empty preference/version defaults. Compatible historical views save/reopen through the same
owner/CAS path using presentation ID `legacy`, never by converting their analysis to V2.
V2 historical reports use original evidence and deterministic defaults without source reload. Documentation
and UI must distinguish old legacy PDF from new validated visual export during transition.

## 7. Acceptance

Test owner isolation, version conflicts, unchanged evidence, incompatible/over-limit draft
preservation, model/query call counters, old report decoding and retention. Test composite
success/valid-empty/acknowledged-failed sections; one technical failure produces no partial
document. Inspect actual graphic output, automated PDF structure/header relationships,
full pair evidence, fonts/glyphs, page breaks and grayscale. Perform actual screen-reader
checks for the web; manual PDF reader behavior is NOT ASSESSED. Keep failures and unexecuted gates
in dated records, never promote a planned example to a pass.
