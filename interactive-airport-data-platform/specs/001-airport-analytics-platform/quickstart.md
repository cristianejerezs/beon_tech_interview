# Quickstart and Validation Guide

This guide describes the expected local setup for the implementation. It does not provision model weights, a hosted-model account, or an OIDC provider. The application can be configured for local Ollama or a hosted LangChain-supported provider. Hosted use requires a configured provider, a visible provider-use notice, and the application-enforced USD 10 monthly inference cap.

## Prerequisites

- Windows, macOS, or Linux host with Python 3.12.
- The supplied CSV files in `source_data/`.
- Either Ollama installed locally with an approved model artifact already available, or credentials for an explicitly configured LangChain-supported hosted provider.
- OIDC provider configuration for interactive sign-in. Automated tests should use a test identity fixture rather than a production provider.
- Hosted-provider configuration must define the model identifier, current input/output token rates or free-plan status, request token ceilings, and quota limits. Keep API keys in environment secrets, never in source control.

## Run locally

From the repository root, after implementation has created the application dependencies:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
streamlit run app.py
```

For a local-model configuration, verify the installed model with `ollama list`. For a hosted provider, set provider credentials and pricing/quota configuration before launching. Provider selection must be explicit; an unavailable provider must not trigger silent fallback.

## Validate

Run the project test suite:

```powershell
python -m pytest
```

The completed implementation should include tests for these scenarios:

1. **Grounded answer**: ask a supported connectivity, delay, airline, or aircraft question. Verify the report is derived from query results for the current source snapshot and includes relevant metric definitions/caveats.
2. **Weather context**: ask a delay question involving weather. Verify the airport/time join coverage and association method are disclosed and no causal claim is made.
3. **Ambiguity and scope**: submit an ambiguous or unsupported question. Verify the app asks one focused clarification or explains the limitation, and does not run a query before a valid plan exists.
4. **Query safety**: submit SQL-shaped text or an instruction to access an unknown table/field. Verify the model response is treated as untrusted, the compiler rejects non-catalog identifiers, and no arbitrary SQL executes.
5. **Budget enforcement**: test requests at, near, and over the USD 10 UTC calendar-month cap, including concurrent reservations and unestimable costs. Verify no request can push maximum reserved spend over the cap.
6. **Provider disclosure and fallback**: use a hosted provider whose terms allow product improvement. Verify the notice appears before the first hosted call, remains separate from FAQ reuse consent, and provider failures never trigger silent provider switching.
7. **Tracing privacy**: verify LangSmith tracing is disabled by default and enabling it requires explicit configuration and disclosure.
8. **Consent transitions**: decline at session start, enable later, disable, and re-enable. Verify only content created while consent is active is copied for the disclosed purpose and already-reused material remains after withdrawal.
9. **Analyst isolation**: authenticate as two test analysts. Verify report history, details, and PDF/CSV exports for one analyst cannot be read by the other.
10. **Provider failure**: stop the configured local runtime or simulate a hosted API error/invalid response. Verify a visible error, no unsafe plan execution, no budget overrun, and no silent fallback.
11. **History retention and exports**: create more than ten reports for one analyst. Verify only the ten newest remain in private history and report exports preserve the intended report/table content.
12. **Latency baseline**: after selecting the host and provider, run representative supported questions end to end and record the benchmark method, environment, and measured response times here. This establishes an MVP baseline only; there is no hard latency pass/fail threshold.
13. **Provider-quality gate**: evaluate 12 fixed supported questions (three per analysis area) against independent expected metrics and scope. A candidate must correctly interpret at least 11/12; every generated numeric result must match the independently calculated result, and invalid plans must never execute.
14. **Input bounds**: submit empty, whitespace-only, non-text, 2,001-code-point-after-trimming, and maximum-length valid questions. Rejections occur before model invocation or budget reservation; a 2,000-code-point trimmed plain-text question is accepted for processing.
15. **Budget reconciliation**: verify fee/tax/FX accounting and month attribution for requests invoiced late; test partial responses, provider-confirmed non-acceptance retries, uncertain acceptance reservations retained through reconciliation, and operator-visible handling when actual charges exceed reservations.
16. **Restart and accessibility**: restart the application and verify committed reports, consent events, and usage reservations persist. Review analyst-facing controls for keyboard operation, programmatic labels, visible focus, and status/error cues not conveyed by color alone.
17. **Production reuse gate**: verify shared reuse is disabled for production configuration until a retention/deletion policy covers identity mappings, reports, consent events, shared artifacts, and backups.

Detailed data and interface shapes are in [data-model.md](./data-model.md) and [contracts/](./contracts).

## Convergence implementation and pending release evidence

Owner-approved session-default and loopback-only development exceptions are documented in
[spec.md](spec.md). Historical default-off test descriptions above must be read with that
amendment: disable default-on purposes before private testing, and verify disabled choices
remain off. Neither defaults nor tests establish legal consent or production approval.

Reports now label observed date bounds in their filtered population; full-snapshot geographic
coverage remains separately labelled. Joined coverage uses the effective filtered population
before match-only exclusions. Destination counts include supporting routes (up to 500,
explicitly marked incomplete if truncated), a separate CSV, and PDF route/scope evidence.
Ranking cutoff ties are disclosed; secondary ordering uses group labels, not a unique winner.
Source validation checks field types, grain keys, nulls, and duplicates; repeated flight
observations with different source-row IDs are retained and counted in snapshot metadata.
Source files are content-fingerprinted before cached executor reuse.

Uncertain paid requests persist and block further paid authorization across restarts/months
until evidence-based reconciliation. Charge overruns are logged without prompt/response bodies.
Never clear or delete the ledger to bypass these restrictions.

### Provider acceptance and latency commands

**Status: NOT RUN. No live provider pass or latency baseline is claimed.**

Review the configured provider/model, account quotas, current data-use/retention terms,
fees/rates, and [main quickstart](../../QUICKSTART.md) before dispatch. Use the normal configured
ledger. Disable tracing. The following explicitly dispatches the 12 synthetic golden questions
through the normal provider/disclosure/budget gates; it does not send source rows or identities:

```powershell
python -m airport_analytics.analytics.evaluation --run-live --acknowledge-hosted-processing
```

Set the provider and model explicitly in the environment before running each candidate.
The CLI emits only per-case IDs, safe error categories, pass flags, timing/environment and
snapshot identifiers, not prompts, raw provider output, keys, or report rows. It exits nonzero
if fewer than 11/12 generated interpretations match scope or any generated numeric result
differs from the independent fixture (absolute floating tolerance 1e-12).
Scope comparison is conservative: equivalent alternative filter/date encodings require
manual review rather than being silently counted as a pass.

The first model call may be cold; subsequent sequential calls are warm/provider-dependent.
Dataset validation time is reported separately. Record hardware, host, Python/dependency
versions, candidate terms/quota review, cold/warm conditions, failures, and the returned timings
here after execution; there is no latency pass/fail threshold.

For an opt-in pytest baseline with the same real-provider acceptance gate:

```powershell
$env:AIRPORT_RUN_LIVE_EVALUATION = "true"
python -m pytest -q -s tests\performance\test_report_latency.py
Remove-Item Env:\AIRPORT_RUN_LIVE_EVALUATION
```

This opt-in test is skipped during normal automated validation. Do not run both commands
unnecessarily: each dispatches another 12 requests. No automatic retries or fallback occur.

Still required: actual candidate comparison and selected provider rationale (T058/T071),
measured latency (T059/T078), [owner-approved retention](../../docs/privacy-data-retention.md)
(T060/T073), [five real analyst sessions](../../tests/acceptance/analyst_study.md)
(T061/T074), and authenticated browser keyboard/focus/accessibility review (T062/T075).
