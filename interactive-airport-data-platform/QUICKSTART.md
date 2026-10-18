# Quickstart: use the Airport Data Platform

This guide covers the current single-host MVP on Windows with PowerShell.
The recommended first run uses Ollama locally, with hosted inference and tracing off.

**Before you start:** normal use requires OIDC sign-in. For trusted local development,
you can explicitly enable the localhost-only development sign-in described in step 3.
Either route still requires a running model service; installing Python packages alone
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

## 3. Choose development sign-in or OIDC

### Option A: development sign-in (local machine only)

You can skip OIDC registration and the secrets file for local development. Set these in `.env`:

```dotenv
AIRPORT_DEV_SIGN_IN_ENABLED=true
AIRPORT_PRODUCTION=false
```

Start the server with an explicit loopback bind:

```powershell
python -m streamlit run app.py --server.address=127.0.0.1
```

Without activation, use:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address=127.0.0.1
```

Open `http://127.0.0.1:8501` and select **Sign in as local developer**. Continue with step 5.
The app shows a warning because this is not real authentication: every development
session uses the same stable identity and can access that identity's private history.
Its identity is separate from normal OIDC analysts. **Sign out** clears the development
session and its disclosure/consent state, but does not delete saved reports.

The bypass is off by default and is rejected in production or without an explicit
`localhost`, `127.0.0.1`, or `::1` server bind. Never expose it through a reverse proxy,
tunnel, shared host, or public network. For production, set
`AIRPORT_DEV_SIGN_IN_ENABLED=false` and `AIRPORT_PRODUCTION=true`.
Hosted-provider disclosures, budgets, query validation, and reuse controls still apply.

Development sign-in also enables the reuse controls even when
`AIRPORT_SHARED_REUSE_ENABLED=false`. Session choices default to on for both purposes:

1. Review the expanded **Optional sharing and reuse controls**. Turn off **Enable FAQ examples reuse**
   or **Enable System improvement reuse** if you do not want that purpose enabled.
2. Generate a new report after the session grant is recorded. Older reports cannot be shared retroactively.
3. Open **Share this report under active reuse consent**, choose a purpose, and select
   **Create shared copy**.
4. Open **Shared FAQs** to read FAQ copies and their saved scope/results.
   **Use this FAQ question** fills the question input; generating a new answer still uses
   the normal validated-query and model/budget checks. System-improvement copies are
   retained separately and are not displayed in the FAQ list.
5. Turn the corresponding toggle off to withdraw consent and stop future sharing.
   It stays off across reruns in the session. Existing shared copies remain.

The same session defaults apply with normal OIDC sign-in, but only if deployment reuse is
enabled and, in production, retention/deletion policy is approved. Disabled deployment
features are not enabled by session defaults. Grants use notice version `v2-default-on`;
they record a default selection, not an affirmative user click.

Remote models are also available in development when configured. Keep the local default
and add these settings to `.env` (real credentials stay local):

```dotenv
AIRPORT_OPENAI_API_KEY=REPLACE_WITH_YOUR_KEY
AIRPORT_OPENAI_MODEL_NAME=REPLACE_WITH_YOUR_HOSTED_MODEL
```

Configure current token rates, fee/FX bounds, and data-use terms, or verified free-plan
quotas, using the optional hosted-processing section below. Restart the server and explicitly
select **OpenAI (hosted)** in **Model provider**. `AIRPORT_OPENAI_BASE_URL` may point to an
OpenAI-compatible service; the disclosure displays the configured endpoint. Credentials
are not supplied by development mode, and disclosures and the shared USD 10 cap still apply.

### Option B: normal OIDC sign-in

Keep `AIRPORT_DEV_SIGN_IN_ENABLED=false` and follow the configuration below.

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

Use the [question-writing guide](QUESTION_GUIDE.md) for supported metrics, compatible
breakdowns, copyable examples, and tips for clarifying or refining a question.

1. Confirm **Model provider** is **Ollama (local)**.
2. Review **Optional sharing and reuse controls**. Enabled purposes default to on;
   turn both off for private-only analysis.
3. Enter an English question in **Question** and select **Generate report**. For example:
   - "How many distinct destinations did EWR serve in 2013?"
   - "What were the three busiest destinations from LGA in 2013?"
   - "Which carrier had the highest mean departure delay in 2013?"
   **Use this FAQ question** fills the same editable field. Questions remain in the field
   after submission, including failures, so you can correct or resubmit them.
