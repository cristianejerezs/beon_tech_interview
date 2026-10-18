# Visual reporting and presentation

[Documentation home](README.md) | [Previous: Reports, persistence, and retention](reports-and-persistence.md) | [Next: CSV, ZIP, and PDF exports](exports.md)

Implementation reference: 2026-10-18. See [scope and status](README.md#scope-and-status).

- [Visual reporting](#visual-reporting)
  - [Feature boundary](#feature-boundary)
  - [Evidence and resolution](#evidence-and-resolution)
  - [Bounds and accessibility](#bounds-and-accessibility)
  - [Preference implementation status](#preference-implementation-status)

## Visual reporting

### Feature boundary

`AIRPORT_VISUAL_REPORTING_ENABLED` controls the browser visual-preview path and defaults false.
V2 analytical exploration is a separate UI toggle and defaults true.

Visual preparation consumes saved report evidence, not a fresh model call or analytical query.
The exact result table remains available. Missing/invalid/unsupported visual evidence must
produce an explicit status rather than a chart using substituted source data.

### Evidence and resolution

`prepare_visual_evidence()` produces detached canonical evidence. Its versioned documents
carry report/section/revision/source identity, definition, scope, coverage, missingness,
format and payload.

Current visual metadata includes `visual_evidence_version=1`,
`selection_rule_version="003.1"`, source evidence version, and SHA-256 evidence fingerprint.
`resolve_presentation()` determines compatible/default view, selected identities, counts,
limitations and state before chart construction.

| Evidence shape | Default view | Other compatible views |
|---|---|---|
| Scalar | summary | table |
| Listing | table | none |
| Category/ranking | bar | dot, table |
| Time | line | bar, table |
| Time series | line | small multiples, table |
| Two categories | grouped bar | heatmap, table |
| Period change | bar | dot, table |
| Distribution | histogram | table |
| Flight relationship | scatter | table |
| Weather panel | scatter | table |

Compatibility does not imply the preference can currently be edited and persisted from the UI.
Relationship/weather evidence containing density uses the density view instead of scatter;
the resolver follows the saved pairing payload rather than resampling the source.

### Bounds and accessibility

- Category/ranking charts show at most 20 identities.
- Selected time-series identities cap at 20; line views cap at eight selected series.
- Grouped bars require two categorical roles, at most 20 primary categories and one to eight series.
- Heatmaps use at most 500 saved cells.
- Preference identity lists cap at 500 and must refer to saved evidence without duplicates.
- Visual selection does not change analytical returned/available population counts.
- Non-ready/selection-required states carry explanatory reasons.
- Accessible text descriptions, explicit table alternatives and non-color-only status are part
  of the implemented presentation approach; full manual accessibility acceptance is separate.

Rankings default to the first 20 identities in evidence order, with separate analytical and
visual cutoff-tie disclosure. Unranked category results above 20 identities require selection
rather than inventing a top-20 ordering. Explicit selections preserve evidence order, not
the order of IDs supplied in a preference. Non-finite/null data does not become invented
points; no usable numeric values produces `no_plottable_data` while keeping the saved table.

### Preference implementation status

The typed preference model contains chart family and category/series identity lists.
The repository's persisted update path currently accepts only `default`/`table` without identity
selections. The UI labels this as table-only presentation preference editing.

The unfinished preference test module expects additional orientation, weather-variable/origin,
schema-version and evidence-binding fields that are not yet implemented. Do not infer full
cross-view persistence from the broader in-memory chart family enum.

V1 retains a legacy Plotly chart path, including table fallback for empty results, multiple
groupings or more than 50 rows. Its behavior is not the V2 visual-evidence resolver.

---

[Documentation home](README.md) | [Previous: Reports, persistence, and retention](reports-and-persistence.md) | [Next: CSV, ZIP, and PDF exports](exports.md)
