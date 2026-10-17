# Interactive Airport Data Platform

Question-driven, evidence-grounded analytics for the supplied historical NYC-area airport data.

For first-time setup and product usage, follow the [quickstart guide](QUICKSTART.md).

## Status

The Python application, validated query pipeline, report generation, private history, consent
controls, and export paths are implemented. Provider/model acceptance evaluation, production
retention-policy approval, and analyst usability sessions remain release gates; see the
[implementation tasks](specs/001-airport-analytics-platform/tasks.md).

## Safety and privacy boundaries

- LangChain interprets analyst questions as structured analysis plans only. The application
  validates each plan against its JSON Schema and closed catalog, then compiles a parameterized,
  read-only DuckDB `SELECT`. A model receives no database access or source rows; model-generated
  SQL is never executed.
- Normal sign-in uses OIDC issuer and subject claims to produce a pseudonymous analyst ID. Private reports, report detail,
  deletion, history, and downloads are owner-scoped. Each analyst's ten newest private reports are
  retained.
- An opt-in development sign-in bypass is available only with explicit loopback server binding
  and production mode disabled. It uses one shared development identity, not real authentication.
  Never expose that server through a proxy or tunnel. See the [quickstart](QUICKSTART.md#option-a-development-sign-in-local-machine-only).
- Hosted inference requires an explicit provider/model disclosure and a pre-call budget
  reservation. There is no automatic provider fallback. Hosted inference and any enabled,
  metered LangSmith traces share a deployment-wide USD 10 cap per UTC month.
- LangSmith tracing is off by default. Enabling it requires operator configuration, a bounded
  charge, user-facing disclosure, and analyst acknowledgement; traces may include questions,
  plan context, aggregate results, or report text.
- Shared FAQ/system-improvement reuse is disabled by default. Consent is purpose-specific,
  reversible, and session-scoped. Withdrawing consent stops future reuse; already-shared,
  identity-free artifacts remain. Production reuse must stay disabled until the deployment owner
  approves retention/deletion procedures, including backup handling.

## Scope

The initial analysis areas are connectivity, delays, airline comparisons, and aircraft statistics.
Weather is contextual only and must not be described as causal. The data is a historical snapshot,
not live flight information. The MVP is English-only and requires keyboard-operable, labelled
controls and visible status/error messaging.

The single-host MVP has no uptime, high-availability, response-time, or concurrency-throughput SLA.
Representative latency may be measured as a baseline, not a pass/fail threshold.

## Development setup

Requires Python 3.12 and the supplied CSV files in `source_data/`.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

Configure Streamlit OIDC for `st.login` in `.streamlit/secrets.toml` using the provider's
discovery metadata and registered redirect URL. Never commit credentials. Set the desired provider,
model name, data path, and SQLite path in the environment or `.env`. Local use requires the
configured Ollama service and model. Hosted use requires an API key; paid plans additionally
require token rates and a maximum per-request fee/tax bound. Check the provider's current free
quotas and data-use terms before enabling it.

Start the app:

```powershell
streamlit run app.py
```

Important settings are documented in [.env.example](.env.example). Shared reuse is disabled by
default. Keep `AIRPORT_SHARED_REUSE_ENABLED=false` in production until the documented retention
and deletion policy has been approved. Do not turn on `LANGSMITH_TRACING` unless its disclosure,
API key, maximum trace charge, and monthly budget have been configured.

## Validation

```powershell
python -m pytest
python -m ruff check .
```

The golden question corpus, architecture, requirements, and validation protocol are in
[specs/001-airport-analytics-platform/](specs/001-airport-analytics-platform/).