4. Review the answer, metric definition, active filters, period, supporting rows,
   coverage, and limitations. A clarification or unsupported-data response is not a report.
5. To refine a displayed report, check **Refine the currently displayed report's scope**,
   enter a follow-up such as "Only flights from EWR", and generate again. Verify the new scope.
   This control is disabled until a report is generated successfully or opened from history.
   The refinement-target caption identifies which saved report the follow-up will use.
6. Use **Download result table (CSV)** or **Download complete report (PDF)**.
7. Use **Open one of your saved reports** to revisit private history. Only your ten newest
   private reports remain. **Delete private report** removes that private copy.
8. Select **Sign out** when finished.

**V2 exploration is enabled by default** by the **Use V2 summary exploration** toggle.
It supports one to four labelled analyses, including summaries, unique entity lists,
individual-flight listings and the analytical forms below. Turn it off for V1 generation.

For example, ask "List distinct destinations served from JFK" or "Show individual flights from EWR".
Listings show exact totals and a saved bounded preview, not an implied full population.
**Load listing page** supports 25/50/100/500 rows with deterministic sorting. Size/sort/scope
changes and out-of-range positions reset to page one with a notice. Paging never calls the model.
Saved listings remain browseable even when V1 generation is selected.

**Download saved preview (CSV)** downloads only the saved rows. To export more, choose
**Listing export rows**, confirm a partial population if needed, then **Prepare listing CSV**.
The prepared file starts at row one in saved report order and contains at most 10,000 data rows,
with exact exported/total counts and scope/definition metadata. Null field names are recorded
separately from empty text; risky spreadsheet text receives a reversible leading apostrophe.
The table PDF contains the saved preview, not every matching flight.

Changed/missing source files or analytical context disable historical paging and full-listing
exports without removing saved previews. **Restart listing on current source** fills the question
form; review it and explicitly select **Generate report** to analyze again. Catalog 2.2's analytical
definitions invalidate recomputation of older-context reports, not their saved evidence.

### V2 analytical and multi-section workflows

- Ask explicitly for the airport(s), historical period and up to four related analyses.
  Daily/weekday distinct-destination means, known-seat daily capacity, positive/net delay
  totals, manufacturer-qualified aircraft frequencies, period changes, distributions and
  flight-pair/origin-hour weather relationships are locally calculated.
- Configure `AIRPORT_COVERAGE_PATH` only when reviewed local evidence supports the exact loaded
  snapshot. The declaration must satisfy the [coverage schema](specs/002-natural-language-exploration/contracts/coverage.schema.json),
  name known origins, nonoverlapping inclusive intervals/contained gaps, reviewer/passed-check
  metadata and local documents with matching SHA-256 hashes. No declaration is fabricated or
  fetched from a network. Invalid, stale or missing evidence leaves coverage unknown.
- Calendar daily means include verified no-flight days as zero, exclude unknown dates, and
  never divide by a displayed sample. Without verified days they are unavailable. Use
  **Edit analytical definition** to explicitly select observed operating days, making a new
  provisional revision. Weekdays use their own eligible-day counts and exact half-up display.
- Set `AIRPORT_WEATHER_UNITS_PATH` only for a reviewed JSON declaration with `schema_version: 1`,
  `weather_sha256`, `units`, `reviewed_by`, `evidence_reference`, `evidence_sha256`.
  `units` must be exactly `{"temp":"F","wind_speed":"mph","precip":"inches","visib":"miles"}`.
  The weather-file hash and local evidence-document hash must match. This enables verified
  weather-unit labels and descriptive precipitation comparisons. Without valid evidence,
  the four equal-origin-hour Pearson coefficients still use the recorded numeric values,
  explicitly labelled provisional with unverified units; precipitation-band comparisons
  are omitted. No conversion or physical unit is inferred. Pearson is dimensionless and
  unchanged by positive linear unit conversions, but assumes consistent numeric scales and
  meaningful recorded values. Warnings and unit status persist in saved reports and exports.
- **Pending analysis** resolves each section before execution. Structured correction targets
  the focused section; explicit removal preserves the other section IDs. A request exceeding
  four sections can run only an explicitly confirmed subset, never an automatic report queue.
- **Refine the scope of selected or all sections** applies explicit local origin/airline/date
  edits in a new analytical revision. Other sections retain their meaning. Use the analytical
  section selector for daily denominator, period or bin-definition changes.
