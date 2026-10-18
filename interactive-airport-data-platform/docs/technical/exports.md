# CSV, ZIP, and PDF exports

[Documentation home](README.md) | [Previous: Visual reporting and presentation](visual-reporting.md) | [Next: Identity, authorization, and consent](identity-and-consent.md)

Implementation reference: 2026-10-18. See [scope and status](README.md#scope-and-status).

- [Export contracts](#export-contracts)
  - [Export surfaces](#export-surfaces)
  - [CSV integrity](#csv-integrity)
  - [Source-backed selection and bundles](#source-backed-selection-and-bundles)
  - [V2 PDF](#v2-pdf)
  - [Native runtime and resource policy](#native-runtime-and-resource-policy)

## Export contracts

### Export surfaces

| Function/surface | Contract |
|---|---|
| `export_report_csv` | V1 result/routes or one V2 section's saved table/listing preview |
| `export_listing_csv` | Explicitly selected, bounded source-backed listing expansion |
| `export_report_bundle` | ZIP of section evidence, manifest and available supporting evidence |
| `export_chart_evidence_csv` | Exact applied visual rows plus visual provenance metadata |
| `export_report_pdf` | V1 ReportLab or V2 tagged WeasyPrint report |

`export_chart_evidence_csv` is currently a library/test API, not a download button wired
into the app. Ordinary CSV, ZIP and PDF exports are wired in the UI.

### CSV integrity

CSV uses UTF-8 with BOM and CRLF. V2 listing exports carry `_meta_*` fields describing report,
section, revision, source/context, scope, definition, completeness, exported/total population,
partial status, null fields and text-escaping rules.

Risky string cell prefixes, including spreadsheet formula prefixes and leading apostrophes,
receive reversible apostrophe escaping. Numeric values are not an excuse to interpret text
as spreadsheet formulas. Reserved `_meta_` data column names are rejected.
Empty listings can emit a metadata-only row.

### Source-backed selection and bundles

`ExportSelection` binds analyst/session/report/request/revision/source/context, effective
scope/order hashes, section allocations, population totals and confirmation.
Changing a bound selection invalidates prior confirmation.

Default bundles export saved evidence and never implicitly expand listing previews.
Explicit expansion requires the bound current executor, deterministic allocations, current
population checks and confirmation. Failed sections remain represented with status/reason
metadata rather than disappearing.

Supporting files can include daily denominator/count evidence and weather-pair evidence.
Bundle generation is atomic: a failure does not offer a success-shaped partial download.

ZIP layout:

```text
manifest.json
section-1.csv
section-2.csv
section-1-daily-support.csv          # when daily support exists
section-2-weather-{index}.csv       # indexed weather auxiliary files when present
...
```

The weather suffix is an implementation variable index; inspect `auxiliary_files` rather
than assuming a named variable from the filename alone.
The manifest contains report/revision/source/context, completeness, allocations, bundle kind,
listing/null/text rules and section entries. Each section entry describes its file, auxiliary
files, status, exported/total rows, selection, scope, definition, fields, failure and omitted
listing rows. Weather auxiliary evidence distinguishes complete pairs from density cells.

### V2 PDF

The V2 exporter creates semantic HTML over all sections, including the original question near
the top, report metadata, definitions, exact evidence tables, charts where supported, limitations
and failed-section reasons. Incomplete reports must be persistable/acknowledged first.

Vega-Lite charts are converted to SVG and embedded as data-URI images with alternative text.
WeasyPrint writes a tagged PDF (`pdf_tags=True`) with document language, headings, figure and
table structure. Bundled Noto Sans regular/bold fonts avoid remote font dependencies.

This is implemented structural accessibility, not a claim of manual screen-reader certification
or compliance with every PDF accessibility standard.

### Native runtime and resource policy

WeasyPrint requires Pango/native dependencies. On Windows, the runtime can discover
`C:\msys64\ucrt64\bin` or `C:\msys64\mingw64\bin` when the needed DLL is present, or use
`WEASYPRINT_DLL_DIRECTORIES`.

The PDF fetcher allows data URIs and the specifically bundled font files. Arbitrary network
resources and unrelated local file resources are rejected. PDF rendering is not a general
HTML-to-PDF service for arbitrary external URLs.

If native loading fails, `PdfRuntimeUnavailableError` is explicit. The UI disables the PDF
download and retains CSV/browser evidence. There is no silent untagged V2 PDF fallback.
V1 still uses its separate ReportLab path.
The browser visual flag does not gate V2 PDF chart preparation: PDF charts resolve saved
evidence/preferences independently. Disabling browser charts therefore does not disable
V2 PDF chart conversion or eliminate its renderer dependencies.

Downloading an ordinary report returns bytes to the browser. It does not automatically write
a copy into the repository's local `reports` directory; files there are separately generated
test/evaluation artifacts.

---

[Documentation home](README.md) | [Previous: Visual reporting and presentation](visual-reporting.md) | [Next: Identity, authorization, and consent](identity-and-consent.md)
