# Automatic Visual Reporting: Execution Record

## 2026-10-18: Live Quality Recovery and Local V2 Test Exports

The owner subsequently authorized paced real-provider quality tests, fixes,
local V2 activation and chart-bearing test PDFs for all ten airport questions.
This later authorization supersedes the implementation-entry restriction below
only for those explicitly requested actions. Historical failed runs remain
preserved; this is not a retrospective first-attempt pass.

- Local environment enables `AIRPORT_VISUAL_REPORTING_ENABLED=true`; shared
  code/example defaults remain off.
- Selected real Groq 20B/120B saved answers now match independent calculations
  for all ten questions, including all 16 distinct-flight-number airline counts
  and all 16 observed-day seat-capacity averages.
- Fixed explicit observed-day contract/provenance, browser Arrow projection,
  temporal identities, density-compatible defaults, applied weather selection,
  origin-hour density labeling and the saved daily-mean scalar summary.
- **189 targeted tests passed**, plus Ruff checks and `git diff --check`.
  Actual browser checks confirmed the expected chart marks for the eight
  graphical questions; daily-mean scalar AQ-02 displays 81.
- Ten separate V2 test PDFs were exported. Two scalar questions appropriately
  have no chart; the other eight have charts. First/graphical pages were
  raster-inspected and initial layout defects corrected. Painted text is
  at least 9.999756 pt, within the 10 pt threshold's 0.001 pt serialization
  allowance; selectable evidence and tagged structure checks passed.

Detailed evidence, limitations, source-run mapping and downloadable index:
[post-fix quality report](../../reports/quality-test-20261018/POST-FIX-QUALITY-REPORT.md).

**Scope boundary:** these PDFs are separate local test-workflow exports using
the saved-evidence chart builder; the application's PDF download remains the
legacy exporter. This does not complete production visual-PDF integration,
all 66 implementation tasks, or the release/participant/performance gates.
Manual PDF screen-reader compatibility remains **NOT ASSESSED
(owner-excluded)**. Tagged structure is not a PDF/UA or reader-compatibility
certification. Not every long evidence-appendix page was manually inspected.

## 2026-10-18: Implementation Entry

The owner explicitly requested that the assistant review the custom requirements checklist,
mark satisfied criteria, then proceed with implementation. This is requirements review
authorization, not a waiver of any numerical, visual, accessibility, independent/live or
human-study acceptance gate. No live provider call or native system installation is authorized.

### Requirements-Quality Review

[Custom checklist](./checklists/visual-reporting.md): **0/35 -> 35/35 checked**.
[Built-in checklist](./checklists/requirements.md): **16/16**, unchanged.

| Criteria | Evidence reviewed | Disposition |
|----------|-------------------|-------------|
| CHK001..005 | FR-001..004/009/014..017/024, logical evidence table; data-model historical compatibility; presentation/export contract sections 1/4 | Complete shape, evidence, control and historical contracts |
| CHK006..011 | Default/precedence rules, FR-011/022/029/030, formatting precedence and weather clarification | Temporal/categorical roles, counts, Pearson axes/defaults, summary and rounding are explicit |
| CHK012..016 | Shared-contract traceability table, current 002 E2E/AQ/FR/SC definitions, model/version and export contracts | Nine E2Es, ten AQs, tolerance, retention, composites and unit policy agree |
| CHK017..020 | SC-001..009, twelve-PDF guide, mixed-background SC-007, separate browser/PDF timing | Measurable numerical/visual/manual/participant obligations, no invented SLA |
| CHK021..024 | FR-014/015/019/023/031, resolution states, lifecycle and export failure tables | Primary, alternate, conflict, exception, recovery and ownership scenarios specified |
| CHK025..029 | Numeric eligibility, inclusive thresholds, missingness and complete-pair/grid contracts | Degenerate values, labels, unknown coverage, exact limits and interval rules explicit |
| CHK030..033 | FR-018/019/023, accessible explanations, PDF presentation, resource policy | Web controls, dual PDF descriptions, 10-point limits, Unicode, local-only and explicit failure requirements |
| CHK034..035 | Dependency table, pending release matrix, clarifications, plan, corrected task dependencies/checkpoint selectors | Assumptions and blockers declared; no remaining high-impact requirements conflict identified |

