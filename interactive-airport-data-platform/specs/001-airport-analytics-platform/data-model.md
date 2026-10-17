# Data Model: Interactive Airport Data Platform

## Overview

The application keeps three boundaries separate:

1. **Analytical source data**: local CSV files queried through DuckDB.
2. **Private analyst state**: report history and consent events stored locally in SQLite.
3. **Shared reuse material**: a separate copy created only from content produced while the current session's relevant consent is active.

The language model receives schema/metric context and the question, and returns an `AnalysisPlan`. It does not own persistent state or execute queries.

## Source Data

### Source Dataset Snapshot

Identifies the exact source files used for a report.

| Field | Description |
|---|---|
| `snapshot_id` | Stable identifier derived from the manifest/version of the source set. |
| `dataset_name` | Dataset identifier, such as flights, airports, airlines, planes, or weather. |
| `relative_path` | Workspace-relative source file path. |
| `sha256` | Content digest used to detect replacement or modification. |
| `row_count` | Validated number of imported rows. |
| `schema_version` | Version of the application's normalized column catalog. |
| `validated_at` | Time the local validation completed. |

Each report refers to a snapshot identifier. A modified source file creates a new snapshot rather than silently changing the provenance of a saved report.

### Flight

One row from the flight CSV, retaining a stable source-row identifier.

| Field group | Description |
|---|---|
| Identity | `flight_row_id` (snapshot plus source row index). |
| Schedule/date | Year, month, day, scheduled departure/arrival times, and flight date. |
| Actuals/delays | Actual departure/arrival times and available departure/arrival delay measures. |
| Route | Origin and destination codes, distance, and available elapsed-time measures. |
| Carrier/aircraft | Carrier code and tail number where present. |
| Time/weather context | Flight hour/time key where present; joined weather is optional and must pass temporal/key validation. |

Preserve raw source values and normalized values separately when parsing or code normalization is required. Missing values remain missing; do not coerce them to zero.

### Airport

One airport reference row, with the source code, name, location, and coordinates available in the supplied file. Code normalization must preserve the original code and be validated against flight origin/destination coverage before it is used as a join key.

### Airline

One carrier reference row, keyed by the source carrier code, with the airline name/description.

### Aircraft

One aircraft reference row, keyed by tail number where available, with manufacturer, model, engine, and other supplied descriptive attributes.

### Weather Observation

One weather row, retaining the source airport/origin code and time key, with the supplied temperature, wind, visibility, and other weather measures. A flight-to-weather association is permitted only after validating the key/time alignment and documenting the matching rule. Weather comparisons are contextual associations, not causal findings.

## Analyst and Session State

### Analyst Identity

| Field | Description |
|---|---|
| `analyst_id` | Internal stable identity derived from the OIDC issuer and subject pair. |
| `issuer` | Identity provider issuer. |
| `subject` | Provider's stable subject claim. |

Do not use email as the ownership key. Avoid copying identity claims into report text or shared FAQ content unless a separately disclosed and authorized purpose requires it.

### Analysis Session

| Field | Description |
|---|---|
| `session_id` | Opaque random identifier for one application session. |
| `analyst_id` | Owner of the session. |
| `started_at` | Session start time. |
| `consent_state` | Current session-level state for each disclosed reuse purpose. |
| `notice_version` | Version of the notice presented for consent. |

Session consent is not a permanent account preference. A new session starts with reuse disabled; an analyst may enable it later and may disable or re-enable it during that session.

### Consent Event

Append-only record of a consent action.

| Field | Description |
|---|---|
| `consent_event_id` | Opaque event identifier. |
| `analyst_id`, `session_id` | Actor and session for the event. |
| `purpose` | Specific reuse purpose presented to the analyst. |
| `action` | Explicit grant or withdrawal. |
| `occurred_at` | Event time. |
| `notice_version` | Exact disclosure version accepted or withdrawn. |

Each shared reuse artifact points to the grant event that authorized its creation. A later withdrawal prevents future reuse but does not delete previously created shared artifacts. Retain only the minimal event metadata needed to audit a retained artifact; production retention duration requires privacy/legal review.

