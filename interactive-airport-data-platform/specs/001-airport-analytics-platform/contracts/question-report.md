# Question-to-Report Interaction Contract

## Analyst interaction

1. An analyst authenticates through the configured OIDC provider. The application identifies the analyst by stable issuer/subject claims.
2. Before the first question in an application session, the UI explains each shared-reuse purpose and asks for an explicit choice. Reuse starts disabled; the analyst can enable it later, disable it, or enable it again during that session.
3. The analyst enters a non-empty plain-text question of at most 2,000 Unicode code points after
   trimming surrounding whitespace and may ask follow-ups against the minimum active structured
   analysis context. Empty, non-text, or oversized input is rejected before model invocation or
   hosted-budget reservation.
4. The application returns either:
   - a complete report with an answer, supporting result table and/or appropriate chart, definitions, and relevant caveats;
   - one focused clarification question when the request is ambiguous; or
   - a clear explanation when the requested analysis is unsupported by available data.
5. Reports are private to the authenticated analyst. The history view contains up to the ten most recent reports. PDF export represents the full report; CSV export contains tabular results. Every history and export request is ownership-checked by the application.
6. Before the first hosted model call to each provider in a session, the application discloses the configured provider/model and whether its terms allow submitted content to improve products. It updates the disclosure before a call if provider, model, or material data-use terms change. If the configured provider cannot be reached or returns an invalid plan, the application reports an actionable error. It must not execute the invalid plan, silently switch providers, or exceed the monthly inference budget.

## Model boundary

- Input for plan generation: analyst question, bounded follow-up context, versioned schema/metric glossary, and the JSON Schema in [analysis-plan.schema.json](./analysis-plan.schema.json). Hosted requests send only the minimum needed context.
- Output: exactly one JSON analysis-plan object conforming to that schema.
- The model has no database credentials, filesystem access, or query-execution capability. It never receives raw source rows, analyst identifiers, credentials, or private report history.
- Model output is untrusted. Application validation applies the metric/dimension/filter allowlists and resource limits before compilation.
- Only application-compiled, parameterized analytical queries execute locally.
- Result narrative generation, if performed by the model, receives validated aggregate results and metric definitions, not arbitrary database access. Rendered numeric claims must agree with computed results.
- Application-enforced hosted-model inference and metered LangSmith tracing costs are capped at USD 10 per UTC calendar month, including directly attributable provider-billed fees/taxes and currency conversion; unrelated hosting costs are excluded. Attribute charges to the UTC month the operation was accepted, even if invoiced later. The application reserves maximum cost using token ceilings and current rates before each paid call, includes in-flight reservations, retries only after provider-confirmed non-acceptance, retains uncertain reservations until reconciled, and accounts conservatively for partial responses.
- Free-tier quotas and provider rate limits are enforced separately. There is no silent provider fallback.
- LangSmith tracing is disabled by default. Enabling it requires explicit operator configuration and user-facing disclosure; any metered tracing charge counts toward the USD 10 monthly cap.

## Provider disclosure boundary

- Each hosted provider/model and its applicable content-use terms are disclosed before its first hosted call in a session, including whether content may be used to improve the provider's products. Re-disclose material provider, model, or data-use changes before a subsequent call.
- This is separate from the analyst's session-level consent for the platform to reuse questions/reports in FAQs or system improvement.

## Consent and reuse boundary

- Consent is explicit, session-scoped, purpose-specific, and recorded with a notice version.
- Content created while consent is off is never eligible for shared reuse, even if consent is enabled later.
- Withdrawal stops future reuse. Already-created shared artifacts remain, as disclosed in the consent notice.
- Shared artifacts are stored separately from private report history and do not include analyst identity by default.
