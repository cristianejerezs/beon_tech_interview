# Quickstart: use the Airport Data Platform

This guide covers the current single-host MVP on Windows with PowerShell.
The recommended first run uses Ollama locally, with hosted inference and tracing off.

**Before you start:** the app requires OIDC sign-in, even for local analytics.
There is no anonymous mode or development sign-in bypass. You need an identity-provider
application registration and a running model service; installing Python packages alone
does not make the product ready to answer questions.

## 1. Open the project and prepare Python

Use the project folder once, not a second nested `interactive-airport-data-platform` folder:

```powershell
Set-Location "C:\Users\Cristian E Jerez S\Desktop\BEON\beon_tech_interview\interactive-airport-data-platform"
```

The project requires Python 3.12. Create the environment only if it does not exist:

```powershell
if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    py -3.12 -m venv .venv
}
.\.venv\Scripts\Activate.ps1
python --version
python -m pip install -e ".[dev]"
python -m pip install "streamlit[auth]>=1.42,<2"
```

The second install supplies Streamlit's authentication extra (Authlib), which the current
project dependency declaration does not install explicitly.

If `py` is unavailable but `python --version` reports 3.12, use
`python -m venv .venv` instead.

If activation is blocked by PowerShell execution policy, you can skip activation and use
the environment's interpreter directly for each command:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pip install "streamlit[auth]>=1.42,<2"
```

An "Activate.ps1 not recognized" error means the script cannot be found: check your folder
and create the environment before attempting activation.

## 2. Configure local processing

Create your local environment file without overwriting an existing one:

```powershell
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
}
notepad ".env"
```

Keep these settings for the local quickstart:

```dotenv
AIRPORT_MODEL_PROVIDER=ollama
AIRPORT_MODEL_NAME=llama3.1:8b
AIRPORT_OLLAMA_MODEL_NAME=llama3.1:8b
AIRPORT_OLLAMA_BASE_URL=http://localhost:11434
AIRPORT_SOURCE_DATA_DIR=source_data
AIRPORT_DATABASE_PATH=var/airport_analytics.sqlite3
AIRPORT_SHARED_REUSE_ENABLED=false
AIRPORT_RETENTION_POLICY_APPROVED=false
LANGSMITH_TRACING=false
AIRPORT_LANGSMITH_DISCLOSURE_ENABLED=false
```

Process environment variables override `.env` values. Restart the app after changing settings.
Use a trusted local Ollama endpoint; "local" selection sends prompts to the configured endpoint.

Install [Ollama](https://ollama.com/download/windows), start its service, and download the model:

```powershell
ollama pull llama3.1:8b
Invoke-RestMethod "http://localhost:11434/api/tags"
```

If the service is not running, run `ollama serve` in a separate terminal and keep it open.
The example model is the configured default, not a model that has passed the project's
pending acceptance evaluation. Its download, memory use, and response time depend on your host.

Verify the five supplied files are present:

```powershell
Get-ChildItem ".\source_data\*.csv"
```

Expected: `nyc_airlines.csv`, `nyc_airports.csv`, `nyc_flights_fixed.csv`,
`nyc_planes.csv`, and `nyc_weather.csv`. The app validates the snapshot before analytics.
Do not replace these with live or differently shaped CSVs.

## 3. Configure sign-in

Ask your identity-provider administrator to register an OIDC web application with this
local redirect URL:

```text
http://localhost:8501/oauth2callback
```

Obtain its client ID, client secret, and discovery metadata URL. Its identity token must
provide stable `iss` (issuer) and `sub` (subject) claims.

Create a local secrets file:

```powershell
New-Item -ItemType Directory -Path ".streamlit" -Force | Out-Null
notepad ".streamlit\secrets.toml"
```

Enter this structure, replacing every placeholder with your actual configuration:

```toml
[auth]
redirect_uri = "http://localhost:8501/oauth2callback"
cookie_secret = "REPLACE_WITH_A_LONG_RANDOM_SECRET"
client_id = "REPLACE_WITH_YOUR_CLIENT_ID"
client_secret = "REPLACE_WITH_YOUR_CLIENT_SECRET"
server_metadata_url = "https://YOUR_OIDC_ISSUER/.well-known/openid-configuration"
```

Generate the cookie secret locally with `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
Never commit or paste real secrets into chat. The repository ignores this secrets file,
local `.env` files, and the default runtime storage folder.