Checkbox approval establishes the quality of the written requirements only. It does not
establish that any chart, native renderer, tagged PDF or reader behavior has passed.
The four analysis findings were checked against the corrected dependency/checkpoint text.

### Setup Inspection

- Workspace remains the approved application directory; existing dirty worktree preserved.
- The parent repository's Python ignore rules cover bytecode, virtual environments,
  caches, environment secrets and application runtime storage; added the missing `build/`
  rule after validating the distribution wheel. No redundant local
  ignore file is needed. No Docker/Node/Terraform/Helm project setup is present.
- Expected MSYS2 UCRT64 Pango DLL is absent at `C:\msys64\ucrt64\bin\libpango-1.0-0.dll`.
  This probe is not proof that no alternative Pango installation exists. Native provisioning
  and an actual successful renderer spike remain unverified.

### Implementation and Release Status

**T001..T012 complete; 12/66 checked, 54 pending.**

| Tasks | Persistent result | Actual verification |
|-------|-------------------|---------------------|
| T001 | Explicit delegated checklist review and disposition | 35/35 custom, 16/16 built-in criteria checked |
| T002 | 33 synthetic examples (three per ten defaults plus weather), deterministic threshold/degenerate recipes, independent expectations and frozen V1/V2 payloads | Standard-library rational/count/bin/Pearson oracle tests; no chart/analytical helper used to derive expectations |
| T003 | Direct renderer/font dependencies and Streamlit 1.66 floor; original Python and legacy dependencies retained | Candidate versions recorded in research; installation and `pip check` passed |
| T004 | Unmodified pinned Noto Sans Regular/Bold, embedded copyright/OFL notices, per-asset provenance/hash and packaged license | Static/embedding/glyph/hash tests pass; distribution wheel contains all four required font resources |
| T005..T009 | Closed immutable evidence/dimension/selection/resolution models, canonical identities and analytical SHA-256 | Exact integer/finite numeric, immutability, version/role/state, identity collision, inclusive-boundary and fingerprint tests |
| T010 | Source-free shape projection over all eight existing result types, fixed role/classification precedence and conservative V1 mapping | Thirteen offline generated cases preserve every serialized analytical value; provider/executor/catalogue re-entry patched to fail |
| T011 | Backward-compatible optional verified bucket intervals saved only during new temporal generation | Old/new reports, exact binding, overlap rejection, 500/501 overflow and no-write-on-read tests pass |
| T012 | Typed evidence/render/export errors and explicit default-off rollout setting | Flag validation, import isolation and existing configuration/history tests pass |

Nested evidence is stored as immutable canonical JSON with detached, existing typed-union
decoding, rather than exposing mutable Pydantic dictionaries inside a nominally frozen
wrapper. This implementation choice is documented in the data model.

At this checkpoint the rollout setting was a foundation capability only. The later US1
increment below wires its default-off gate into saved and unsaved report presentation.

### Executed Automation

Task-plan interpreter: `..\beon\Scripts\python.exe` (Python 3.12).

```powershell
& '..\beon\Scripts\python.exe' -m pytest `
  tests\unit\test_visual_evidence.py `
  tests\integration\test_visual_historical_evidence.py `
  tests\unit\test_visual_fixture_oracles.py `
  tests\unit\test_visual_font_assets.py `
  tests\unit\test_config.py `
  tests\unit\test_exploration_results.py `
  tests\integration\test_exploration_daily_metrics.py `
  tests\integration\test_exploration_summaries.py `
  tests\integration\test_exploration_compatibility.py -q
```

**142 passed**, no deselections, skips or warnings in the final run.

Additional restoration regression:

```powershell
& '..\beon\Scripts\python.exe' -m pytest `
  tests\integration\test_exploration_provider.py `
  tests\integration\test_model_failure_modes.py -q
