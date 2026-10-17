# Feature Specification: Interactive Airport Data Platform

**Feature Branch**: `001-airport-analytics-platform`

**Created**: 2026-10-17

**Status**: Draft

**Input**: User description: "Interactive Airport Data Platform. The platform should begin by
taking user questions and enabling dynamically rendered reports using the existing data and the question
from the user."

## Clarifications

### Approved amendment 2026-10-17: session defaults and development identity

The owner explicitly approved preserving default-on session reuse choices in both sign-in
modes and the guarded local development sign-in exception. This amendment supersedes earlier
default-off/explicit-opt-in wording in clarification history, user-story descriptions, and
edge cases below. Default selections are not evidence of an affirmative user click or a
legal determination of valid consent. Production reuse still requires approved retention
and privacy procedures. Shared copies still require a separate analyst action.
Hosted/tracing acknowledgement controls default on, remain visible and reversible, and do
not enable tracing, override deployment gates, or change provider/budget boundaries.

### Session 2026-10-17

- Q: Should each analyst’s last ten reports be private to that analyst, limited to the current browser, or shared with other users? → A: Private per-analyst history; only its creator can access saved reports.
- Q: Should analysts’ questions and generated reports be reused outside their private history to support FAQs and improve agent support, and if so, how? → A: Reuse identifiable questions and reports only with explicit user opt-in.
- Q: Should an analyst opt in separately for each question and report, or can one setting authorize future questions and reports to be reused? → A: One explicit opt-in per session applies only to questions and reports from that session.
- Q: Which formats should analysts be able to save or export a generated report in? → A: Both a PDF containing the complete report and CSV files containing the report's tabular results.
- Q: When should the analyst be asked to opt in to reuse questions and reports from a session? → A: Ask at the start of each session, before the first question; the analyst can decline and continue privately, opt in later, or turn reuse off at any time.
- Q: If an analyst turns consent off, what should happen to questions and reports already reused? → A: Keep content already reused; stop future reuse.
- Q: Should an external AI service process the analyst's question and selected data results? → A: Initial decision was local-only; superseded on 2026-10-17 by allowing hosted models under a monthly USD 10 inference-spend cap.
- Q: How should natural-language report generation work? → A: Use LangChain with local or hosted model integrations; hosted model inference is allowed only under the monthly cap and disclosed provider data-use terms.
- Q: Is a free-tier hosted model acceptable if the provider may use submitted content to improve its products? → A: Yes, provided the application clearly discloses this before hosted processing.
- Q: Should the USD 10 monthly hosted-model budget apply to the whole application deployment or separately to each analyst? → A: One shared cap for the whole deployment per UTC calendar month, so total application spend cannot multiply as analysts are added.
- Q: If the shared monthly budget is exhausted, should an analyst be able to explicitly switch to an already configured local model, or should question answering stop until the next budget period? → A: Stop hosted calls and offer an explicit switch to a configured local model; if none is available, explain that hosted question answering resumes next month.
- Q: Before a question or result is sent to a hosted provider that may use submitted content to improve its products, should analysts have to explicitly agree, or is a clear disclosure enough? → A: Clear disclosure before the first provider call in each session is enough; processing proceeds unless the analyst explicitly switches to a configured local model.
- Q: How should analysts sign in so the app can keep report history private to each person? → A: Require sign-in through an organization-configured OIDC identity provider.
- Q: Which charges should count against the shared USD 10 monthly cap for hosted model use? → A: Count all provider-billed inference and tracing charges, including applicable fees and currency conversion; exclude unrelated hosting costs.
- Q: If a hosted request times out and it is unclear whether the provider processed or charged it, should the app retry automatically? → A: Retry automatically only when the provider confirms the first request was not accepted.
- Q: What response-time target, if any, should the first usable report meet for a typical supported question? → A: Set no hard response-time target for the MVP; measure typical latency during model evaluation and revisit a target after trying the chosen model and host.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ask a Question and Get a Report (Priority: P1)

An analyst starts by asking a question in their own words about the available airport and flight
data. The platform interprets the question and generates a report tailored to it, using relevant
data and presenting the answer as an explanation with appropriate tables, comparisons, or
visualizations. Supported topics include airport connectivity, delays, airline comparisons, and
aircraft statistics.

**Why this priority**: Asking questions and receiving a tailored report is the primary entry point
and value of the platform.

**Independent Test**: Submit a clear question answerable from the available data and verify that
the report addresses it, uses relevant data, and explains the metrics and period it presents.

**Acceptance Scenarios**:

1. **Given** the available flight data is ready, **When** the analyst submits a question about
   airport connectivity, **Then** the platform generates a report that answers it using relevant
   flight data and identifies the period and metric definition.
2. **Given** the analyst submits a question comparing airline delays, **When** the report is
   generated, **Then** it presents a relevant comparison with its metric definition, observation
   counts, and appropriate visual or tabular support.
3. **Given** the analyst asks a question about aircraft statistics, **When** matching aircraft
   data is available, **Then** the report distinguishes aircraft characteristics from observed
   flight activity.
4. **Given** the current source-data cache is available, **When** the analyst asks an answerable
   question, **Then** the report uses that data state and identifies the relevant data coverage
   and quality limitations.
5. **Given** a hosted model provider is configured for the session, **When** the platform is about
   to send its first request to that provider, **Then** it has disclosed the provider and whether
   submitted content may be used to improve the provider's products, offers any configured local
   alternative, and sends only the minimum required context unless the analyst switches locally.
6. **Given** hosted model calls are subject to the monthly budget, **When** a request could exceed
   the remaining USD 10 limit, **Then** the platform blocks it before sending the request.
7. **Given** the deployment-wide monthly budget is exhausted, **When** the analyst continues
   exploring, **Then** the platform offers an explicit switch to an available configured local
   model or explains that hosted question answering will resume next month.

---

### User Story 2 - Refine a Report with a Follow-Up Question (Priority: P2)

An analyst asks a follow-up question to narrow, compare, or further explain a generated report
without having to restate the entire analysis request.

**Why this priority**: Follow-up questions make exploration interactive and allow analysts to
develop a useful report through natural conversation.

**Independent Test**: Generate a report, ask a follow-up that adds a supported constraint, and
verify that the new report reflects that constraint and retains relevant prior context.

**Acceptance Scenarios**:

1. **Given** a report has been generated, **When** the analyst asks a supported follow-up to
   restrict it to a particular airport, airline, or period, **Then** the platform produces an
   updated report that reflects the requested context.
2. **Given** a follow-up changes the scope of the analysis, **When** the updated report appears,
   **Then** its displayed context and metric definitions reflect the updated scope.

---

### User Story 3 - Understand the Report (Priority: P2)

An analyst reviews a generated report and can understand what data supports it, how its measures
are defined, and what limitations apply.

**Why this priority**: Clear definitions and evidence help analysts interpret generated results
without treating assumptions or incomplete source data as facts.

**Independent Test**: Ask a question that produces a metric or comparison and verify that the
report presents its definition, relevant period and population, and material data limitations.

**Acceptance Scenarios**:

1. **Given** a report includes a rate, average, or ranking, **When** the analyst reviews it,
   **Then** the platform explains the measure and identifies its relevant population or sample
   size.
2. **Given** a relevant analytical term appears in the report, **When** the analyst reads the
   report, **Then** the platform provides a concise explanation without requiring a separate
   request.
3. **Given** the analyst requests an export, **When** the report includes narrative and tabular
   results, **Then** the platform provides a PDF of the complete report and CSV files containing
   the report's tabular results.

---

### User Story 4 - Keep Reports Private and Control Reuse (Priority: P2)

An analyst can review their own recent reports and control whether their questions and reports
may be reused outside their private history.

**Why this priority**: Private history and explicit, controllable consent protect analysts' work
while supporting optional reuse for FAQs and system improvement.

**Independent Test**: Have two analysts create reports, verify each sees only their own ten most
recent reports, and verify declining or disabling reuse prevents further reuse without blocking
analysis.

**Acceptance Scenarios**:

1. **Given** multiple analysts have generated reports, **When** an analyst opens report history,
   **Then** only that analyst's ten most recent reports are available.
2. **Given** an analyst signs in, **When** the application identifies them, **Then** it uses their
   stable identity-provider issuer and subject to associate report history, not a mutable email
   address.
3. **Given** a new session begins, **When** the analyst is asked about reuse before submitting a
   question, **Then** they can decline and continue with private analysis.
4. **Given** the analyst opts in to reuse during a session and later turns reuse off, **When**
   subsequent questions and reports are created, **Then** that subsequent content is not reused
   outside the analyst's private history.
5. **Given** the analyst declines the initial prompt, **When** they opt in later during that same
   session, **Then** only questions and reports created while consent is active may be reused.

---

### User Story 5 - Handle Unsupported or Unclear Questions (Priority: P3)

