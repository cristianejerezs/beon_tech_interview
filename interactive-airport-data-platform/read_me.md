# Interactive Airport Data Platform

## Overview

The Interactive Airport Data Platform is a planned browser-based analytics application for
exploring the supplied historical NYC-area airport datasets through natural-language questions.
It will turn supported questions into evidence-grounded reports with explanatory text, tables,
and appropriate charts.

**Current status:** Implementation has progressed through the core analytics, report, history,
consent, export, and UI flows. Provider/model acceptance evaluation and external release gates
remain outstanding; the task breakdown and acceptance expectations are in
[`specs/001-airport-analytics-platform/tasks.md`](./specs/001-airport-analytics-platform/tasks.md).

## Planned solution

- **User interface:** Streamlit application for analyst question entry, reports, follow-ups,
  history, consent controls, and exports.
- **Data analytics:** DuckDB queries the local supplied CSV files. A versioned catalog defines
  allowed metrics, dimensions, filters, and joins; the application validates source snapshots
  and reports relevant data quality and coverage.
- **Question interpretation:** LangChain integrates an optional local Ollama model or an
  explicitly configured hosted provider. Hosted provider selection remains a deployment decision.
- **Safe query boundary:** Models return a structured analysis plan, never executable SQL.
  Application-owned schema/catalog validation and a deterministic compiler produce parameterized,
  read-only DuckDB queries. Models receive no database credentials, raw source rows, or query
  execution tools.
- **Report evidence:** Calculations and numeric results come from validated query results.
  Narratives, metric definitions, scope, counts, and limitations must agree with those results.
- **Persistence and identity:** SQLite stores private reports, consent events, and hosted-usage
  reservations. OIDC identifies analysts by stable issuer/subject claims; every private resource
  is ownership-checked.

## Product scope

The initial question-answering areas are airport connectivity, delays, airline comparisons, and
aircraft statistics. Weather may support delay analysis only; associations must not be described
as causal findings. The application uses the supplied historical snapshot, not live flight data.

Analysts can refine reports with follow-up questions. Private history retains at most each
analyst's ten most recent reports. Reports can be exported as a complete PDF and their tabular
results as CSV.

Reuse of questions or reports outside private history requires explicit, reversible,
session-scoped consent. Declining does not block analysis; consent can be enabled later or
withdrawn. Previously reused material remains after withdrawal. Production shared reuse stays
disabled until retention and deletion periods and procedures, including backup handling, are
approved by the deployment owner.

## Privacy, safety, and budget constraints

- Hosted processing requires disclosure of the provider/model and material data-use terms before
  the call. Updated disclosure is required if those details materially change during a session.
- Hosted inference and any metered LangSmith tracing share a deployment-wide **USD 10 cap per UTC
  calendar month**. The cap includes directly attributable provider fees/taxes and currency
  conversion, but excludes unrelated hosting costs. Free-tier quotas also apply.
- The application reserves maximum possible charges before paid hosted calls, counts concurrent
  reservations, retries only after provider-confirmed non-acceptance, and retains uncertain
  reservations until reconciled. It fails closed when cost or acceptance cannot be established.
- LangSmith tracing is off by default. Provider changes and local-model switches are never silent.
- Questions must be non-empty plain text and no longer than 2,000 Unicode code points after
  trimming surrounding whitespace. Invalid input is rejected before model invocation or budget
  reservation.
- The MVP is English-only, with keyboard-operable controls, programmatic labels, visible keyboard
  focus, and status/error cues that do not rely on color alone.
- The single-host MVP has no uptime, high-availability, or concurrency-throughput SLA. Committed
  SQLite state must survive a normal application-process restart, and failures must be actionable.
- There is no hard MVP response-time threshold. Measure representative end-to-end report latency
  on the selected host/provider and record a baseline for future target-setting.

## Quality gates

1. Establish a fixed golden set of 12 supported questions (three per analysis area) with
   independently calculated expected metrics and scope. A candidate model must interpret at least
   11 of 12 correctly; generated numeric results must match independent calculations.
2. Validate schema, metric/dimension/filter allowlists, parameterization, read-only behavior,
   bounded execution, and safe rejection of invalid plans.
3. Verify ownership isolation, ten-report retention, consent transitions, and PDF/CSV exports.
4. Exercise concurrent budget reservations, provider failures, retries, uncertain outcomes,
   reconciliation, late invoices, disclosure, and tracing defaults.
5. Run five anonymous analyst sessions; at least four of five must meet each of the first-question,
   follow-up-scope, and report-comprehension outcomes.
6. Review accessibility requirements and benchmark latency without imposing an MVP latency
   pass/fail threshold.

## Project documents

- [Feature specification](./specs/001-airport-analytics-platform/spec.md)
- [Implementation plan](./specs/001-airport-analytics-platform/plan.md)
- [Research decisions](./specs/001-airport-analytics-platform/research.md)
- [Data model](./specs/001-airport-analytics-platform/data-model.md)
- [Question/report contract](./specs/001-airport-analytics-platform/contracts/question-report.md)
- [Analysis-plan schema](./specs/001-airport-analytics-platform/contracts/analysis-plan.schema.json)
- [Quickstart and acceptance scenarios](./specs/001-airport-analytics-platform/quickstart.md)
- [Implementation tasks](./specs/001-airport-analytics-platform/tasks.md)
- [Feature-quality checklist](./specs/001-airport-analytics-platform/checklists/feature-quality.md)

## Implementation token-usage record

Implementation has started. The current environment does not provide an authoritative Copilot or
session token-usage report, so token counts are not available yet. Record only usage figures
available from the Copilot/session usage report or another authoritative meter; do not estimate or
invent token counts. Update this record at implementation milestones when authoritative figures
are available.

Keep this record distinct from the application's hosted-model usage ledger: runtime inference
usage and cost are tracked by the application against the monthly USD 10 cap, while this section
records tokens used to build the solution.

| Date / work period | Implementation phase or task IDs | Usage source / model | Input tokens | Cached input tokens | Output tokens | Total tokens | Notes |
|---|---|---|---:|---:|---:|---:|---|
| 2026-10-17 | Setup and implementation through UI/history/consent integration (T001–T050) | Authoritative usage report unavailable | — | — | — | — | Implementation milestone recorded; counts withheld rather than estimated. Update when an authoritative usage report becomes accessible. |