```

**77 passed**, no deselections or skips. Provider transports/models are synthetic/mocked;
there were no live inference calls. Combined independent selections: **219 passed**.

- Ruff check passes for all touched Python files; new/edited visual modules and the
  shared model/generation files pass format checks. `git diff --check` passes.
- Pylance reports no diagnostics in the new adapter or updated generation/config modules;
  the shared models retain only three pre-existing unused re-export hints.
- Wheel packaging passed using the declared isolated build backend. The initial
  `--no-build-isolation` attempt failed because the task-plan environment has no
  setuptools; standard isolated build succeeded without installing extra system tooling.
  The task-owned validation wheel/build directories were removed.
- The editor test tool did not discover the new modules; actual pytest commands above
  were used instead. No-tests-found was not treated as a pass.
- Initial behavioral red tests demonstrated missing projection/exact-integer adaptation,
  generation-time coverage and rollout capability before implementation.
- Imports of legacy export and the evidence adapter do not import WeasyPrint.
- No implementation extension hooks are registered.

### Pending Gates and Next Work

- Next implementation phase: T013..T024, browser defaults, shared chart grammar,
  evidence-derived explanations, application wiring and browser validation.
- T025..T027 still require the synthetic SVG/tagged-PDF feasibility spike. The actual
  native prerequisite is now installed from the official MSYS2 UCRT64 package repository:
  the signed-official installer `MSYS2.MSYS2` version `20260611` was downloaded by WinGet
  with the manifest SHA-256 verified; MSYS2 core and full system upgrades completed; then
  `mingw-w64-ucrt-x86_64-pango` was installed. Pango is 1.58.2; GLib/GObject and Pango
  DLLs are present at `C:\msys64\ucrt64\bin`. No repository/runtime code was copied there.
- Setting `WEASYPRINT_DLL_DIRECTORIES=C:\msys64\ucrt64\bin` in the renderer process makes
  `weasyprint --info` succeed with WeasyPrint 68.1 / Python 3.12.0 / pydyf 0.13.0 /
  Pango 1.58.2. A real one-page WeasyPrint PDF was generated in memory and parsed with
  pypdf; `PDF runtime ready` remained selectable. The console extraction displayed
  question marks for Greek/Latin diacritics in the default font, so this is not evidence
  of source-glyph coverage; package font preflight and the full T027 synthetic font check
  are still required. The install used about 60.14 MiB download / 433.17 MiB installed.
- T027 remains **NOT PASSED**: no actual Vega chart, tagged reading-order/header check,
  page/raster review, fault/timeout test or human reader assessment has been performed.
  PDF integration remains gated on that spike. Native provisioning itself is no longer a
  blocker; browser work continues independently. The app process must receive the DLL
  directory through its environment (or its managed launcher); the interactive session's
  current Python process already has it set only within the smoke-test PowerShell.
- Preferences/CAS UI, visual exports and rich chart integration remain unimplemented.
- SC-001..011/full E2E/AQ visual acceptance, twelve-PDF inspection, actual browser/PDF
  accessibility, independent/live acceptance and real-participant study remain pending.
  Foundation automation is not a replacement for these gates.

## 2026-10-18: US1 Browser Defaults Increment

**T013..T017, T020..T021 and T023..T024 complete; cumulative 21/66 tasks checked.**
The 003 setting is now wired through saved-history, source-unavailable history, and
unsaved-report presentation. It remains default-off. When enabled, supported saved
evidence can display a summary/card or embedded Vega-Lite chart alongside the exact
saved table; the UI does not reload source data or call an analytical/provider path to
prepare a visual. Listing results remain table-only. Failed, valid-empty, no-plottable,
selection-required and missing-evidence cases keep explicit messages and existing saved
evidence. Disabled mode identifies the existing report presentation.

The initial adapters cover scalar, grouped, listing, period-change, distribution, pair
and weather evidence shapes, but this is not full shape acceptance. At this original
checkpoint T018..T019 and T022 were pending; the later US1 increment below records their
implementation and focused validation. Interactive preference editing/CAS, visual
exports, the US2/US3 matrix and visual PDF remain unimplemented or unaccepted.

### Executed Automation

Command run with `..\beon\Scripts\python.exe`:

```powershell
& '..\beon\Scripts\python.exe' -m pytest `
  tests\unit\test_visual_evidence.py `
  tests\integration\test_visual_historical_evidence.py `
  tests\unit\test_visual_fixture_oracles.py `
  tests\unit\test_visual_font_assets.py `
  tests\unit\test_visual_defaults.py `
  tests\unit\test_visual_charts.py `
  tests\browser\test_visual_default_ui.py `
  tests\browser\test_exploration_summary_ui.py `
  tests\unit\test_exploration_results.py `
  tests\unit\test_exploration_contracts.py `
  tests\unit\test_config.py -q
```

