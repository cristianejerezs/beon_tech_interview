# Validation Quickstart: Automatic Visual Reporting

**Date**: 2026-10-18  
**Status**: Implementation in progress. Candidate Python dependencies and initial
fixtures are available; consult [actual execution records](./acceptance-results.md).
Commands naming subsequent visual modules become runnable after their tasks; this
guide is not evidence of a successful renderer/accessibility run.

## 1. Prerequisites and Safety

- The [35-item requirements checklist](./checklists/visual-reporting.md) is reviewed under
  explicit owner delegation; [35/35 criteria are satisfied](./acceptance-results.md#requirements-quality-review).
  This requirements-quality disposition is not implementation or release acceptance.
- Keep the workspace at
  `C:\Users\Cristian E Jerez S\Desktop\BEON\beon_tech_interview\interactive-airport-data-platform`.
- Use the supplied Python 3.12 environment at `..\beon\Scripts\python.exe`.
- Preserve the dirty worktree and local ledger; no reset, model calls, source edits or
  shared production database changes are required to validate visual transformations.
- Run tests against temporary synthetic/owned report fixtures. Mock provider dispatch;
  visual/subset/export interactions must make zero provider or analytical query calls.
- Provision approved local native/font resources only as part of implementation setup.
  Planning does not install or change dependencies. Follow [research.md](./research.md)
  and record exact package/runtime versions once the renderer spike has passed.

## 2. Early Renderer Feasibility Gate

After dependency-manifest changes, install the declared rendering dependencies in the
existing environment using the normal project package manager workflow. On Windows,
the Python WeasyPrint route additionally needs the official MSYS2 UCRT64 Pango runtime;
use an explicitly configured DLL directory if required. Do not assume `pip install`
alone makes tagged PDF export ready.

### Windows native provisioning and probe record

The missing `libgobject-2.0-0` was resolved through the official MSYS2 UCRT64 route.
MSYS2 20260611 and `mingw-w64-ucrt-x86_64-pango` are installed; WeasyPrint 68.1 reports
Pango 1.58.2 with the configured DLL directory. No runtime DLL was copied into the package.
For a fresh machine, the documented route is:

1. Have the operator approve/provision MSYS2 from its official distribution.
2. In the MSYS2 UCRT64 terminal run `pacman -S mingw-w64-ucrt-x86_64-pango`.
3. In the same PowerShell process as a renderer probe/application, if needed set
   `$env:WEASYPRINT_DLL_DIRECTORIES = 'C:\msys64\ucrt64\bin'`.
4. Re-run the probe and record native/library versions before the T027 spike.

The same-process DLL setting was needed for this runtime:

```powershell
$env:WEASYPRINT_DLL_DIRECTORIES = 'C:\msys64\ucrt64\bin'
& '..\beon\Scripts\python.exe' -m weasyprint --info
```

A one-page PDF generated and parsed successfully, but this is only a native smoke test,
not the T027 chart/tag/layout/accessibility feasibility pass. Keep the DLL variable set
when running the app/export worker. The earlier console probe displayed question marks
for non-ASCII characters with its default font; bundled-font glyph coverage still must
be validated. The documented provisioning commands below need not be rerun here.

Package setup is not authorization to assert full document accessibility:
The bundled unmodified Noto Sans Regular/Bold assets carry their OFL license and pinned
per-asset hashes. Do not substitute unreviewed commercial fonts; unsupported glyphs
must fail safely rather than render replacement characters.

Record:

```powershell
& '..\beon\Scripts\python.exe' -m weasyprint --info
& '..\beon\Scripts\python.exe' -m pip show streamlit altair vl-convert-python weasyprint pypdf
```

Generate a synthetic local report using the proposed PDF spike fixture. It must contain:

1. At least one real chart from embedded Vega-Lite data, not a placeholder.
2. Selectable text with long labels, duplicate names/codes and non-ASCII source names.
3. Headings, document language, figure descriptions and multi-page exact tables with
   row/column-header relationships and repeated visible headers.
4. A4 portrait/landscape behavior and labels/table text no smaller than 10 points.
5. No network requests or arbitrary file reads; missing font, DLL and glyph cases fail safely.

Inspect both the document structure and actual pages. Use pypdf structural checks for
tagged reading order/header relationships and a local PDF rasterizer for clipping
inspection. Per the owner's 2026-10-18 scope decision, manual PDF screen-reader review
is NOT ASSESSED and does not block implementation or release. Record versions and
what was checked. The tagged output option alone is not a pass, and no verified PDF
reader compatibility or PDF/UA certification is claimed.

Impose a technical timeout and a missing-renderer fault. In each case confirm the report
survives, no partial bytes become a download, job resources are cleaned and retry is explicit.
If the spike fails, stop dependent PDF integration and record the cause; do not downgrade
the visual export to an untagged table document.

## 3. Automated Validation (after implementation)

Proposed test module prefixes are defined in [plan.md](./plan.md); create tests before
their implementations. Run focused suites rather than an unnecessary full baseline:

```powershell
& '..\beon\Scripts\python.exe' -m pytest tests\unit -k visual -q
& '..\beon\Scripts\python.exe' -m pytest tests\integration -k visual -q
& '..\beon\Scripts\python.exe' -m pytest tests\browser -k visual -q
& '..\beon\Scripts\python.exe' -m pytest tests\accessibility -k visual -q
& '..\beon\Scripts\python.exe' -m pytest tests\performance -k visual -q
```

A no-tests-selected result is NOT a pass. Task generation must map these prefixes to
real collected tests and all spec tables/requirements. Existing closely related regression:

```powershell
& '..\beon\Scripts\python.exe' -m pytest `
  tests\integration\test_exploration_pair_metrics.py `
  tests\integration\test_exploration_airport_questions.py `
  tests\integration\test_exploration_summaries.py `
  tests\integration\test_exploration_composites.py `
  tests\integration\test_exploration_composite_storage.py `
  tests\browser\test_exploration_summary_ui.py -q
```

For files touched by implementation, run the existing Ruff lint/format checks and Pylance
diagnostics. Record commands, exact test counts and failures; do not reuse historical
pass counts as evidence of a new run.

## 4. Numerical and Shape Matrix

Freeze at least three independently checked examples for EACH of the ten default
presentation rows. Include normal, boundary and degenerate cases. Add weather as its
declared relationship bundle and all AQ-01..10 evidence forms.

| Scenario | Expected observation |
|----------|----------------------|
| Ungrouped count/mean, zero/negative/null | Summary or unavailable card; no fake trend |
| One finite category | One labelled bar/dot, not an ungrouped card |
| Ranked categories 20/21 | All 20 or first 20 with omissions and tied-cutoff notice |
| Unranked categories 21 | Explicit subset required; invalid 21-selection retains old view |
| Time series 8/9/20/21 | Lines / small multiples / small multiples / selection required |
| Two categorical dimensions 8x20 and 9-series or 21-primary | Grouped bars only within both thresholds, otherwise sparse heatmap |
| Time missing/null/zero and one known point | Gaps versus zero, isolated marker, no invented completeness |
| Weekdays and pooled month-of-year | Ordered categories, not temporal inference |
| Calendar month ranking | Ranked YYYY-MM categories, not a forced historical line |
| Exact distribution bins and zero bins | Original edges/inclusivity/counts; missingness separate |
| Two-period change with zero/unavailable baseline | Base units separate from relative percentage/reason |
| Pair counts 1/5,000/5,001 | Point / full scatter / complete saved density |
| Varying/one-constant/both-constant axes | 20x20 / 1x20 or 20x1 / 1x1; each varying axis has 20 equal-width intervals over its observed range, exact population and boundaries |
| All-null/zero/negative/constant measures | Correct no-data or permitted marks; no arbitrary volume suppression |
| Duplicate names, null identities and literal missing labels | Stable distinct identities and correct labels |
| Near-ties rounded to same display | Original order/ties from unrounded evidence |
| Weather unverified/verified, selected variable/airport | Overview, correct separate pairing, unit/provenance notices; bands only when verified |
| Temperature plot unavailable versus Pearson unavailable | Keep temperature with reason/explicit alternatives when no plot is possible; still plot valid pairs when only the coefficient is unavailable |
| Capacity/daily means and aircraft frequencies | Exact denominators, requested rounding, lower-bound/provisional and qualified-model labels |
| Listing/airport connections with numeric counts | Table; listing status takes precedence over incidental numbers |

Compare adapter/spec/CSV/PDF values against independent frozen expected evidence, not just
one production helper against itself. Integer counts/identities/order/boundaries match
exactly; finite independent decimals use `max(1e-9, 1e-12 * abs(expected))` tolerance.

## 5. Owned Controls and Saved Reopening

After implementation, start a dedicated local instance for the controlled browser checks
without assuming the already shared browser tab points to the current build:

```powershell
& '..\beon\Scripts\python.exe' -m streamlit run app.py
```

Use a free local port if the default is occupied; do not stop another chat's service.
Record the actual URL/build and verify readiness before collecting browser evidence.
Do not submit a hosted-model question without separate authorization.

Using temporary reports in AppTest and a controlled actual browser:

1. Apply compatible views/subsets and verify zero provider/query calls, unchanged analytic
   revision/evidence/scope, canonical order and explicit chart versus analytical bounds.
2. Save and reopen; check same view, selection, rule/fingerprint binding and labels.
3. Open the same owned report in two tabs; save a preference in tab A, then attempt a stale
   save in tab B. The latter must preserve the newer saved view and retain the draft.
   Reload/review/reapply is explicit and rechecks the version.
4. Attempt unknown IDs, incompatible views, wrong-owner access and deleted/pruned reports.
   No write, stale asset leak, success-shaped empty chart or automatic retry is allowed.
5. Reopen old V2 and V1 fixtures without current source availability. Valid historical
   evidence generates defaults and supports explicit compatible-view save/reopen with CAS;
   missing fields receive honest explanations, not backfills. Reading alone writes nothing.
   A missing snapshot shows a source-unavailable notice and disables historical paging/
   recalculation without suppressing valid saved results.
6. Prune/delete and confirm preferences/assets follow existing ownership/retention behavior.
   Shared copies must not grow raw pair/selection/graphic payloads.

## 6. PDF/CSV and Accessibility Matrix

Inspect at least twelve actual complete PDFs, not just text extraction:

1. Scalar card and one-category chart.
2. Ranked chart with 20 categories, tie/omission notices and long labels.
3. Time series with gaps/unknown coverage.
4. Eight-series labelled lines.
5. Nine-to-twenty-panel small multiples with shared scales.
6. Grouped bars with non-color cues.
7. Heatmap with absent/null/zero cells.
8. Distribution with exact intervals and missing counts.
9. Period change including unavailable relative change.
10. Full 5,000-pair scatter and exact paginated pair appendix.
11. Complete density including constant-axis cases and boundary table.
12. Weather overview/selected plot and four-section composite, including an acknowledged
    analytical failure; add separate examples if needed to cover both layouts fully.

For every example check chart/evidence/CSV agreement, selected subset, complete names/codes,
units/periods, glyphs/fonts, legends/grayscale, page breaks, minimum text sizes, no clipping
and no partial export. Chart-evidence CSV is distinct from full analytical/listing exports.

Check period-change text/value summaries in every permitted view and PDF. For each PDF
chart verify BOTH its visible description block and associated tagged figure alternative
against the web evidence-derived explanation; alt text alone is not sufficient.

Perform an actual web keyboard and screen-reader review with recorded browser, OS and
reader versions (for example Edge and NVDA). Test named disabled choices/reasons, focus
retention, controls, no traps and table relationships. PDF validation uses automated
heading/figure/header structure checks and actual page inspection. Manual PDF reader
navigation is NOT ASSESSED under the owner's scope decision. Do not mark actual web
reader behavior passed from AppTest, or PDF reader behavior passed from tags.
Document failures; PDF/UA certification is not asserted.

## 7. Performance, Privacy and Failure

Measure actual browser chart-ready and complete PDF build separately from model/query
durations for all twelve examples and boundary cases, cold and warm. Record environment,
package/native versions, family, evidence size, elapsed time and safe failure category.
No numerical product deadline exists; an imposed watchdog is a fault/recovery check.

Verify telemetry contains no question, label, number, scope/filter, raw spec, HTML, source
row, credential or analyst identifier. Explicitly test missing renderer/native library/font,
unsupported glyph, malformed tag/output, timeout and browser renderer faults. Preserve
report data and reject partial/stale downloads without provider calls.

## 8. Integrated Release and Human Gates

Run the authoritative [002 shared E2E-01..09](../002-natural-language-exploration/spec.md#shared-end-to-end-acceptance-cases)
and AQ-01..10 through natural-language interpretation, analysis, visual, saved reopening
and PDF/CSV. Mock interpretation tests do not establish live interpretation acceptance.
Any live run needs fresh authorization and normal disclosure/budget policy; no automatic
provider request is implied by this guide.

Independent corpus/reviewer/live gates still pending in 002 remain pending. Recruit five
real representative analysts, not implementers, for the specified category, time and
distribution/relationship tasks. Each task separately needs at least four of five correct
first unassisted answers covering BOTH an observation and a material limitation. Repeat
with five new participants after material fixes, retaining earlier results.
Each round includes at least one participant with aviation-domain experience and one
without; all have report/analysis experience. Record de-identified backgrounds alongside
outcomes without subgroup/population representativeness claims.

Create a dated acceptance record during actual execution with environment, method,
independent oracle, outcomes, failures and evidence references. Until then every matrix
entry in this guide is planned/not run. No automated suite substitutes for manual
accessibility, visual inspection, independent review or the real-participant gate.