- A runtime fault retains the failed section and its notice. A report with no successful section
  is not saved. A partially successful report requires exact failed-section acknowledgement
  before save, sharing or export. Save failures retain unsaved evidence only in the current
  session; **Save unsaved report** retries persistence without another model call.
- Saved-evidence ZIPs include each section and a status/scope manifest. To expand listings, set
  explicit per-section allocations whose combined total is at most 10,000, confirm any partial
  populations, then prepare the allocated bundle. No download is produced after a technical
  failure. Daily support and weather pair/density CSVs are included as bounded auxiliary files.
- Owner-scoped presentation preferences are atomically versioned and currently limited to
  default/table. They never change evidence or creation time. Refresh after conflicts.
  Automatic charts, composite chart PDFs, tagged PDFs and integrated visual/accessibility
  acceptance remain specification 003 work; table PDFs are not claimed accessible/tagged.

Reports and budget state persist in the configured SQLite file across normal restarts.
Protect that file and its backups; do not commit runtime data. Deleting a private report
does not delete a separately retained, previously authorized shared artifact.

## Optional hosted processing and sharing

### Groq free-plan setup

Groq is supported explicitly for `openai/gpt-oss-20b` and `openai/gpt-oss-120b`
on the official endpoint. Support uses the GPT-OSS Harmony tokenizer with a conservative
framing allowance rather than pretending that these models are OpenAI chat model names.
Provider-reported usage settles the ledger; application validation still rejects unsafe plans.
This compatibility path is tested with mock responses, not a completed live-model acceptance study.

1. Create a Groq account at <https://console.groq.com> and review your plan/billing settings.
   Confirm your requests are free and cannot trigger paid overage. Do not upgrade to a paid
   plan for this configuration: this Groq integration currently supports verified free use only.
2. Check your actual limits at <https://console.groq.com/settings/limits>.
   Limits can include requests/tokens per minute and per day, not just monthly usage.
   Provider `429` responses still apply; the app does not automatically retry.
3. Review <https://console.groq.com/docs/your-data> and your organization's Data Controls.
   The documentation describes no default inference-content retention, with reliability/abuse
   exceptions (up to 30 days, subject to legal requirements) and Zero Data Retention controls.
   Verify current product-improvement terms separately and accurately disclose your settings.
4. Generate a key at <https://console.groq.com/keys>. Put it only in your local `.env`,
   not in chat or a committed file.
5. Configure the following, replacing placeholders locally:

```dotenv
AIRPORT_MODEL_PROVIDER=ollama
AIRPORT_MODEL_NAME=llama3.1:8b
AIRPORT_OLLAMA_MODEL_NAME=llama3.1:8b
AIRPORT_OPENAI_API_KEY=YOUR_GROQ_KEY
AIRPORT_OPENAI_BASE_URL=https://api.groq.com/openai/v1
AIRPORT_OPENAI_MODEL_NAME=openai/gpt-oss-20b
AIRPORT_HOSTED_FREE_PLAN=true
AIRPORT_HOSTED_MAX_INPUT_TOKENS=16000
AIRPORT_HOSTED_MAX_OUTPUT_TOKENS=4096
AIRPORT_HOSTED_FREE_MONTHLY_REQUEST_LIMIT=100
AIRPORT_HOSTED_FREE_MONTHLY_TOKEN_LIMIT=1000000
AIRPORT_HOSTED_PRODUCT_IMPROVEMENT_TERMS=REPLACE_WITH_REVIEWED_TERMS_AND_DATA_CONTROL_SETTINGS
LANGSMITH_TRACING=false
```

Only set `AIRPORT_HOSTED_FREE_PLAN=true` after step 1. The quota values above are
conservative application allowances, not verified Groq entitlements; lower them if needed.
No dollar rates are required for confirmed free inference. Tracing, if enabled separately,
still needs a bounded charge and shares the USD 10 budget.

Restart the app, explicitly select **Groq (hosted, verified free plan)**, and review
the provider/model/endpoint/data-use notice. The reused `AIRPORT_OPENAI_*` variable names
refer to the OpenAI-compatible protocol; the key must be from Groq, not OpenAI.
The sidebar **Groq model** selector offers `openai/gpt-oss-20b` and
`openai/gpt-oss-120b`. If 20B hits a provider limit, explicitly select 120B, review the
updated processing notice and submit again only if your free account permits it.
There is no automatic retry or model fallback. Groq organization/model limits still
apply, and a different model is not guaranteed to have remaining quota. Selecting it
does not reset or bypass the application's shared hosted-budget/quota ledger.
In non-production/development mode only (`production=false`), a verified free-plan
configuration uses provider-enforced limits
instead of the additional local monthly request/token allowances. The sidebar explicitly
shows this policy. Usage, including uncertain reservations, is still recorded; the USD
spending cap and paid-request safeguards remain enforced. Production and evaluation
runs retain the local monthly free quotas. This policy does not depend on authentication
method or enable development sign-in. This policy does not predict
provider quota availability or enable retries, automatic switching or paid overage.
To default directly to Groq, set `AIRPORT_MODEL_PROVIDER=groq` and
`AIRPORT_MODEL_NAME=openai/gpt-oss-20b`.