All settings belong under `[auth]` because the current app calls `st.login()` without a
named provider. Follow your provider's registration instructions; the placeholder metadata
URL is not a working provider. A deployed host needs HTTPS and matching redirect URLs in
both the application and identity-provider registration.

## 4. Start the product

From the project folder, with the environment activated:

```powershell
python -m streamlit run app.py
```

Without activation:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Open `http://localhost:8501`, select **Sign in**, and complete the OIDC flow.
Leave the terminal running. Stop the app with `Ctrl+C`.

## 5. Ask, refine, and export

1. Confirm **Model provider** is **Ollama (local)**.
2. Leave **Optional sharing and reuse controls** off for private analysis.
3. Enter an English question in **Question** and select **Generate report**. For example:
   - "How many distinct destinations did EWR serve in 2013?"
   - "What were the three busiest destinations from LGA in 2013?"
   - "Which carrier had the highest mean departure delay in 2013?"
4. Review the answer, metric definition, active filters, period, supporting rows,
   coverage, and limitations. A clarification or unsupported-data response is not a report.
5. To refine a displayed report, check **Refine the currently displayed report's scope**,
   enter a follow-up such as "Only flights from EWR", and generate again. Verify the new scope.
6. Use **Download result table (CSV)** or **Download complete report (PDF)**.
7. Use **Open one of your saved reports** to revisit private history. Only your ten newest
   private reports remain. **Delete private report** removes that private copy.
8. Select **Sign out** when finished.

Reports and budget state persist in the configured SQLite file across normal restarts.
Protect that file and its backups; do not commit runtime data. Deleting a private report
does not delete a separately retained, previously authorized shared artifact.

## Optional hosted processing and sharing

Hosted inference is not needed for the local path above. To enable it, an operator must
configure the OpenAI-compatible credentials, model, current rates or verified free-plan
quotas, fee/FX bounds, and data-use terms in the process environment or local `.env`,
using [.env.example](.env.example) as a reference. Set both
`AIRPORT_MODEL_NAME` and `AIRPORT_OPENAI_MODEL_NAME` to the intended hosted model when
`AIRPORT_MODEL_PROVIDER=openai`.

Select the hosted provider explicitly and acknowledge its notice before submitting a question.
No model gets unrestricted database access: it returns a plan, which the application validates
and compiles locally. Hosted inference and enabled metered tracing share the deployment-wide
USD 10 UTC-month cap. Budget exhaustion does not trigger automatic fallback; select Ollama
explicitly or wait for the next UTC month. Unknown provider acceptance retains its reservation.

Keep tracing and shared reuse off during initial use. Shared reuse additionally requires
session/purpose consent and an explicit **Create shared copy** action for a report created
under the active grant. Withdrawal stops future reuse, not previously shared copies.
Production shared reuse remains blocked until owner-approved retention/deletion procedures
are documented; do not enable approval flags merely to bypass this gate.

## Troubleshooting and current limitations

| Symptom | Action |
|---|---|
| Missing module or wrong Python | Activate `.venv` or use its interpreter explicitly, then install dependencies as above. |
| Sign-in fails | Check Authlib installation, `[auth]`, issuer/subject claims, and exact redirect URL registration. |
| Model unavailable | Check Ollama is running, `/api/tags` lists the configured model, and the endpoint is correct. There is no automatic fallback. |
| Dataset unavailable | Check the working directory, source-data setting, and all five original CSVs. |
| Hosted submit disabled | Acknowledge provider processing and, if enabled, tracing notices. |
| Hosted input/cost bound rejected | The operator must review token ceilings, tokenizer support, current rates, and fee bounds. Do not disable validation. |
| No records or unsupported question | Broaden filters or ask about supported connectivity, delays, airlines, or aircraft metrics. |

The snapshot is historical, not live flight data. Weather comparisons are contextual, not
causal. Live provider/model evaluation, latency baselining, owner retention approval, five
analyst sessions, and the full accessibility review remain pending. Automated tests are
not evidence that those release gates have been completed.

For developer checks, run `python -m pytest` and `python -m ruff check .`.
See [README.md](README.md) for architecture and
[the task list](specs/001-airport-analytics-platform/tasks.md) for remaining work.