**186 passed** in the recorded run. This selection includes AppTest for a default scalar
card, grouped chart, exact table-only listing, feature-disabled presentation, valid-empty
and failed sections, missing visual evidence, source-unavailable saved history and zero
provider/query calls during visual preparation. Synthetic category, small-multiple and
sparse-heatmap Vega-Lite specs were compiled to SVG with vl-convert; this does not satisfy
T027 or establish PDF tagging, font coverage or reader accessibility.

`ruff check` passed on the nine touched Python files; `ruff format --check` and
`git diff --check` passed. Pylance returned no diagnostics for the visual evidence,
chart and report-rendering modules and the new tests. The touched `app.py` and shared
models also retain previously observed unused-variable/re-export hints; no new error
diagnostics were returned. Signature compatibility was checked: all 49 `render_report`
call sites accept the optional feature flag.

After hardening the all-zero category scale, the broader regression selection
(`..\beon\Scripts\python.exe -m pytest tests\unit
tests\browser\test_visual_default_ui.py tests\browser\test_exploration_summary_ui.py -q`)
passed **287 tests**. The focused all-zero chart test also passed and compiled its spec
to SVG. Ruff check, format check and `git diff --check` passed again. These checks do not
change the pending release gates.

## 2026-10-18: US1 Temporal, Formatting and Timing Increment

**T018, T019 and T022 complete; cumulative 24/66 tasks checked.**

Temporal charts use recorded ISO dates as temporal axes, validate Monday-start week keys,
and normalize calendar-month keys without changing saved evidence. Verified coverage
creates explicit unavailable gaps only inside saved per-origin intervals; unknown
coverage breaks lines at nonconsecutive buckets without claiming those dates were
covered. Per-origin series use their own intervals, and an aggregate period is marked
partial unless every scoped origin covers the full bucket. Partial-calendar buckets use
a distinct marker; isolated single observations render as points. Time-series small
multiples retain shared scales and declared series order.

Chart names and explanations now include the measure/unit, dimensions/grain, requested
and observed periods, shown/returned/available scope, snapshot/revision provenance,
shown-subset extrema, counts, ties, missingness and saved unavailable reasons. English
labels preserve source Unicode. Numeric chart labels/tooltips and scalar/period summaries
use the saved effective `EvidenceFormat.rounding` when present and otherwise use the
two-decimal computed-value default; integer values retain integer display. Raw embedded
values, order and tie decisions remain unrounded. AQ-specific rounding is not inferred
from question text; the saved analytical format remains authoritative, and AQ acceptance
is still part of the pending T054 integrated matrix.

The visual-preparation timing record includes only duration, platform/Python version,
validated family, serialized evidence size and a safe failure category. It excludes
report content, IDs, labels, filters and exception text. The timing is server-side
preparation only and is not presented as browser-ready timing.

Command run with `..\beon\Scripts\python.exe`:

```powershell
& '..\beon\Scripts\python.exe' -m pytest `
  tests\unit `
  tests\browser\test_visual_default_ui.py `
  tests\browser\test_exploration_summary_ui.py `
  tests\performance\test_exploration_stage_timings.py -q
```

**305 passed.** The visual chart tests compile temporal, partial-coverage, gap and
small-multiple specs to SVG; timing tests verify content-free success/failure records and
stage aggregation. Ruff check/format, `git diff --check` and Pylance diagnostics passed
for all current implementation and regression-test files. These results do not establish
the remaining export, accessibility, AQ acceptance, reviewer or participant gates.

## 2026-10-18: US4 Synthetic PDF Feasibility Increment

