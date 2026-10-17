# Research: Interactive Airport Data Platform

## Decisions

### Owner-approved amendment, 2026-10-17

The specification's approved session-default/development-identity amendment supersedes
earlier rejected-default/explicit-opt-in and universal-OIDC decisions below. Reuse defaults
are disclosed default selections, not affirmative user consent, and require privacy review
before production. Loopback-only nonproduction sign-in is an explicitly approved development
exception, never production authentication. Provider acceptance, retention approval,
accessibility review, latency measurement, and real analyst outcomes remain unverified
until their evidence is recorded; automated/mocked tests do not establish these outcomes.

### 1. Browser application and analyst identity

**Decision**: Use a single Python/Streamlit application with OIDC sign-in through `st.login`/`st.user`. Derive the stable analyst key from the identity provider's issuer and subject, not a mutable email address. Require authentication before showing private reports or allowing exports. Enforce ownership in repository/service operations, not only in the UI.

**Rationale**: The product is a question-driven report application with a Python analytics and model-integration stack. Streamlit provides a direct browser interaction model and native OIDC support. Stable identity claims support private report history across sessions. OIDC traffic is limited to authentication; questions, CSV data, and report content are not sent to the identity provider.

**Alternatives considered**:
- FastAPI plus a separate JavaScript client: more UI flexibility, but adds a second application stack without a current requirement for it.
- Shared or anonymous access: simpler for a demo, but cannot reliably isolate reports and exports per analyst.
- Directly keying ownership by email: rejected because email can change and may not be a stable identity claim.

