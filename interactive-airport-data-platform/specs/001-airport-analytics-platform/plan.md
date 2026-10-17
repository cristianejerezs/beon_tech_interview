# Implementation Plan: Interactive Airport Data Platform

**Branch**: `001-airport-analytics-platform`<br>
**Date**: 2026-10-17
**Spec**: [spec.md](./spec.md)

## Summary

### Approved amendment: 2026-10-17

Owner-approved exceptions supersede earlier default-off/explicit-opt-in and universal OIDC
wording in this plan. Session reuse choices default on where deployment policy permits,
with visible notice, reversible toggles, a fresh per-session/purpose grant under notice
`v2-default-on`, and separate explicit shared-copy creation. They are not affirmative
user consent clicks. Production retention/privacy approval remains mandatory.
Development sign-in may bypass OIDC only when explicitly enabled in nonproduction with
an explicit loopback server bind. Its separately namespaced shared identity, warnings,
sign-out clearing, and production prohibition remain mandatory. All normal/production
private-resource operations require OIDC and ownership checks.
Hosted/tracing acknowledgements default on and remain reversible; tracing itself is
operator-enabled only. No budget, query-validation, or production gate is relaxed.

Build a browser-based, question-driven analytics application for the supplied NYC-area airport datasets. LangChain provides the model integration layer for local Ollama and, when configured, hosted providers. A model interprets an analyst's question into a structured analysis plan; application code validates the plan and compiles it into parameterized, read-only analytical queries. Reports combine verified results with explanatory narrative, tables, and charts. Analysts authenticate individually, retain private report history, and control session-scoped reuse consent. Hosted inference is allowed only with provider-use disclosure and a hard USD 10 per UTC calendar-month cap; LangSmith tracing is off by default.

## Technical Context

**Language/Version**: Python 3.12<br>
**Primary Dependencies**: Streamlit 1.32+ (browser UI and OIDC sign-in), DuckDB (CSV analytics), SQLite (local report/history/consent/usage ledger), LangChain (model/provider integration), Ollama (optional local inference provider), Pydantic (plan validation), Plotly (charts)<br>
**Storage**: Supplied CSVs remain the analytical source; DuckDB reads them locally. SQLite stores analyst-owned reports, consent/reuse events, and a monthly hosted-inference budget ledger. LangChain provider configuration selects a local model or an approved hosted model.<br>
**Testing**: pytest for unit/integration tests; Streamlit AppTest for interaction flows; browser-level tests for authentication, isolation, and exports where needed. Provider tests assert schema, query, privacy, cost-accounting, and evidence invariants rather than byte-identical prose.<br>
**Target Platform**: Python web application on a private, single host; analysts use a browser. The app may call a configured local inference runtime or hosted model provider. OIDC is used for analyst identity; it receives authentication traffic only, never analytical questions or source data.<br>
**Project Type**: Single browser-based application<br>
**Performance Goals**: No response-time, concurrency-throughput, availability, or high-availability SLA is specified. Record end-to-end latency for representative supported questions on the selected host and provider as a baseline only, not as an MVP pass/fail threshold. The single-host application must preserve committed SQLite state across a normal process restart and surface provider/application failures as actionable errors.<br>
**Constraints**: Hosted model inference charges must not exceed USD 10 per UTC calendar month; free plans are allowed, including providers whose terms permit product improvement using submitted content, when disclosed before hosted processing. The cap includes metered inference and LangSmith tracing, directly attributable provider-billed fees and taxes, and currency-conversion charges; assign charges to the UTC month in which the underlying request was accepted even if invoiced later. Exclude unrelated hosting costs. Enforce concurrent maximum-cost reservations before calls, including configured input/output token ceilings and current rates, and fail closed if costs cannot be bounded. Retry timeouts only on provider-confirmed non-acceptance; retain uncertain reservations until reconciled and account conservatively for partial responses. Accept only non-empty plain-text questions up to 2,000 Unicode code points after trimming. Minimize hosted payloads. Never execute model-generated SQL or grant models database access. Do not switch providers silently; redisclose before a call if the provider, model, or material data-use terms change. LangSmith tracing is off by default and requires explicit operator enablement and user-facing disclosure. Enforce analyst ownership on every history, report, and export operation. Keep no more than ten private reports per analyst. Shared reuse requires explicit, reversible session consent; previously reused content remains after withdrawal. Production shared reuse remains disabled until its documented retention/deletion policy, including backups, is approved. The MVP UI is English-only and requires keyboard-operable, programmatically labelled controls, visible focus, and status/error cues not conveyed by color alone.<br>
**Scale/Scope**: Fixed supplied datasets (approximately 28 MB total); four initial analytical areas—connectivity, delays, airlines, and aircraft—with weather data available as supporting context for delay questions. Single-host MVP; no live data ingestion, multi-host scaling, uptime target, or concurrency-throughput target.