**T025 complete; T027 remains pending; cumulative 25/66 tasks checked.** The automated
Windows spike generated and parsed a PDF containing a real Vega-Lite SVG and a long
synthetic table. The `tests\integration\test_visual_pdf_spike.py` selection passed
**4 tests**.

Observed runtime versions: Python 3.12.0, WeasyPrint 68.1, vl-convert-python 1.9.0.post1,
pypdf 5.9.0, fontTools 4.67.0 and Pango 1.58.2. The PDF tests use the packaged Noto Sans
Regular/Bold fonts; fontTools confirms the accented synthetic airport name is covered.
`WEASYPRINT_DLL_DIRECTORIES=C:\msys64\ucrt64\bin` makes the installed UCRT64 Pango
runtime available to the test process.

Automation verified PDF language and structure-tree presence; H1/H2/Figure/Table/TR/TH/TD
roles; table-row and header/cell parent relationships; figure alternative text; extracted
Unicode in both SVG title and table; repeated table headers on later pages; portrait and
landscape geometry; and local-file-only resource fetching in the real-SVG case. A missing
native-resource subprocess fails without producing PDF bytes. The timeout case validates
Python's synthetic subprocess watchdog only; there is no production PDF worker yet.
Ruff check/format, `git diff --check` and Pylance syntax validation passed for the spike
test.

This is automated feasibility evidence, not a visual or reader-accessibility pass. The
shared PDF browser rejected local-file access with a trusted-folder 403, and no local PDF
rasterizer or screen-reader executable was available for actual page/reader inspection.
Therefore T027 remains unchecked, supported package versions are not finalized, and
T028..T032 remain gated. The automated PDF structure assertions do not replace an actual
reader's header association or navigation check.

### Remaining Gates

- T027: actual page and reader inspection plus independent accessibility checks remain
  pending. Automated T025 feasibility and Pango runtime installation alone are not a pass.
- T028..T036: visual PDF/CSV, document accessibility, export agreement, failure handling
  and release validation remain blocked/pending as declared by the task dependencies.
- T037 onward: saved preference editing and lifecycle, complete view matrix, weather/AQ
  integration and integrated visual accessibility remain pending. No live provider,
  independent reviewer or participant evaluation was performed.

## 2026-10-18: US4 Browser Accessibility Progress

T033 remains pending because an actual screen-reader review has not been performed.
The large-pair evidence table now has a labelled native page control and retains the
complete saved population while showing bounded 100-row pages. Smaller pair results stay
in one complete table; the density evidence remains unpaged.

The synthetic 125-pair report was open in the shared real browser at `127.0.0.1:8765`.
The user manually pressed ArrowUp, changing the page from rows 1-100 to 101-125. The
assistant did not generate that keyboard action; it inspected the resulting page and
observed focus on the labelled page input. The browser accessibility snapshot exposed
the named exact-pair table and row range. The visible explanation reported 125 complete
paired observations and their missingness, without the misleading saved-group count or
unrelated temporal-coverage language. AppTest also verifies the five-pair result remains
a single complete named table.

After the final small-table regression was added, the focused command
`pytest tests\browser\test_visual_accessibility.py tests\browser\test_visual_default_ui.py tests\unit\test_visual_charts.py -q`
reported **29 passed**. Ruff check/format and `git diff --check` passed, and Pylance
reported no diagnostics for the touched chart, rendering and accessibility-test files.

This browser/keyboard evidence does not establish screen-reader output, PDF accessibility
or release acceptance. The browser console also reported a Vega-Lite schema/client version
mismatch (spec 5.20.1 versus client 6.4.3) and infinite-extent warnings; the chart rendered,
but these warnings remain to be investigated before compatibility is finalized. T033 and
the cumulative task count remained at **25/66** at this checkpoint.

## 2026-10-18: T026 Export Contract Test Increment

**T026 test authoring complete; T027 remains pending; cumulative 26/66 tasks checked.**
Added `tests\integration\test_visual_exports.py` and
`tests\accessibility\test_visual_pdf_accessibility.py` with the required
`test_export_defaults_*` selection token. The integration cases cover repository owner
checks, evidence-fingerprint-bound chart data, agreement with the existing analytical CSV,
zero versus missing-pair counts, exact floating-point serialization, formula-safe source
text, acknowledgement checks and no returned PDF bytes when renderer construction fails.
The accessibility case checks document language, tagged chart/table roles and figure
alternatives; it is automated structure coverage, not reader acceptance.

