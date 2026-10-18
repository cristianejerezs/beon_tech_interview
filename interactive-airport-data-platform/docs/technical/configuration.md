# Configuration reference

[Documentation home](README.md) | [Previous: Identity, authorization, and consent](identity-and-consent.md) | [Next: Local setup and deployment](deployment.md)

Implementation reference: 2026-10-18. See [scope and status](README.md#scope-and-status).

- [Environment settings](#environment-settings)
  - [Model and cost configuration](#model-and-cost-configuration)
  - [Data, feature, and deployment configuration](#data-feature-and-deployment-configuration)
  - [Tracing and evaluation](#tracing-and-evaluation)

## Environment settings

`Settings.from_env()` optionally loads `.env` with `override=False`: existing process variables
win. Paths are interpreted relative to the current working directory unless absolute.
Restart the app after changing startup settings. Sidebar choices can still select a different
provider/model from the initial defaults.

Booleans accept only `true`/`false`; numeric values must satisfy finite/nonnegative/minimum
rules. Never publish a real `.env` or Streamlit secrets file.

### Model and cost configuration

| Variable | Default | Meaning |
|---|---|---|
| `AIRPORT_MODEL_PROVIDER` | `ollama` | `ollama`, `openai`, or `groq` |
| `AIRPORT_MODEL_NAME` | `llama3.1:8b` locally; hosted model fallback otherwise | Initial selected-provider model |
| `AIRPORT_OLLAMA_MODEL_NAME` | UI fallback to local setting/default | Local model when switching providers |
| `AIRPORT_OLLAMA_BASE_URL` | `http://localhost:11434` | Configured local inference endpoint |
| `AIRPORT_OPENAI_API_KEY` | unset | Hosted credential; required for hosted selection |
| `AIRPORT_OPENAI_BASE_URL` | unset; official Groq URL if Groq is the initial provider | OpenAI-compatible endpoint |
| `AIRPORT_OPENAI_MODEL_NAME` | unset | Hosted model/sidebar availability |
| `AIRPORT_HOSTED_FREE_PLAN` | `false` | Verified no-paid-overage assertion; required for Groq |
| `AIRPORT_HOSTED_INPUT_USD_PER_MILLION` | unset | Required paid input rate |
| `AIRPORT_HOSTED_OUTPUT_USD_PER_MILLION` | unset | Required paid output rate |
| `AIRPORT_HOSTED_PROVIDER_FEES_FX_MULTIPLIER` | `1.0` | At least one |
| `AIRPORT_HOSTED_MAX_EXTRA_FEE_USD_PER_REQUEST` | unset | Required bounded paid fees/taxes |
| `AIRPORT_HOSTED_MAX_INPUT_TOKENS` | `4000` | Hosted input safety/reservation ceiling |
| `AIRPORT_HOSTED_MAX_OUTPUT_TOKENS` | `1000` | Output ceiling; also used by local adapter |
| `AIRPORT_HOSTED_FREE_MONTHLY_REQUEST_LIMIT` | `1000` | Local ledger allowance when enforced |
| `AIRPORT_HOSTED_FREE_MONTHLY_TOKEN_LIMIT` | `1000000` | Local ledger allowance when enforced |
| `AIRPORT_DEPLOYMENT_MONTHLY_BUDGET_USD` | `10.00` | Deployment cap, between zero and ten |
| `AIRPORT_HOSTED_PRODUCT_IMPROVEMENT_TERMS` | `unknown` | Disclosure text/signature component |
| `AIRPORT_MODEL_TIMEOUT_SECONDS` | `60` | Model transport timeout |

For the larger GPT-OSS V2 prompt, the documented operating configuration uses 16,000 input
and 4,096 output ceilings. The smaller defaults can reject an otherwise valid large prompt.
Increasing a ceiling increases the conservative reservation; it does not grant external quota.

### Data, feature, and deployment configuration

| Variable | Default | Meaning |
|---|---|---|
| `AIRPORT_DATABASE_PATH` | `var/airport_analytics.sqlite3` | Durable local SQLite file |
| `AIRPORT_SOURCE_DATA_DIR` | `source_data` | Five source CSVs |
| `AIRPORT_QUERY_TIMEOUT_SECONDS` | `30` | DuckDB query timeout |
| `AIRPORT_COVERAGE_PATH` | unset | Local complete-day declaration |
| `AIRPORT_WEATHER_UNITS_PATH` | unset | Local weather-unit declaration |
| `AIRPORT_VISUAL_REPORTING_ENABLED` | `false` | Browser saved-evidence visual preview |
| `AIRPORT_SHARED_REUSE_ENABLED` | `false` | Deployment permission for shared artifacts |
| `AIRPORT_PRODUCTION` | `false` | Production policy mode |
| `AIRPORT_DEV_SIGN_IN_ENABLED` | `false` | Restricted loopback-only development bypass |
| `AIRPORT_RETENTION_POLICY_APPROVED` | `false` | Operator approval assertion, not approval evidence |
| `WEASYPRINT_DLL_DIRECTORIES` | native/runtime default | Native library search override; not a `Settings` field |

### Tracing and evaluation

| Variable | Default | Meaning |
|---|---|---|
| `LANGSMITH_TRACING` | `false` | Operator trace request |
| `AIRPORT_LANGSMITH_DISCLOSURE_ENABLED` | `false` | Required trace disclosure enablement |
| `LANGSMITH_API_KEY` | unset | Required when tracing enabled |
| `AIRPORT_LANGSMITH_MAX_TRACE_CHARGE_USD` | unset | Required finite nonnegative per-trace bound |
| `AIRPORT_RUN_LIVE_EVALUATION` | unset | Explicit opt-in for the real-provider performance test |

Tracing requires both enablement flags, credential, bounded charge and UI acknowledgement.
It may include questions, plan context, report text or aggregate results, unlike the content-free
timing telemetry. Disable it for the evaluation CLI, which explicitly rejects enabled tracing.

---

[Documentation home](README.md) | [Previous: Identity, authorization, and consent](identity-and-consent.md) | [Next: Local setup and deployment](deployment.md)