Official references: [API compatibility](https://console.groq.com/docs/openai),
[structured outputs](https://console.groq.com/docs/structured-outputs),
[limits](https://console.groq.com/docs/rate-limits), and
[data controls](https://console.groq.com/docs/your-data).

### Other hosted processing

Hosted inference is not needed for the local path above. To enable it, an operator must
configure the OpenAI-compatible credentials, model, current rates or verified free-plan
quotas, fee/FX bounds, and data-use terms in the process environment or local `.env`,
using [.env.example](.env.example) as a reference. Set both
`AIRPORT_MODEL_NAME` and `AIRPORT_OPENAI_MODEL_NAME` to the intended hosted model when
`AIRPORT_MODEL_PROVIDER=openai`.

Select the hosted provider explicitly and review its notice before submitting a question.
Hosted-processing acknowledgement defaults to on; turn it off to block submission.
The choice is retained when switching away and back to the same provider/model/terms.
LangSmith acknowledgement also defaults to on when operator-configured tracing is enabled;
turning it off blocks submission. These defaults do not enable tracing itself or bypass
credentials, fees, quotas, or the monthly budget.
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
| Development sign-in is blocked | Set `AIRPORT_PRODUCTION=false` and launch with `--server.address=127.0.0.1`. Do not expose the development server externally. |
| Model unavailable | Check Ollama is running, `/api/tags` lists the configured model, and the endpoint is correct. There is no automatic fallback. |
| Provider HTTP 400 or 422 | The provider rejected the request/schema or parameters. Use the current app version and restart Streamlit after updates. Groq's V2 wire schema removes overlapping integer/number alternatives and merges same-type string enums; the full schema is still validated locally. |
| Provider HTTP 401/403/404 | Check the API key locally, model permissions, and endpoint/model configuration. Never share the key in logs or chat. |
| Provider HTTP 429 | Check the provider's request/token limits and wait; the app does not retry automatically. Unknown-acceptance reservations stay held until reconciliation. |
| Dataset unavailable | Check the working directory, source-data setting, and all five original CSVs. |
| Hosted submit disabled | Acknowledge provider processing and, if enabled, tracing notices. |
| Hosted input/cost bound rejected | The operator must review token ceilings, tokenizer support, current rates, and fee bounds. Do not disable validation. |
| No records or unsupported question | Broaden filters or ask about supported connectivity, delays, airlines, or aircraft metrics. |
| Browser shows `Unknown request URL: GET /openai/v1` | This is an API base URL, not a web page. Leave the configured base URL unchanged; use the app to send chat-completions requests. |
| Provider HTTP 400 | This can mean a rejected request/schema or a generated response that failed provider validation. Share only the app's safe `Code` and `Rejected parameter` details when present, never raw response bodies or keys. `json_validate_failed` identifies a generated-output validation failure. Do not change providers or disable validation to bypass it. |
| Question says "the airport" without naming one | With V2 enabled, a valid ambiguous response opens **Pending analysis** with a focused question. Submit a locally validated choice or a free-text clarification. Three unresolved answered turns lead to guided correction, not unlimited model calls. |
| V2 says it could not safely interpret the question | Invalid structured output is a provider-output failure, not a valid clarification. Use explicit **Retry interpretation**, structured correction, restart or cancel. No hidden repair or provider switch occurs. Missing coverage or weather-unit evidence needs a local evidence/definition correction, not invented data. |

The snapshot is historical, not live flight data. Weather comparisons are contextual, not
causal. Live provider/model evaluation, latency baselining, owner retention approval, five
analyst sessions, and the full accessibility review remain pending. Automated tests are
not evidence that those release gates have been completed.

For developer checks, run `python -m pytest` and `python -m ruff check .`.
See [README.md](README.md) for architecture and
[the task list](specs/001-airport-analytics-platform/tasks.md) for remaining work.