The exact initial selector collected **7 tests**: **4 passed and 3 failed**, with no
deselections or skips. The three red contract failures identify work deliberately pending
the later exporter implementation: there is no distinct chart-evidence CSV entry point,
acknowledged multi-section PDF export is not integrated, and the current V2 PDF lacks
document-language/tagged chart structure. They are not recorded as feature passes.
The unacknowledged composite and synthetic renderer-failure cases reject export without
returning bytes. Ruff check/format and `git diff --check` passed for the new tests and task
record. T027 still blocks T028..T032; T033 remains pending actual screen-reader review.

## 2026-10-18: T037 Preference Contract Test Increment

**T037 test authoring complete; T040/T043 implementation remains pending; cumulative
27/66 tasks checked.** Added `tests\unit\test_visual_preferences.py` for all declared
chart families, orientation and weather-field relevance, schema-version normalization,
identity validation and selection limits, saved-evidence/rule bindings, and the complete
shape compatibility matrix. The matrix uses representative time-series and two-category
dimensions at the inclusive grouped-bar limits.

The focused command `pytest tests\unit\test_visual_preferences.py -q` collected **29
tests**: **24 passed and 5 failed**, with no deselections or skips. The five expected red
cases expose the not-yet-implemented preference schema version, bar orientation,
weather-specific preference fields, and evidence/rule binding fields; these are scheduled
for T040 and T043. All compatibility-matrix cases and duplicate/unknown/over-limit
selection checks pass. Pylance reported no Python syntax errors; Ruff check and format
checks passed after formatting. The editor test runner did not discover the file, so the
project's direct pytest command was used for the recorded result.

## 2026-10-18: T027 Page Inspection and Legibility Correction

**T027 remains pending actual reader review; cumulative 27/66 tasks checked.**
Both requirements checklists remain satisfied (16/16 and 35/35); no checklist markers
were changed. The implementation prerequisite script resolved this feature, and no
extension hooks were configured.

The initial spike rerun passed all four existing tests, but actual raster inspection
identified an untested defect: chart labels were only approximately **6.22495 points**
after SVG scaling. A new PDF text-matrix/font-size assertion reproduced that failure.
The spike now uses explicitly sized horizontal bars, 16-pixel axis fonts, additional
axis-title padding, and proportional image height. The landscape fixture's clipped
placeholder text SVG was removed: the same real chart, language, tags, text-size and
complete-table assertions now run for both portrait and landscape. The visible caption
matches the figure alternative, and every one of the 90 synthetic table rows is checked.
The minimum-size assertion permits only 0.001 point of CSS/PDF serialization
quantization, not a smaller chart-text design.

Final focused command with the task-plan interpreter:

```powershell
& '..\beon\Scripts\python.exe' -m pytest tests\integration\test_visual_pdf_spike.py -q
```

**5 collected, 5 selected, 5 passed; 0 failed, deselected or skipped.** This is synthetic
renderer feasibility coverage, not integrated export or release acceptance.

The already installed `pypdfium2` **5.14.0** supplied local rasterization without any new
installation. The assistant inspected every page of the corrected four-page portrait
and six-page landscape PDFs at 1.5x raster scale. The reviewed output has legible separated
category/axis labels, visible matching figure descriptions, intact accented names,
repeated table headers, unsplit rows, and no observed clipping. All 90 table rows are
present in each orientation. This supersedes the earlier lack-of-rasterizer blocker.
This visual inspection is by the implementer, not an independent reviewer.

Review artifacts are retained under this session's `files` directory:
`acceptance-spike-review-20261018-0447\test_synthetic_tagged_pdf_pres0\synthetic.pdf`
(portrait), and the corresponding `test_synthetic_tagged_pdf_pres1\synthetic.pdf`
(landscape), with page rasters alongside them.