An analyst asks an ambiguous question or one that cannot be answered from the available data and
receives clear guidance rather than an unsupported report.

**Why this priority**: Transparent handling of uncertainty prevents confident-looking reports
based on missing data or unclear intent.

**Independent Test**: Submit ambiguous and unsupported questions and verify that the platform
asks a focused clarification or explains the data limitation.

**Acceptance Scenarios**:

1. **Given** a question could reasonably refer to multiple measures or populations, **When** the
   analyst submits it, **Then** the platform asks a focused clarification before producing a
   definitive report.
2. **Given** a question requires information not present in the available data, **When** the
   analyst submits it, **Then** the platform identifies the missing information and does not
   fabricate a result.
3. **Given** the configured model provider is unavailable or the monthly hosted-inference budget
   is exhausted, **When** the analyst submits a question, **Then** the platform explains that
   model processing is unavailable and does not silently switch providers or exceed the budget.

### Edge Cases

- A selected combination of filters has no matching flights; the platform shows an empty state
  instead of misleading zeros or stale results.
- Delay values are missing for some flights; affected measures disclose the population used and
  do not count missing values as zero.
- An airport, airline, or aircraft code lacks a matching reference record; the flight remains
  identifiable as unmatched and is not silently attributed to another entity.
- Airline sample sizes differ substantially; the platform shows the counts so analysts can judge
  the comparison and does not imply reliability from rank alone.
- Ties occur in a ranking; tied entries are clearly represented.
- A question is ambiguous; the platform requests only the clarification needed to establish the
  intended measure, population, or scope.
- A question asks for information absent from the supplied data; the platform explains the
  limitation rather than inventing a result.
- The configured model provider is unavailable or the hosted-inference budget is exhausted; the
  platform reports that model processing is unavailable and does not silently switch providers or
  exceed the budget.
- A question is about to be sent to a hosted model; the platform has already disclosed which
  provider receives it and whether the provider may use submitted content to improve its products.
- After seeing the provider-use disclosure, an analyst may explicitly switch to a configured
  local model; otherwise hosted processing proceeds under the disclosed terms.
- A proposed hosted request could exceed the monthly budget, or provider usage cannot be reliably
  estimated; the application blocks the request rather than risk exceeding the cap.
- A hosted request times out; the application retries automatically only if the provider confirms
  the original request was not accepted, and it reserves the retry's maximum charge before sending.
- The shared monthly budget is exhausted; hosted calls stop, and the analyst may explicitly
  select an available configured local model. If none is configured, the platform explains that
  hosted question answering will resume in the next UTC calendar month.
- LangSmith tracing is not explicitly enabled; no prompts, results, or report data are sent to it.
- A follow-up changes or contradicts prior context; the platform makes the active scope clear
  instead of silently applying conflicting filters.
- An analyst has not opted in to reuse of their questions or reports; that content remains in
  their private history and is excluded from shared FAQs and improvement activities.
- An analyst opts in after creating reports; content created before consent became active is not
  reused.
- An analyst has opted in during one session but not a later session; only content from the opted-in
  session may be reused.
- An analyst turns off and later re-enables reuse during a session; only content created while
  consent is active may be reused.
- An analyst turns consent off after content has already been reused; previously reused content
  remains in shared materials, while no further content is reused.
- An analyst submits an empty, whitespace-only, malformed non-text, or more than 2,000-character
  question; the application rejects it before any model call or hosted-budget reservation.
- A hosted response is partial or a provider invoice arrives after the UTC month containing the
  request; usage is conservatively reconciled and charged to the month in which the request was
  accepted.
- A provider, model, or material data-use term changes during a session; the updated disclosure
  appears before the next hosted request.
- A normal application restart occurs while analysts have saved reports or usage reservations;
  committed SQLite state remains available, while no higher availability guarantee is implied.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The platform MUST let an analyst submit a natural-language question about the
  available airport and flight data as the primary starting point for analysis.
- **FR-002**: For an answerable question, the platform MUST generate a report tailored to the
  question using relevant available data, rather than requiring the analyst to select a
  preconfigured analysis first.
- **FR-003**: The platform MUST maintain a current cached state of available source data, including
  its coverage and data-quality context, to support question analysis, documentation, agent
  support, system improvement, and user FAQs.
- **FR-004**: A generated report MUST choose relevant narrative, tables, and visualizations to
  address the question and MUST make no unsupported claim beyond the available data.
- **FR-005**: The platform MUST allow an analyst to refine or extend a report with a follow-up
  question using relevant prior context, and MUST make the resulting analysis scope visible.
