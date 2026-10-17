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
  is ownership-checked. Trusted local development can opt into a separate shared development
  identity without OIDC; this bypass is disabled by default, requires explicit loopback server
  binding, and is prohibited in production. See the [quickstart](./QUICKSTART.md).

## Product scope

The initial question-answering areas are airport connectivity, delays, airline comparisons, and
aircraft statistics. Weather may support delay analysis only; associations must not be described
as causal findings. The application uses the supplied historical snapshot, not live flight data.

Analysts can refine reports with follow-up questions. Private history retains at most each
analyst's ten most recent reports. Reports can be exported as a complete PDF and their tabular
results as CSV. Distinct-destination reports also provide supporting routes and a separate
route CSV, with an explicit warning if the 500-row evidence bound truncates the table.
Periods describe observed dates within the effective filters; reference/weather coverage
uses that filtered population before match-only exclusions. PDFs include active scope and
supporting evidence, and rankings disclose ties crossing the result limit.

Reuse choices are purpose-specific, reversible, and session-scoped. Under the owner-approved
requirements amendment, permitted purposes start enabled with a visible notice and off switch
in all sign-in modes. Declining does not block analysis; choices can be enabled later or
withdrawn. Default selection is not affirmative legal consent. Previously reused material
remains after withdrawal. Production shared reuse stays disabled until retention and deletion
periods and procedures, including backup handling, are approved by the deployment owner.

Local development sign-in enables default-on FAQ and system-improvement controls for testing.
Creating a shared report copy still requires its separate explicit action. FAQ copies can be read
under **Shared FAQs** and their questions reused as new inputs. Remote-model access still
requires configured credentials, processing disclosure, and budget authorization.

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

The [acceptance quickstart](./specs/001-airport-analytics-platform/quickstart.md#provider-acceptance-and-latency-commands)
documents the opt-in live-evaluation commands and outstanding external evidence. The retention
worksheet, analyst protocol, and partial accessibility review are not completed release approvals.

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
session token-usage report. An account-level Copilot usage export is now available, but it reports
AI credits rather than tokens and contains no repository/workflow attribution. Its credit quantity
is recorded below as account-level context only; input/output token counts remain unavailable and
are not estimated.

Keep this record distinct from the application's hosted-model usage ledger: runtime inference
usage and cost are tracked by the application against the monthly USD 10 cap, while this section
records tokens used to build the solution.

| Date / work period | Implementation phase or task IDs | Usage source / model | Input tokens | Cached input tokens | Output tokens | Total tokens | Notes |
|---|---|---|---:|---:|---:|---:|---|
| 2026-10-17 | Account-level Copilot usage export; not attributable to this repository | Copilot AI credits (not token counts) | — | — | — | — | 167.0928263 credits; gross USD 1.670928157, fully discounted (net USD 0). Repository and workflow fields are blank in the export. Token usage for this implementation remains unavailable. |
| 2026-10-17 | Convergence implementation, T063-T079 | No new authoritative project/session usage export supplied | — | — | — | — | Report evidence, source integrity/freshness, budget uncertainty/alerts, approved requirements exceptions, restart tests and release tooling. No token estimate or attribution of the prior account-wide credits. External acceptance evidence remains pending. |