Actual reader heading order, figure announcements and table-header navigation remain
**NOT RUN**. NVDA was not available on PATH; this is not proof that no reader is installed.
The existing shared download PDF still returns a trusted-folder 403 in the integrated
browser; that restriction was not bypassed. T028..T032 remain gated, and supported
renderer versions/watchdog are not finalized. No live provider calls, independent
review or participant study were performed. The previously recorded export/preference
contract failures remain unresolved and are not converted into acceptance passes.

## 2026-10-18: Initial Actual NVDA Review Observation

At the owner's request, NVDA 2026.2 was installed through the verified NV Access winget
package (registered version 2026.2.0.57664). The portrait synthetic review PDF was opened
in the owner's Adobe Acrobat installation; the viewer version and reading preferences
have not yet been recorded.

The owner reports hearing the first heading as "synthetic report", followed by text
about the snapshot, but no further headings were found. The expected second heading
is "Exact evidence table". Record this as an unsuccessful initial heading-navigation
check, not an accessibility pass. Whether this reflects document structure, reading
mode/focus or viewer settings is not yet established. Graphic-description and table
navigation checks remain NOT RUN. T027 remains pending and T028..T032 remain gated.

## 2026-10-18: Owner PDF Review Scope Amendment and Report-Quality Priority

The owner clarified that pressing the level-2 heading shortcut in NVDA announces
"Exact evidence table". The initial inability to find the second heading was therefore
not reproduced with targeted heading navigation; it is not evidence of a confirmed
missing-heading defect. Graphic alternatives and table-header navigation were not tested.

The owner explicitly selected: "Skip manual PDF accessibility review; keep visual PDF
exports and automated structural checks, and remove the manual-review implementation
blocker", then requested focus on generated-report quality. The specification, plan,
tasks, research, validation guide and export contract now reflect that scope decision.
Manual PDF reader assessment is **NOT ASSESSED (owner-excluded)**, never passed.
No verified PDF reader compatibility or PDF/UA certification is claimed.

Retain automated structure/header/figure-description checks, visible descriptions,
selectable text, readable charts, actual page inspection and complete exact evidence.
Browser accessibility, numerical correctness, privacy/ownership, independent review and
other release gates are not waived. Existing reviewer-owned checklist markers remain
unchanged; their historical disposition predates this amendment.

No additional task is marked complete by this amendment. T027 no longer waits on a
manual PDF reader; its outstanding renderer-version compatibility/finalization and
watchdog evidence must still be resolved before dependent integration. Subsequent work
prioritizes factual findings and limitations, chart/evidence agreement, legibility and
complete exports rather than further PDF screen-reader exercises.

Post-amendment report-quality baseline using `..\beon\Scripts\python.exe -m pytest`:
`tests\unit\test_visual_charts.py tests\unit\test_visual_defaults.py
tests\unit\test_visual_fixture_oracles.py tests\integration\test_visual_pdf_spike.py -q`
reported **76 passed**, with no failures, deselections or skips. This verifies the
existing chart/default/oracle and synthetic PDF quality coverage only; it does not
resolve the outstanding integrated-export/preference tests or establish completed
visual PDF exports. No production rendering behavior or rollout default was changed.

## 2026-10-18: Owner AQ-07 distinct-flight-number clarification

The owner selected unique flight numbers within each airline, counted once across
the full scoped dataset, rather than recorded departure rows. Added the separate
`distinct_flight_number_count` measure, closed provider-schema/order support and
prompt guidance; existing `flight_count` semantics remain unchanged.

Airport-question, contract and provider regressions: **78 passed**. Independent
CSV sets agree with all 16 locally executed airline counts: UA leads with 1,284,
EV 1,098 and WN 862. The real Groq follow-up uses the correct metric but still
returns only ten airlines, so it is not a complete-ranking acceptance pass.

The complete analyst-configured ranking and legacy PDF, as well as the partial
live report/PDF and initial schema failure, are separately preserved in
[the AQ-07 correction report](../../reports/quality-test-20261018/AQ-07-CORRECTION.md).
Earlier row-count AQ-07 artifacts are historical and superseded for this question.
No browser-chart or visual-PDF acceptance claim is made by this metric change.