- **FR-006**: For ambiguous questions that could materially change the result, the platform MUST
  ask a focused clarification about the intended measure, population, or scope before presenting
  a definitive answer.
- **FR-007**: When a question cannot be answered from available data, the platform MUST explain
  what is unavailable and MUST NOT fabricate values, sources, or conclusions.
- **FR-008**: Every reported measure MUST identify its definition, unit where applicable,
  population, time period, and numerator or denominator when relevant. Rates and averages MUST
  identify their observation population.
- **FR-009**: Connectivity reports MUST distinguish distinct destinations from flight volume and
  MUST identify the routes supporting a destination count.
- **FR-010**: Delay reports MUST distinguish departure from arrival delays, disclose missing-delay
  handling, and MUST NOT present missing observations as zero.
- **FR-011**: Airline comparisons MUST show the selected ranking measure and corresponding flight
  count. Ties MUST be represented clearly, and rankings alone MUST NOT be described as proof of
  statistically significant or conclusive performance differences.
- **FR-012**: Aircraft reports MUST distinguish aircraft characteristics from observed flight
  activity and identify records with unmatched or unavailable aircraft details.
- **FR-013**: The platform MUST allow analysts to refine report scope by supported dates, airports,
  airlines, and aircraft, whether those constraints are included in the original question or
  provided as a follow-up.
- **FR-014**: Reports MUST show the active period and other material scope constraints, and MUST
  identify the geographic coverage represented by the available data without implying live or
  broader coverage.
- **FR-015**: The platform MUST provide a clear no-results state when a question or its constraints
  match no records and MUST NOT present stale results as if they answered the current question.
- **FR-016**: The platform MUST explain relevant analytical terms concisely when they arise, without
  requiring the analyst to ask.
- **FR-017**: The platform MUST maintain the last ten generated reports separately for each
  analyst, and only the analyst who created a report MUST be able to access it in their history.
- **FR-018**: When an analyst requests an export, the platform MUST provide a PDF containing the
  complete report and CSV files containing the report's tabular results.
- **FR-019**: Shared FAQ/system-improvement copies MUST require an active session/purpose
  grant and an explicit create-copy action. Eligible purposes default on where deployment
  policy permits; the audit notice MUST distinguish default selections from affirmative opt-in.
- **FR-020**: Before the first question, the platform MUST visibly explain default-on optional
  reuse and permit disabling it without preventing private analysis. Re-enabling later MUST
  be possible. Deployment-disabled purposes MUST remain off.
- **FR-021**: Session-level consent MUST apply only to questions and reports created while consent
  is active. Each new session MUST establish its own disclosed choices and grant records. The analyst
  MUST be able to turn reuse off or back on at any time; content created while consent is off MUST
  remain excluded from shared FAQs and system improvement.
- **FR-022**: Turning consent off MUST stop future reuse but MUST NOT remove content already reused
  in shared FAQs or system-improvement materials.
- **FR-023**: Before a session grant is recorded, the consent explanation MUST disclose that previously
  reused content remains in shared materials if the analyst later turns reuse off.
- **FR-024**: The platform MUST use LangChain-supported model integrations and MAY use local or
  hosted models. Across the entire application deployment, hosted model inference MUST use a free
  plan or have total metered inference charges no greater than USD 10 per UTC calendar month.
- **FR-025**: The platform MUST enforce the hosted-inference budget before each request, account
  for concurrent in-flight requests, record usage and estimated or provider-reported charges, and
  block a request whenever its maximum possible charge would exceed the deployment-wide USD 10
  limit for the UTC calendar month. The cap applies to hosted model inference and any metered
  LangSmith tracing, including directly attributable provider-billed fees and taxes and currency-
  conversion charges; unrelated hosting costs are excluded. Charges are assigned to the UTC
  calendar month in which the underlying inference or tracing request was accepted, even if the
  provider invoices them later. Before a paid request, the platform MUST bound cost using the
  configured input/output token ceilings, current rate card, and applicable fees. The platform MAY
  retry a timed-out hosted request automatically only when the provider confirms the original
  request was not accepted, and MUST reserve the retry's maximum charge before sending it. A
  partial response MUST be reconciled using provider-reported usage or a conservative estimate.
  If acceptance or cost cannot be determined reliably, the platform MUST fail closed for further
  paid hosted inference and retain the uncertain request's reservation until reconciled. Free-tier
  quotas MUST also be respected. When the cap is exhausted, hosted calls MUST stop; the analyst
  MAY explicitly select an available configured local model, otherwise the platform MUST explain
  that hosted question answering resumes in the next UTC calendar month. If reconciled provider
  charges exceed the reserved estimate, the ledger MUST record the actual charge and block further
  paid hosted calls for that UTC month if the remaining allowance is exhausted; the incident MUST
  be surfaced to the deployment operator.