## Constitution Check

### Before Design

| Principle | Check |
|---|---|
| Accurate, explainable analysis | PASS — local data catalog, validated query plans, deterministic query compilation, and report caveats/provenance are in the design. |
| Data quality and provenance | PASS — source snapshots, join validation, missingness checks, and explicit metric definitions are planned. |
| Question-driven analysis and explainability | PASS — analysts ask questions, receive complete answers, can ask follow-ups, and get concise explanations of relevant analytical terms. |
| Privacy and consent | PASS — OIDC identity, per-analyst server-side ownership checks, private history, explicit session consent, and withdrawal controls are planned. |
| Privacy-aware model processing | PASS — hosted processing is disclosed and minimized; the monthly budget is enforced before requests; tracing is disabled by default. |

No constitution violations or complexity exceptions are identified.

## Design Decisions

See [research.md](./research.md) for alternatives, rationale, evidence, and remaining operational risks.

1. Use Streamlit for a Python-first browser application with OIDC identity; keep authentication separate from analytics.
2. Use LangChain as a provider integration layer. Support Ollama locally and an explicitly configured hosted provider; choose a hosted provider only after evaluating the fixed 12-question golden set (three supported questions per analysis area), current free quotas/rates, data-use terms, and costs. A candidate must interpret at least 11 of 12 questions with the expected metric and scope; every generated numeric result must match independent calculations, and no invalid plan may be executed.
3. Require the model to return a JSON analysis plan validated against a fixed schema and application allowlists. Compile only validated fields into parameterized DuckDB `SELECT` queries; never run model-generated SQL or grant model database access.
4. Enforce a shared USD 10 UTC calendar-month ceiling on hosted inference (and any metered LangSmith tracing) using a persistent usage ledger and conservative per-request cost reservations. Include configured token ceilings, current rates, directly attributable provider-billed fees and taxes, and currency conversion; assign charges to the month the operation was accepted. Reject a request if its maximum estimated cost would exceed the remaining allowance.
5. Keep analytical data and user metadata separate: DuckDB for the CSVs, SQLite for private reports, consent/reuse events, and model usage accounting.
6. Choose tables and charts deterministically from validated result semantics; use models only for intent interpretation and evidence-grounded explanation.
7. Disclose provider and applicable product-improvement terms before hosted processing. Keep this notice distinct from consent for application FAQ/report reuse.
8. Disable LangSmith tracing unless explicitly enabled by the operator after user-facing disclosure; traces may contain prompts and report data.
9. Preserve consented shared material after withdrawal, but do not include analyst identity in shared FAQ content unless a separately disclosed purpose requires it. Keep the minimal consent event that authorized any retained shared copy. Do not enable production reuse until retention/deletion periods and procedures for identity mappings, reports, consent events, shared artifacts, and backups are approved.
10. Enforce a 2,000-code-point trimmed plain-text question limit before model invocation; provide an English-only MVP with keyboard-operable, labelled, visibly focused controls and non-color-only status/error cues.

## Project Structure

The following is the planned application structure; the current repository contains the source datasets and specification artifacts, not the application implementation.

```text
app.py
src/
  airport_analytics/
    auth.py
    config.py
    data/
      catalog.py
      loader.py
      validation.py
    analytics/
      model_client.py
      budget.py
      provider_policy.py
      plan_schema.py
      query_compiler.py
      execution.py
      metrics.py
    reports/
      generation.py
      rendering.py
      export.py
    history/
      repository.py
    consent/
      service.py
      repository.py
    observability/
      tracing.py
tests/
  unit/
  integration/
  browser/
source_data/
specs/001-airport-analytics-platform/
```

## Constitution Check (Post-Design)

| Principle | Check |
|---|---|
| Accurate, explainable analysis | PASS — the model proposes intent only; schema validation, allowlisted compilation, read-only execution, and result-grounded reporting form the evidence chain. |
| Data quality and provenance | PASS — snapshot hashes, source row counts, data-quality validation, and metric definitions are part of the data/report model. |
| Question-driven analysis and explainability | PASS — the analyst controls question flow and can inspect a complete, question-specific report. |
| Privacy and consent | PASS — user scoping is enforced server-side; consent is purpose- and session-scoped; prior reuse is retained only as disclosed and recorded. |
| Privacy-aware model processing | PASS — local or hosted model use follows a disclosed provider policy, a pre-call USD 10 monthly budget guard, minimized payloads, and no silent provider switch; LangSmith tracing is disabled by default. |

**Post-design result**: PASS. No constitution violations or complexity exceptions are identified. Hosted provider terms, provider-specific retention/product-improvement practices, budget-accounting accuracy, consent wording, shared-content retention, and applicable jurisdiction require review before production deployment.