**Evidence**: [Streamlit authentication documentation](https://docs.streamlit.io/develop/concepts/connections/authentication) documents OIDC login and user information. Its authentication configuration and identity provider remain deployment settings.

### 2. Model integration, structured output, and provider choice

**Decision**: Use LangChain as the model integration layer, supporting Ollama locally and a configured hosted provider when desired. Do not lock the design to a particular hosted vendor yet: evaluate candidates against 12 fixed supported questions (three per analysis area), with independently recorded expected metrics and scope. A candidate must interpret at least 11/12 with the expected metric and scope; any invalid plan is rejected, and every generated numeric result must match the independent calculation. Also check structured-output compatibility, free-tier quotas/rates, data-use terms, retention, and performance. Hosted inference may use a free plan even when provider terms allow submitted content to improve products, provided the applicable provider/model terms are disclosed before processing and redisclosed before a call after material changes.

**Rationale**: LangChain allows consistent model invocation and structured-output handling across local and hosted integrations. This supports evaluating a free or low-cost hosted model without redesigning report generation. The framework is not the model, does not make hosted calls free, and does not replace application validation or accounting.

**Alternatives considered**:
- Direct provider SDK: fewer dependencies and simplest if only one provider is ever used; less convenient for comparing local and hosted providers.
- Ollama-only: avoids token charges and external question processing but constrains model performance to local hardware and local model capability.
- Agent with database tools: rejected. The model must never have query-execution capability or unrestricted database access.

**Evidence**: [LangChain model integrations](https://docs.langchain.com/oss/python/langchain/models) documents common model interfaces and structured output; [LangChain Ollama integration](https://docs.langchain.com/oss/python/integrations/chat/ollama) documents the local adapter. [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing) documents that free-tier access may use submitted content to improve products; terms vary by provider and tier and must be checked at selection time.

### 3. Hosted-inference budget and data-use boundary

**Decision**: Apply a hard USD 10 ceiling per UTC calendar month to hosted model inference and any metered LangSmith tracing. Before every paid hosted request, reserve a conservative maximum cost based on current rates, configured input/output token ceilings, directly attributable provider-billed fees and taxes, and currency conversion; include in-flight reservations in the available-budget calculation. Attribute charges to the month in which the operation was accepted even if invoiced later. Reconcile reservations with provider-reported usage or conservative estimates afterward; account conservatively for partial responses. Retry only after the provider confirms non-acceptance, and retain uncertain reservations until reconciliation. Block requests when the ceiling could be exceeded or cost cannot be bounded. Enforce free-tier rate and quota limits separately. Never switch providers silently.

Before hosted inference begins in a session, disclose the configured provider/model and whether its applicable terms permit submitted content to be used to improve products. Update the disclosure before a call when the provider, model, or material data-use terms change. This notice is distinct from the platform's FAQ/report reuse consent. Minimize hosted payloads to the current question, minimal active structured context for a follow-up, and schema needed to generate a plan; narrative generation may receive validated aggregate results. Do not send source rows, credentials, analyst identifiers, or saved/private report history.

**Rationale**: The cost limit is an explicit product constraint, not an expected average. Reserving worst-case request cost prevents concurrent calls from spending the same remaining allowance. A separate provider-use disclosure makes third-party processing visible even if no fee is charged.

**Alternatives considered**:
- Monitor invoices after the fact: rejected because it cannot prevent an over-cap month.
- Estimate typical request cost without reservations: rejected because retries, output length, and parallel requests can exceed the estimate.
- Treat FAQ/reuse consent as permission to disclose to a model provider: rejected; provider processing is a separate purpose and disclosure.

### 4. LangSmith observability

**Decision**: Keep LangSmith tracing disabled by default. Enable it only through explicit operator configuration and user-facing disclosure that traces may contain questions, schema context, aggregate results, or generated report text. Any metered tracing charges share the USD 10 monthly ceiling. Do not enable automatic tracing in tests or production configuration by default.

**Rationale**: Traces can be useful when diagnosing provider behavior, but they can retain the same sensitive content as model prompts and answers. Opt-in avoids exporting content as an accidental side effect of enabling LangChain.

**Alternatives considered**:
- Always-on remote traces: rejected due to unnecessary prompt/result disclosure and possible charges.
- Local structured application logs without prompt bodies: suitable default operational diagnostics; keep them minimized and avoid private question text.

### 5. Safe analytics-query generation

**Decision**: The model returns a typed analysis plan containing an allowlisted metric, dimensions, filters, time bounds, and presentation intent. Validate every identifier, operator, value type, range, and result limit in application code. Compile the plan into parameterized DuckDB `SELECT` statements and reject invalid or unsupported plans. Never execute SQL text from the model.

**Rationale**: A small fixed schema and dataset make an application-owned query compiler practical. The application can guarantee the model cannot introduce DDL/DML, arbitrary tables, or unbounded query shapes. Explicit validation also makes query behavior independently unit-testable.

**Alternatives considered**:
- Model-generated SQL followed by a text check: rejected because substring checks are not a reliable SQL safety boundary.
- Grammar-constrained raw SQL: potentially more expressive, but requires a schema-specific SQL grammar and still needs semantic authorization and resource controls.

**Validation controls**: allowlisted catalog; parameter binding; local read-only analytical access; bounded result rows and execution time; explicit joins; safe failure for unsupported operations. The compiler, rather than the model, owns SQL construction.

### 6. Data access, schema context, and report evidence

**Decision**: Use DuckDB locally to query the fixed CSV files. Validate file presence, headers, types, row counts, missingness, and join-key coverage at load/initialization. Supply a compact, versioned schema/metric glossary to the configured model rather than raw datasets. Keep report calculations and displayed values derived from query results; use the model only to interpret the question and explain those results.

**Rationale**: The dataset is small and fixed, so a local analytical engine avoids a remote database dependency. Schema and glossary context is enough for the model to choose known metrics without sending large row-level data into prompts. Snapshot metadata enables reproducibility as source files change. The model remains outside the query execution boundary regardless of provider.

**Alternatives considered**:
- Load all CSV rows into each model prompt: rejected for context size, privacy, and factuality.
- Retrieval-augmented generation over the data: unnecessary for a small tabular dataset; consider only if the data catalog grows materially.
- Use charts narrated without query/result provenance: rejected because narrative claims need to be grounded in computed evidence.

**Evidence**: The provided repository data comprises 277,977 flight records and reference/context files for airports (1,458 rows), airlines (16), aircraft (3,322), and weather (26,112). Validate counts and join semantics against the files during implementation rather than hard-coding assumptions.

### 7. Visualization and narrative

**Decision**: Select chart type in application code from the validated question intent and result shape (for example, time series to line chart, category comparisons to bar chart, and detailed rows to a table). Generate narrative from validated results and metric definitions, include caveats, and test that reported numeric claims agree with the result. If a useful chart cannot be justified by the result shape, present a table.

**Rationale**: Deterministic rendering avoids arbitrary or misleading chart specifications from a language model. Keeping narrative separate from query execution makes factual claims easier to verify.

**Alternatives considered**:
- Let the model generate chart code or arbitrary chart JSON: rejected due to safety and correctness risks.
- Always render the same chart type: rejected because it does not suit all report shapes.

### 8. Private report history and consent persistence

**Decision**: Store per-analyst report history in SQLite and enforce analyst ownership on every read, update, delete, and export. Retain at most ten private reports per analyst; remove older private report records, while keeping a separate shared-reuse artifact only when it was created under an active, recorded consent. Maintain minimal append-only consent events with session, purpose, action, timestamp, and notice version. Shared content is not retroactively removed when consent is withdrawn, but future reuse stops until consent is enabled again.

**Rationale**: This implements the clarified privacy and history behavior while making session consent auditable. Keeping private history separate from shared material allows the ten-report cap without silently deleting previously reused material.

**Alternatives considered**:
- Consent inferred from a browser default or continued use: rejected; consent must be explicit.
- Delete all previously reused material on withdrawal: rejected because the product decision is to stop future reuse while retaining already reused content.
- Treat consent as a permanent analyst preference: rejected because the specified scope is session-level and can change during that session.

**Risk/production gate**: The consent notice, retained shared-content behavior, and consent-event retention must receive jurisdiction-appropriate privacy/legal review before production. This plan makes no legal-compliance claim. Shared content should not expose analyst identity unless that specific disclosure is separately explained and authorized.

### 9. Testing strategy

**Decision**: Use layered tests: compiler allowlist and injection-shaped input tests; CSV/schema/join validation; golden natural-language questions covering the four analytical areas; clarification and unsupported-question cases; result-to-report evidence checks; provider disclosure; budget reservation, concurrency, reconciliation, and hard-stop behavior; free-tier quota handling; consent transitions; cross-analyst history/export isolation; tracing-off-by-default; and export integrity. Test model outputs by schema and semantic invariants rather than exact generated prose. Verify provider unavailability never triggers an unannounced provider switch.

**Rationale**: Local model generation can vary between hardware/runtime versions. Structural, execution, and evidence invariants measure the real behavior without brittle text snapshots.

### 10. MVP response-time evaluation

**Decision**: Set no hard question-to-report latency target for the MVP. After selecting the host and model provider, record end-to-end response times for a representative set of supported questions and document the benchmark method and results. Use the baseline to decide whether a measurable target is appropriate later.

**Rationale**: Local hardware, provider load, and model choice materially affect response time, and no validated deployment environment is established yet. A measured baseline provides evidence for future service targets without making an unsupported promise now.

**Alternatives considered**:
- Impose a fixed response-time threshold before the deployment host and provider are evaluated: rejected because it would be arbitrary and may not reflect the intended deployment.
- Omit response-time measurement: rejected because it would leave no evidence to inform an operational target.

### 11. Input, accessibility, availability, and retention boundaries

**Decision**: Reject empty or whitespace-only input and questions longer than 2,000 Unicode code points after trimming before any model call or budget reservation. The MVP is English-only and requires keyboard-operable controls, programmatic labels, visible focus, and status/error messages that do not rely on color alone. Define no uptime, high-availability, or concurrency-throughput SLA; provider/application failures remain actionable, and committed SQLite state survives a normal process restart. Keep production shared reuse disabled until approved retention/deletion periods and procedures cover identity mappings, private reports, consent events, shared artifacts, and backups.

**Rationale**: A clear input boundary limits accidental prompt/cost growth; basic interaction accessibility is part of a usable browser experience. Explicitly excluding service-level targets avoids implying infrastructure guarantees the single-host MVP cannot provide. A production gate prevents indefinite retention from being treated as an approved policy.

**Alternatives considered**:
- Leave question length and accessibility behavior entirely to framework defaults: rejected because the cost and usability boundary would be implicit.
- Enable production reuse before retention/deletion terms are approved: rejected because the platform has promised that previously reused material remains after consent withdrawal.

## Deployment Assumptions and Risks

- The MVP runs on one private host with local CSVs and SQLite state. High availability, horizontal scaling, uptime, and concurrency-throughput targets are unspecified and out of scope. A normal process restart must preserve committed SQLite state.
- OIDC requires a configured identity provider. Authentication traffic may leave the host. Hosted model traffic may leave the host only under the provider disclosure and budget rules above.
- The application can operate with a local Ollama model or an explicitly configured hosted provider. Provider changes require explicit configuration or analyst action; there is no silent fallback.
- Provider prices, free-tier eligibility, quotas, and data-use terms can change. Revalidate them at provider selection and monitor quotas and invoices. The monthly cap is enforced by the application and does not depend on provider billing alerts.
- Weather records are included as supporting context for delay analysis. The implementation must verify temporal alignment and matching coverage before presenting weather-related conclusions; do not imply causation from association alone.
- Source CSVs are treated as a fixed snapshot for the MVP. New or changed files require a refreshed snapshot identifier and data-quality validation.