- **FR-026**: The model MUST return a structured analysis plan. Application code MUST validate
  that plan against its schema and allowlists and compile it into parameterized, read-only
  analytical queries. The model MUST NOT receive database credentials or unrestricted query
  execution, and model-generated SQL MUST NOT be executed.
- **FR-027**: The application MUST minimize information sent to hosted models to the current
  question, the minimum active structured analysis context needed for a follow-up, and necessary
  schema/metric context for plan generation; narrative generation MAY receive validated aggregate
  results and metric definitions. It MUST NOT send raw source records, analyst identifiers,
  credentials, or saved/private report history.
- **FR-028**: Before the first hosted model call to each provider in a session, the application
  MUST disclose that provider and whether its terms allow submitted content to be used for product
  improvement and MUST offer a switch to a configured local model when available. The disclosure
  is not a separate opt-in requirement: unless the analyst explicitly switches locally, processing
  may proceed under the disclosed provider terms. This disclosure MUST be distinct from the
  platform's consent for FAQ or system-improvement reuse. Before a later hosted call, the
  application MUST show an updated disclosure if the provider, model, or material data-use terms
  have changed during the session.
- **FR-029**: If the configured provider is unavailable, the application MUST report the failure
  and MUST NOT silently switch to another local or hosted provider. A provider change must be an
  explicit configuration or analyst action and remain subject to disclosure and budget controls.
- **FR-030**: LangSmith tracing MUST be disabled by default. It MAY be enabled only through
  explicit operator configuration and user-facing disclosure that traces may contain questions,
  schema context, aggregate results, or report text. Any metered tracing charge MUST count toward
  the USD 10 monthly AI-service cap.
- **FR-031**: Analysts MUST authenticate through an organization-configured OpenID Connect
  identity provider before using private report history or other analyst-specific resources. The
  application MUST identify an analyst by the provider issuer and stable subject, not by mutable
  email address, and MUST enforce ownership on every private-resource operation.
  Approved exception: explicitly enabled, nonproduction, explicitly loopback-bound development
  sessions MAY use one separately namespaced shared developer identity. This is not real
  authentication; the UI MUST disclose shared history, prohibit production and non-loopback
  use, and warn against proxy/tunnel exposure. Normal and production sign-in still require OIDC.
- **FR-032**: The platform MUST accept a non-empty plain-text question of at most 2,000 Unicode
  code points
  after trimming surrounding whitespace. It MUST reject an empty or oversized question
  before any model-provider call or hosted-budget reservation.
- **FR-033**: The MVP user interface MUST be in English. All interactive controls MUST be
  keyboard-operable, have programmatic labels, provide a visible keyboard-focus indicator, and
  communicate status and errors without relying on color alone.
- **FR-034**: The single-host MVP has no availability, high-availability, or concurrency-throughput
  SLA. Provider and application failures MUST be shown as actionable errors. A normal application
  process restart MUST preserve committed SQLite report, consent, and model-usage records.
- **FR-035**: Before production deployment enables shared FAQ or system-improvement reuse, the
  deployment owner MUST approve and document retention periods and deletion procedures for analyst
  identity mappings, private reports, consent audit events, shared artifacts, and their backups.
  If that policy is not approved, production shared reuse MUST remain disabled.
- **FR-036**: Reports involving reference-data or weather joins MUST disclose matched and unmatched
  record counts and the matching coverage for the relevant population. There is no universal
  minimum join-coverage threshold; weather context may be included only after validating the
  temporal/key matching rule, and MUST be presented as association rather than causation.

### Key Entities

- **Flight**: A recorded flight with a date, origin, destination, airline, timing and delay
  observations, and optional aircraft identifier.
- **Airport**: An airport identified by a code and, where available, descriptive and geographic
  attributes.
- **Airline**: A carrier associated with recorded flights and used to group comparative measures.
- **Aircraft**: An aircraft or aircraft model with available reference characteristics and a
  possible relationship to flights through an aircraft identifier.
- **Analytical Question**: A user's natural-language request that specifies or implies an
  analytical topic, measure, population, or comparison.
- **Generated Report**: A question-specific response containing findings, metric definitions,
  supporting tables or visualizations, and relevant limitations.
