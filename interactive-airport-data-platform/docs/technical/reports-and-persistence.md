# Reports, persistence, and retention

[Documentation home](README.md) | [Previous: Model integration, token usage, and budgets](hosted-inference.md) | [Next: Visual reporting and presentation](visual-reporting.md)

Implementation reference: 2026-10-18. See [scope and status](README.md#scope-and-status).

- [Report models, evidence, and revisions](#report-models-evidence-and-revisions)
  - [V1 report](#v1-report)
  - [V2 report envelope](#v2-report-envelope)
  - [Incomplete and empty are different](#incomplete-and-empty-are-different)
  - [Saved evidence and deterministic narrative](#saved-evidence-and-deterministic-narrative)
- [SQLite persistence and retention](#sqlite-persistence-and-retention)
  - [Tables](#tables)
  - [Decoding and ownership](#decoding-and-ownership)
  - [Retention and backup](#retention-and-backup)

## Report models, evidence, and revisions

### V1 report

`ReportContent` stores the question, original validated analysis plan, saved result payload,
definitions/scope, narrative, source identity and report ownership metadata.
V1 history remains readable and is not reinterpreted as a V2 result.

### V2 report envelope

`CompositeReportV2` contains:

- `report_version=2`, report/analyst/session identities and optional parent report.
- Original question, revision, UTC creation time, snapshot and context.
- Semantic version map for catalog, aliases, rules, units and coverage.
- Shared scope and explicitly removed sections.
- One to four ordered sections.
- Complete/incomplete status and optional exact incomplete acknowledgement.
- Per-section presentation preferences and preference concurrency version.

Each section carries its interpretation and a completed, valid-empty or failed outcome.
Evidence types include scalar, grouped, listing, comparison/distribution/relationship,
daily support and weather-panel information.

Validation reconciles report/section/request/revision/snapshot/context identities, analytical
definition, scope and grain. A result with inconsistent provenance is not a valid report
merely because its numeric value looks plausible.

### Incomplete and empty are different

- **Valid empty:** execution succeeded and the selected population/result is empty.
- **Failed:** a requested section could not be executed/reported.
- **Incomplete report:** some sections succeeded and at least one failed.
- **All failed:** not accepted as a successful report.

Incomplete persistence/export requires acknowledgement of the exact report/revision and failed
sections. The UI retains computed unsaved evidence while asking for that acknowledgement.
Saving failure is not presented as successful persistence.

### Saved evidence and deterministic narrative

Report text and limitations are assembled locally from calculated results and definitions;
there is no separate unrestricted model call to invent the numerical report narrative.
Definitions preserve population, units, weighting, exclusions and denominator meaning.

Saved previews/tables can be reopened without recomputing against current sources.
Analytical refinement is a new calculation/revision; table formatting is not.
## SQLite persistence and retention

### Tables

| Table | Important columns and role |
|---|---|
| `schema_metadata` | Key/value metadata; current recorded schema version is 3. |
| `reports` | `report_id`, owner/session, question, full `payload_json`, snapshot, creation time. |
| `consent_events` | Grant/withdraw audit identity, owner/session, purpose, notice version, time. |
| `shared_artifacts` | Separate artifact ID, source-report reference, consent-event FK, purpose, content JSON, creation time. |
| `usage_reservations` | Provider/model/month, monetary/token bounds and actuals, status, uncertainty, failure reason, dispatch/settlement timestamps and cached-token telemetry. |

Source CSV tables are in DuckDB, not in these SQLite tables.

`Storage` creates the database parent directory, initializes tables/indexes, enables foreign
keys, sets a 30-second busy timeout and WAL for file-backed databases. Writes use
`BEGIN IMMEDIATE` by default and commit/rollback through context managers.

Initialization also adds missing supported usage columns, including `cached_input_tokens`,
through additive checks. The schema-version value remains 3; do not assume it describes
every additive change as an independently numbered migration.

### Decoding and ownership

Missing `report_version` means legacy V1. Integer `report_version=2` selects V2.
Unsupported versions, malformed JSON or invariant failures raise `ReportFormatError` without
rewriting the stored report.

Repository operations are owner-scoped. Save revalidates the serialized report before writing.
Preference updates use an expected version to detect conflicting updates; conflicts require
refresh and explicit retry rather than silently overwriting another update.
The update also compares the original serialized payload in its SQL condition; a concurrent
writer changing it causes a conflict instead of lost updates.

### Retention and backup

The ten newest private reports per analyst are retained. This is a count-based policy, not
a time-based retention duration. Private deletion/pruning does not retract separately shared
artifacts.

There is no implemented backup scheduler, restore orchestrator, account-deletion workflow,
or backup-expiry policy. Operators must define these before production approval.
For live WAL databases, use SQLite's supported backup mechanism or a coordinated stopped
application backup; copying only the database file during active writes is not a reliable
general backup procedure.

Back up source files, reviewed coverage/unit evidence and deployment configuration appropriately
as well: a report payload and a reproducible source-backed analysis have different recovery needs.
Secrets require separate restricted storage, not inclusion in public report artifacts.

---

[Documentation home](README.md) | [Previous: Model integration, token usage, and budgets](hosted-inference.md) | [Next: Visual reporting and presentation](visual-reporting.md)