Before production reuse is enabled, approve and document retention periods and deletion procedures for analyst identity mappings, private reports, consent events, shared artifacts, and backups. Keep production shared reuse disabled until this policy is approved.

## Reports and Reuse

### Analysis Report

| Field | Description |
|---|---|
| `report_id` | Opaque random report identifier. |
| `analyst_id` | Enforced owner. |
| `session_id` | Session in which it was created. |
| `question` | Non-empty plain-text analyst question of at most 2,000 Unicode code points after trimming, kept in private history. |
| `analysis_plan` | Validated structured plan used by the application. |
| `result_payload` | Typed result data needed to render the answer, tables, charts, and exports. |
| `narrative` | Explanation, if model-generated, grounded in the validated result and metric glossary. |
| `snapshot_id` | Source snapshot used for the report. |
| `created_at` | Report creation time. |

The private report repository retains the ten most recent reports for each analyst. When a report falls outside that limit, delete its private report record and dependent private result payload. Do not delete an independently retained shared reuse artifact that was authorized earlier.

### Shared Reuse Artifact

A separately stored copy of only the question/report material selected for a disclosed reuse purpose.

| Field | Description |
|---|---|
| `artifact_id` | Opaque identifier. |
| `source_report_id` | Originating report identifier for audit, not a public attribution. |
| `consent_event_id` | Grant event authorizing creation. |
| `purpose` | FAQ or system-improvement purpose disclosed at opt-in. |
| `content` | Reusable content, minimized to what that purpose needs. |
| `created_at` | Reuse-copy creation time. |

Create no artifact if consent is inactive at the time the source content is created. Shared artifacts remain after consent withdrawal in accordance with the specified behavior. Do not expose the analyst's identity in the artifact by default.

### Model Usage Reservation

Persistent budget ledger for hosted model calls and any explicitly enabled metered tracing.

| Field | Description |
|---|---|
| `reservation_id` | Opaque identifier for a model request or trace operation. |
| `provider_id`, `model_id` | Configured service and model identifier. |
| `period_start_utc` | UTC start of the calendar-month budget period. |
| `reserved_usd` | Conservative maximum charge reserved before the operation begins. |
| `actual_usd` | Provider-reported charge or conservative reconciled estimate after completion. |
| `status` | Reserved, settled, failed, or released. |
| `input_tokens`, `output_tokens` | Usage quantities where available. |
| `created_at`, `settled_at` | Reservation and reconciliation timestamps. |

Count all in-flight reservations when authorizing another paid hosted call. A reservation is
released or reconciled only when the operation outcome and charge are known; if cost cannot be
bounded, reject the paid hosted request. The combined hosted inference and metered LangSmith
charge MUST remain at or below USD 10 per UTC calendar month. Free-tier quotas have separate
provider-side limits and are tracked even when `actual_usd` is zero. Include directly attributable
provider-billed fees and taxes and currency-conversion charges. Attribute charges to the UTC month
in which the underlying operation was accepted, even if invoiced later. Retry only after provider-
confirmed non-acceptance; retain reservations with uncertain acceptance until reconciled, and
reconcile partial responses using reported usage or a conservative estimate. If reconciled charges
exceed the reservation, record the actual amount, surface the discrepancy to the operator, and
block further paid hosted calls if the remaining allowance is exhausted.

## Analysis Plan

The model's typed response is described by [analysis-plan.schema.json](./contracts/analysis-plan.schema.json). The application validates it against both the JSON Schema and a versioned allowlist derived from the data catalog. Invalid, ambiguous, or unsupported plans are not executed.

## Relationships and Integrity Rules

- An analyst owns zero or more sessions and reports.
- Every report belongs to exactly one analyst and source snapshot.
- Every shared reuse artifact has one originating report and one authorizing grant event.
- Every grant/withdrawal is scoped to a session and a disclosed purpose.
- All history and export access is filtered by authenticated `analyst_id` at the data-access boundary.
- Private report retention is capped at ten per analyst; shared artifact retention is separate.
- Joins to airports, airlines, planes, or weather are explicit catalog relationships. Validate join coverage and cardinality; never infer or silently invent a matching key.
- Query filters, identifiers, operators, sort order, grouping, and row limits are validated before query compilation.
