# Model integration, token usage, and budgets

[Documentation home](README.md) | [Previous: Analytics engine and metric semantics](analytics-engine.md) | [Next: Reports, persistence, and retention](reports-and-persistence.md)

Implementation reference: 2026-10-18. See [scope and status](README.md#scope-and-status).

- [Model providers, prompts, caching, and limits](#model-providers-prompts-caching-and-limits)
  - [Provider selection](#provider-selection)
  - [Prompt contents and structured transport](#prompt-contents-and-structured-transport)
  - [Token ceiling](#token-ceiling)
  - [Interpretation reuse](#interpretation-reuse)
  - [Rate pacing and retry](#rate-pacing-and-retry)
- [Budget accounting and request reconciliation](#budget-accounting-and-request-reconciliation)
  - [Deployment-wide authorization](#deployment-wide-authorization)
  - [Ledger transitions](#ledger-transitions)
  - [Free quotas](#free-quotas)
  - [Reconciliation procedure](#reconciliation-procedure)

## Model providers, prompts, caching, and limits

### Provider selection

`LangChainPlanClient` supports:

- `ollama`: `ChatOllama`, configured endpoint/model, temperature zero.
- `openai`: `ChatOpenAI`, configured OpenAI-compatible endpoint.
- `groq`: the official `https://api.groq.com/openai/v1` endpoint, a verified free plan,
  and `openai/gpt-oss-20b` or `openai/gpt-oss-120b`.

Providers/models are selected explicitly. There is no automatic model/provider fallback.
The sidebar can override the environment's initial provider/model choice.

### Prompt contents and structured transport

The model receives the question, instructions, catalog/schema, and only an explicitly targeted
active follow-up interpretation or clarification context. It receives no source rows,
database access, analyst identity, or full saved history in the interpretation request.

Hosted V2 sends the output schema through `response_format` rather than duplicating it in
the system prompt. Redundant titles are stripped. Groq transport uses a supported schema
projection and best-effort V2 output; the full local schema and typed validation remain enforced.

The only specific V2 Groq envelope normalization fills an absent, unused `selection_reason`
with null for proposed/clarification/unsupported statuses. It does not infer missing
analytical fields, invent answers, or automatically repair a failed interpretation.

### Token ceiling

Hosted calls estimate prompt tokens including the separately transmitted schema and conservative
framing allowance. GPT-OSS uses `o200k_harmony`; other hosted models use the adapter/tokenizer
path. Unknown tokenizer support or an exceeded input ceiling blocks dispatch.

The reservation uses configured maximum input/output tokens, not the measured prompt alone.
Thus a 16,000/4,096 configuration reserves 20,096 local quota tokens until settlement.

The provider-reported `input_tokens`, `output_tokens`, and optional `cached_input_tokens`
are recorded after response. Cached-token telemetry does not automatically lower local
quota charges, paid cost calculations, or the conservative pacing estimate.

### Interpretation reuse

The default process-wide LRU contains at most **128 entries** with a **one-hour TTL**.
Its SHA-256 key includes provider, model, endpoint, output ceiling, contract version,
schema JSON, message types and exact message contents.

Only locally validated V1 `ready` and V2 `proposed` interpretations are cached. Clarification,
unsupported, selection-required and invalid outputs are not stored as reusable successes.
Returned cached payloads are deep copies and revalidated. Hosted disclosure is still required.
A hit reports zero new provider tokens and has no new inference/trace reservation.

This caches **interpretations, not calculated report answers**. Generation still resolves
and executes against the required source/context, so a repeated prompt does not authorize
stale numerical results.

Important limits:

- Cache entries are process-wide, not partitioned by analyst/session or consent purpose.
- The key does not explicitly include credentials, source snapshot, all tracing settings,
  or the caller's identity; active context is included only insofar as it is in the messages.
- Process restart clears entries.
- Concurrent misses are not deduplicated into a single in-flight call.
- Injected test models use no shared interpretation cache unless explicitly supplied.

This operational interpretation reuse is not the separate consent-controlled shared-artifact
feature. Deployments needing stricter session isolation must review that distinction.

### Rate pacing and retry

Hosted responses request response headers. `TokenRatePacer` reads token limit, remaining tokens
and reset duration. It estimates continuous bucket refill and waits when estimated headroom is
insufficient.

- State is keyed by provider/model and held in this Python process.
- No known valid header window means no proactive wait.
- Estimated waits of at most 30 seconds sleep with a small safety margin.
- Longer waits are logged but the request is sent without that proactive sleep.
- Headers from errors also update the estimate.
- Pacing is advisory, not a distributed atomic token reservation or guarantee against 429.
- It does not coordinate other processes/apps using the same provider account.

On HTTP 429, the request reservation is released. A known `Retry-After` or parsed provider
wait of at most 30 seconds gets **one automatic retry**, after the wait plus 0.5 seconds.
The underlying OpenAI adapter has automatic SDK retries disabled.

Daily-limit messages are identified separately, but the implemented retry gate checks
**status and wait duration**, not `daily_limit`. A daily 429 with a short enough reported
wait therefore meets the same retry condition; long daily waits are not slept.
The retry itself goes through the normal disclosure/pacing/reservation path.

Timeout/connection/non-429 errors are not automatically retried. A second 429 is surfaced
with a message explaining the automatic retry already failed.

Provider prompt caching is external. Cache-hit telemetry alone cannot prove how a particular
account's token window is charged or guarantee the next request will be accepted.
## Budget accounting and request reconciliation

### Deployment-wide authorization

The ledger uses `Decimal` monetary values and immediate SQLite transactions. Hosted inference
and enabled metered traces share a maximum **USD 10 per UTC calendar month**, configurable
downward but not upward.

For paid inference:

```text
maximum token cost =
  (max_input_tokens * input_rate + max_output_tokens * output_rate) / 1,000,000

reservation USD =
  round upward to cents(maximum token cost * fee/FX multiplier + maximum extra fee)
```

Rates and a fixed fee/tax bound are mandatory for paid hosted use. The multiplier must be
at least one. Free-plan requests reserve zero USD but retain request/token accounting.

### Ledger transitions

| Event | Ledger handling |
|---|---|
| Before hosted dispatch | Reserve maximum bounded cost/tokens transactionally. |
| Trace reservation fails before inference call | Release inference reservation before dispatch. |
| Successful provider response | Settle actual reported tokens; retain conservative maxima where usage is unavailable. |
| Provider returned malformed structured content | Settle consumed request, then raise invalid-plan error. |
| HTTP 429 rejection | Release confirmed non-acceptance; zero actual cost. |
| Timeout/connection/other uncertain acceptance | Keep `reserved`, set `acceptance_uncertain=1`, retain reason. |
| Trace completes/fails after dispatch | Settle its configured maximum charge. |
| Report save/export fails after calculation | Does not undo provider consumption. |

The schema permits `reserved`, `settled`, `failed`, and `released`. The core current inference
paths chiefly reserve, settle or release. An unresolved paid acceptance blocks later paid
dispatch until reconciled.

### Free quotas

The library ledger can enforce local free-plan monthly request and token limits.
Settled requests use reported input/output counts, falling back independently to each configured
maximum. In-flight/uncertain requests retain full token reservations. Released rows do not
consume these local quota totals.

The Streamlit app disables local monthly free request/token allowances when both
`production=false` and `hosted_free_plan=true`. It still records usage, enforces the monetary
cap and respects external provider limits. The standalone evaluation CLI constructs its own
ledger and does not apply that UI-specific development exemption.

These local monthly allowances are not verified provider entitlements. Provider per-minute
and per-day limits remain external and can change.

### Reconciliation procedure

Inspect status, timestamps, model, failure reason and provider evidence for a specific reservation.
Use the ledger's explicit release/settlement methods where possible. Release confirmed
non-acceptance only when provider rejection is established. Do not bulk-release uncertain
paid requests merely because they are old.

There is no automatic stale-reservation expiry, administrative reconciliation screen, or
provider billing reconciliation service. Back up and audit any operator-directed corrections.
Do not delete usage history as a way of resetting external rate limits.

---

[Documentation home](README.md) | [Previous: Analytics engine and metric semantics](analytics-engine.md) | [Next: Reports, persistence, and retention](reports-and-persistence.md)