- **Analysis Context**: The active period, airports, airlines, aircraft, and other material
  constraints used to answer the current question and any follow-up.
- **Analyst Identity**: A distinct user identity used to associate report history with its
  creator and restrict access to that analyst.
- **Content Reuse Consent**: An analyst's explicit, session-scoped authorization to reuse
  questions and reports created while consent is active during that session outside their private
  history for shared FAQs or system improvement.
- **Model Usage Reservation**: A record reserving the maximum bounded charge for an in-flight
  hosted model or tracing operation against the deployment-wide UTC calendar-month cap, then
  reconciling it with provider-reported usage or a conservative estimate.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: At least 4 of 5 test analysts can submit a clear question answerable from the
  available data and identify the generated report as addressing that question without help.
- **SC-002**: In acceptance testing, reports for tested questions across all four supported
  analysis areas agree with independently checked results for the same data and scope. The
  provider-selection corpus contains 12 fixed supported questions (three per analysis area) with
  independently recorded expected metrics and scope; a candidate model MUST correctly interpret
  at least 11 of 12, and every generated numeric result MUST match its independent calculation.
- **SC-003**: Every tested generated report identifies relevant metric definitions, units where
  applicable, population, and period, and discloses material data limitations.
- **SC-004**: At least 4 of 5 test analysts can use a follow-up question to refine a report and
  correctly identify the resulting analysis scope.
- **SC-005**: Ambiguous and unanswerable questions, empty results, ties, missing observations,
  unmatched reference records, and reuse opt-out are handled according to the stated edge cases
  in acceptance tests.
- **SC-006**: In task-based acceptance testing, at least 4 of 5 analysts can locate a relevant
  finding and explain its metric definition and key limitation from its report.
- **SC-007**: Acceptance testing confirms each analyst can access only their ten most recent
  reports, decline reuse while continuing analysis, and turn reuse off during a session.
- **SC-008**: Budget tests confirm that concurrent hosted requests and metered tracing cannot
  authorize more than USD 10 in maximum reserved charges for a UTC calendar month, and that
  paid requests are blocked when cost cannot be bounded. Tests also confirm retries occur only
  after provider-confirmed non-acceptance, uncertain reservations remain held until reconciliation,
  and accepted-month cost attribution is preserved when invoices arrive later.
- **SC-009**: Acceptance tests confirm provider data-use disclosures appear before hosted
  processing, remain distinct from application reuse consent, and third-party model tracing is
  off by default.
- **SC-010**: Model evaluation records end-to-end response times for a representative set of
  supported questions on the selected host and provider; these measurements establish a baseline
  but are not subject to a hard MVP pass/fail threshold.
- **SC-011**: Restart acceptance testing confirms committed reports, consent events, and budget
  reservations remain available after a normal application-process restart; no uptime or
  high-availability target applies to the MVP.
- **SC-012**: Accessibility acceptance review confirms every analyst-facing interactive control
  is keyboard-operable, programmatically labelled, visibly focused when navigated by keyboard,
  and has status/error information that is not conveyed by color alone.

## Assumptions

- The initial experience is for analysts exploring the supplied historical NYC-area flight data;
  it is not a live flight tracking service.
- The supplied flight records represent 2013. The platform will use the actual date coverage
  confirmed from the data and will not imply a different period.
- Airport, airline, and aircraft reference data are used only where their identifiers can be
  matched reliably to flight records.
- The four analysis areas are the question-answering scope of the initial experience. New data
  sources, live updates, and additional analytical domains are outside this specification.
- Weather data may be used as supporting context for delay questions, but weather analysis is not
  a separate fifth analysis area. Any weather association must disclose data matching limitations
  and must not be presented as proof of causation.
- Reports are generated from the user's question and supplied data; the user is not required to
  navigate a fixed dashboard before asking a question.
- The source data may omit values or reference matches. The platform will disclose those limits
  rather than infer unavailable facts.
- Metric thresholds and ranking definitions not prescribed by the source data will be stated
  transparently and treated as analysis definitions, not inherent facts.
- Turning off consent stops future reuse of that session's content. Content already reused remains
  in shared FAQs or improvement materials, as stated in FR-022 and disclosed before opt-in.
- The MVP has no hard question-to-report latency target; evaluation records response-time
  measurements to inform a later target.
- There is no universal join-coverage pass threshold; reports disclose the relevant matched and
  unmatched counts and coverage, and weather context requires a validated matching rule.
- Production shared reuse is unavailable until the retention/deletion policy in FR-035 is approved.
