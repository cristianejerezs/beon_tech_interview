# Research: Automatic Visual Reporting

**Date**: 2026-10-18  
**Scope**: Design research plus explicitly dated implementation setup below.
No successful PDF spike or accessibility pass is claimed by package installation.

## Implementation setup: 2026-10-18

Candidate direct dependencies were declared before restoring `.[dev]` into the task-plan
Python 3.12 environment (`..\beon\Scripts\python.exe`). Actual installed versions:
Streamlit 1.66.0, Altair 6.3.0, vl-convert-python 1.9.0.post1,
WeasyPrint 68.1, fontTools 4.67.0. `pip check` reports no broken requirements.
These are candidate bounds, not final T027-tested PDF compatibility.
vl-convert advertises Vega-Lite 5.8/5.14/5.15/5.16/5.17/5.20/5.21/6.1/6.4;
the shared browser/SVG version must still be validated.

The native import probe (`python -m weasyprint --info`) fails with Windows error 0x7e:
`cannot load library 'libgobject-2.0-0'`. No native installation was attempted.
Only dependent PDF integration/release is blocked by this result.

Pinned, unmodified Noto Sans Regular/Bold static fonts and their OFL 1.1 notice are
packaged with per-asset SHA-256/provenance. Their upstream revision is
`ffebf8c1ee449e544955a7e813c54f9b73848eac` of
[notofonts/noto-fonts](https://github.com/notofonts/noto-fonts).
Each asset references its bundled license; neither is a workstation commercial font.
Local-only inspection of airport/airline/aircraft records found no non-ASCII characters.
Synthetic Latin, Greek and Cyrillic coverage is checked separately. This is not a claim
that every Unicode script is supported; runtime glyph preflight remains mandatory.

Pylance currently selects the separate parent `.venv` interpreter. Setup deliberately
follows the task-plan `beon` interpreter without switching editor settings or other chats.

## R1. Evidence-first presentation

**Decision**: Build a pure adapter over owned saved interpretations/results, then classify
and select views using versioned fixed rules. Do not add chart instructions to the provider
intent or re-run analytics to switch views.

**Rationale**: Existing 002 models already separate analytical kinds, stable identities,
scope, unavailable values, full pairs/density and per-variable weather coefficients.
Current V2 tables and weather findings prove usable handoff points, but are not a visual
implementation. Historical reports must remain reproducible when local sources change.

**Alternatives considered**: Model-selected charts create charges and nondeterministic
semantics; inspecting label strings confuses calendar months with pooled months; rebuilding
evidence from current sources corrupts historical context.

**Repository evidence**: `models.py` analytical unions and `CompositeReportV2`;
`reports/rendering.py` table/findings adapters; `analytics/pair_metrics.py` complete pair
populations; `reports/export.py` existing bounded evidence bundles.

## R2. Browser and graphic renderer

**Decision**: Use application-owned Vega-Lite specifications through Streamlit, with
Altair where it simplifies typed construction. Use `vl-convert-python` for local SVG.
The same bound dataset, encodings, identities, scales and order feed browser and PDF;
PDF layout may resize or facet without changing the selected population.

**Rationale**: Native Streamlit supports named charts and exact tables. vl-convert embeds
its JavaScript runtime and needs neither Node nor an external browser. Altair 6.3.0 is
already installed transitively; declare it directly when implementing. Explicitly select
a Vega-Lite version supported by both Streamlit's bundled runtime and vl-convert and test
it, rather than assuming latest versions are interchangeable.

**Alternatives considered**: Plotly is already present for V1, but Kaleido v1 needs Chrome
and adds deployment complexity for new static exports. Keep V1 callers until migration;
do not rewrite unrelated legacy charts. Raw custom HTML/chart components are unnecessary.

**Sources**:
- [Streamlit chart documentation](https://docs.streamlit.io/develop/api-reference/charts)
  and version-matched installed Streamlit 1.66 data-display/testing guidance.
- [vl-convert Python](https://pypi.org/project/vl-convert-python/): local SVG/PNG conversion,
  embedded V8 and no external browser/Node requirement.
- [Altair saving charts](https://altair-viz.github.io/user_guide/saving_charts.html).
- [Kaleido](https://pypi.org/project/kaleido/): external Chrome requirement for v1.

**Verification boundary**: No vl-convert wheel/native execution was tested in this plan.
First implementation gate validates Windows/Python 3.12 installation and actual output.

## R3. Tagged, local PDF

**Decision**: Primary route is semantic HTML to WeasyPrint, with application-generated SVG,
semantic headings/tables, explicit row/column headers and figure descriptions. Enable its
documented tagged/accessibility output mode; verify actual structures and reading order.
Do not describe the result as PDF/UA certified.

**Rationale**: The current ReportLab exporter produces table-oriented PDFs, without the
required tagged document contract. WeasyPrint documents accessibility/tagged PDF generation
and paged layout, but its documentation explicitly does not guarantee valid accessibility
output from arbitrary inputs. Correct source semantics and actual validation are required.

**Alternatives considered**: Open-source ReportLab is not the selected tagging path;
commercial ReportLab tagging introduces a new license/service procurement decision.
fpdf2's image alt-text/fallback-font features alone do not establish complete tagged
heading/table/header/reading-order support. Do not infer a package is universally incapable;
the selected route has the relevant documented support and must still pass a spike.

**Sources**:
- [WeasyPrint PDF variants and accessibility](https://doc.courtbouillon.org/weasyprint/stable/common_use_cases.html).
- [WeasyPrint 57 accessibility introduction](https://www.courtbouillon.org/blog/00031-weasyprint-57-beta/).
- [WeasyPrint API/CSS/fonts](https://doc.courtbouillon.org/weasyprint/stable/api_reference.html).
- [ReportLab accessibility](https://docs.reportlab.com/pdf-accessibility/).
- [fpdf2 accessibility work](https://github.com/py-pdf/fpdf2/issues/792)
  and [tables](https://py-pdf.github.io/fpdf2/Tables.html).

**Feasibility gate**: Generate a synthetic multi-page report with headings, an actual chart,
row/column-headed exact tables, long labels and non-ASCII names. Inspect `StructTreeRoot`,
document language, figure alternatives, headings, `Table/TR/TH/TD`, header relationships,
embedded fonts, Unicode extraction and reading order. Raster-inspect clipping and 10-point
text. The owner's 2026-10-18 scope amendment excludes the manual PDF screen-reader spot
check from this gate; record it as NOT ASSESSED. Technical, structural or page-quality
failures still require a corrected spike or a reviewed alternative.

## R4. Windows/native dependencies and resource safety

**Decision**: Use the Python-library integration with locally provisioned Pango on Windows.
Document MSYS2 UCRT64 Pango and `WEASYPRINT_DLL_DIRECTORIES` when required. Do not auto-install
native tools or alter the user's system during planning.

**Rationale**: Official Windows instructions distinguish the standalone executable from
the Python library and require Pango/native dependencies for the latter. A Python wheel
alone is not proof of readiness. The environment currently has neither WeasyPrint nor
vl-convert installed.

**Resource policy**: Generate HTML/CSS/specs internally; HTML-escape data labels and source
text, never treat them as markup. Embed datasets; prohibit external data URLs, scripts,
attachments, remote fonts and arbitrary local file access. Use a deny-by-default asset
fetcher serving only job-owned graphic bytes and approved font assets. Validate SVG has
no external references. Package locally bundled assets and retain their license notices.
Reject unsupported resources and surface glyph/font/layout errors.

**Execution policy**: A local spawned worker handles PDF conversion, with a bounded
technical watchdog and cleanup of that job's temporary paths. Terminate only the owned
worker on failure. Return complete validated bytes or a safe typed error; no partial
downloads, hidden retry, raw HTML logging or detached service. Size bounds are inherited
from 002/003; test large pair appendices and imposed timeout failure explicitly.

**Sources**:
- [Official Windows/Pango installation and DLL troubleshooting](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#windows).
  Verified from the full official HTML: MSYS2 UCRT64
  `pacman -S mingw-w64-ucrt-x86_64-pango`, plus optional DLL search directory.
- [WeasyPrint rendering/resource risks](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#security).

## R5. Fonts and licenses

**Decision**: Package a reviewed, redistributable static font set with notices; start with
Noto Sans and script fallbacks needed by actual fixture/source names. Use the same font
family/metrics in chart image rendering and PDF layout where supported. Preflight every
code point and fail explicitly if no approved font covers it. Do not silently transliterate,
replace with squares or assume an English interface implies ASCII-only source labels.

**Rationale**: OS-dependent fallback is not reproducible. Font coverage and embedding must
be checked after SVG conversion as well as in document text. A missing script can require
an added licensed asset, not permission to corrupt the label.

**Alternatives considered**: Fetching fonts at export time violates local-only rendering;
one system font fails portability and glyph coverage.

**Licensing**: Review exact pinned versions and bundled notices during implementation:
WeasyPrint BSD, vl-convert MIT and Altair BSD-3-Clause are suitable candidate dependencies;
Noto assets commonly use SIL OFL, but record the license for every actual asset shipped.
Do not copy commercial fonts from this workstation into the package.

**Sources**: [Noto fonts](https://notofonts.github.io/);
[WeasyPrint font support](https://doc.courtbouillon.org/weasyprint/stable/api_reference.html#fonts).

## R6. Persistence and concurrency

**Decision**: Extend `SectionPresentationPreference` rather than adding a second preference
table. Reuse `ReportRepository.update_preferences` ownership, report-level expected version
and compare-and-swap. Bind each applied selection to the saved evidence fingerprint and
selection-rule version. Preserve analytical revision and canonical analytical evidence.
Add backward-compatible empty preferences/version to V1 and extend this same CAS path,
so known historical evidence supports owned saved views without migration on read.

**Rationale**: The repository already implements stale-save detection and ten-report pruning.
The current restrictive default/table gate is an integration placeholder, not a reason to
bypass repository validation. Conflict handling offers reload/review/reapply without
silently merging stale choices.

**Alternatives considered**: Session-only state fails reopen requirements; last-write-wins
contradicts the accepted clarification; storing full renderer blobs duplicates evidence.

## R7. Accessibility, validation and observability

**Decision**: Native named controls, explicit disabled reasons, evidence descriptions,
exact row/column-headed table alternatives, fixed non-color encodings and real manual
reviews. Use server stage timings plus browser-side acceptance measurement; record safe
sizes/family/failure categories, not report IDs, values, labels or filter contents in logs.

**Rationale**: A chart `alt` attribute and a PDF tag tree alone do not prove usability.
Streamlit AppTest checks state but not actual DOM focus, chart readiness or screen-reader
navigation. Existing five-analyst and independent/live 002 gates remain external work.

**Alternatives considered**: Treating automated metadata checks as WCAG acceptance or
recruiting implementers as usability participants would misrepresent the specified gates.

## R8. Clarification-to-design reconciliation

**Decision**: Retain the selected evidence-first stack and integrate the clarified behavior
without a new analytical pipeline. Weather uses centered Pearson without transformation,
weather on x and hourly mean departure delay on y. Retain unavailable default temperature
with an explicit reason; coefficient eligibility is not plotting eligibility. Keep period
change summaries as text/value blocks and PDF descriptions both visible and associated
with the tagged figure. Historical source loss does not erase sufficient saved evidence.

**Rationale**: These refinements remove ambiguity without changing approved calculations
or requiring new libraries. The existing data model/contracts now carry them. Mixed
aviation/non-aviation participant backgrounds are a recruitment requirement, not a new
application feature. Exact raw evidence and shared 002 numerical tolerance remain unchanged.

**Alternatives considered**: Automatic weather substitution would hide missing evidence;
independently authored PDF descriptions could drift from the chart; source backfill would
change historical meaning. None is adopted.

**Research reuse**: R1..R7 retain their source references and unresolved feasibility
boundaries. This planning rerun does not repeat the already completed research-agent task
or claim new runtime experiments. The 35-item reviewer checklist is pending review, not
additional empirical evidence of suitability.

## Resolved Decisions and Remaining Validation

No unanswered product clarification remains. The library version pair, native runtime,
tag/header semantics and glyph rendering are mandatory early implementation checks,
not completed results. Manual PDF real-reader compatibility is NOT ASSESSED and is not
a prerequisite under the owner's 2026-10-18 scope decision. If technical checks fail, stop the dependent exporter
work and record the failure. This plan does not authorize a hosted fallback, relaxed
accessibility, provider calls, branch changes or claims of integrated release.
