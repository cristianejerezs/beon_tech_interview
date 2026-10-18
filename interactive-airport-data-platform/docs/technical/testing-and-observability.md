# Testing, evaluation, and observability

[Documentation home](README.md) | [Previous: Local setup and deployment](deployment.md) | [Next: Extension guide, limitations, and glossary](engineering-guide.md)

Implementation reference: 2026-10-18. See [scope and status](README.md#scope-and-status).

- [Observability and troubleshooting](#observability-and-troubleshooting)
  - [Timing and safe logs](#timing-and-safe-logs)
  - [Error handling](#error-handling)
- [Testing and evaluation](#testing-and-evaluation)
  - [Test organization](#test-organization)
  - [Commands](#commands)
  - [Explicit provider evaluation](#explicit-provider-evaluation)

## Observability and troubleshooting

### Timing and safe logs

`capture_stage_timings()` and `timed_stage()` use context variables and avoid counting nested
instances of the same stage twice. Stages include source validation, interpretation, execution,
table preparation, server preparation, visual preparation and export generation.

Visual preparation telemetry records duration, platform/Python, known visual family, evidence
size and a classified failure category. It is not operational question/result tracing.
Provider logs can record model/token counts, pacing duration and safe failure category.

There is no implemented metrics dashboard or centralized log shipping configuration.
Operators should distinguish safe classified messages from unexpected exception logs,
which still require controlled access.

### Error handling

Expected failures subclass `PlatformError`. `user_safe_message()` exposes deliberate safe
messages, not arbitrary exception details. Unknown exceptions become the generic
"An unexpected error occurred..." response, while the UI logs the exception for diagnosis.

| Symptom | Likely layer and action |
|---|---|
| Generic unexpected error | Inspect server traceback; do not infer the cause from the generic browser message. |
| Authentication requires Authlib | Verify current interpreter and install the declared `streamlit[auth]` dependency set there. |
| Development sign-in rejected | Check production flag and explicit loopback bind; never weaken the restriction for a public container. |
| Hosted model missing in sidebar | Configure credential and hosted model, restart, then explicitly select the provider. |
| Input ceiling exceeded | Inspect prompt/schema size and configured maximum; do not remove validation to fit it. |
| HTTP 400 structured response failure | Inspect allowlisted error code/parameter; malformed output must not reach execution. |
| HTTP 429 | Read minute/day distinction and reported wait; one bounded retry may already have occurred. |
| Budget/quota exhausted | Inspect actual/reserved ledger totals and uncertainty, not only settled token usage. |
| Provider timeout | Acceptance may be unknown; reconcile before releasing a held reservation. |
| Dataset unavailable | Check source filenames/schema/keys/content; saved evidence can remain readable. |
| Historical paging unavailable | Current snapshot/context differs; start a new analysis instead of substituting data. |
| Calendar mean unavailable | Supply verified coverage or explicitly choose recorded operating days. |
| Weather limitation | Check exact weather join eligibility and verified unit evidence; provisional Pearson and unit-dependent comparisons differ. |
| Bin-width confirmation required | Accept a sufficiently wide bin or narrow scope; more than 100 bins is not silently accepted. |
| PDF disabled | Install native Pango/use Docker; do not silently substitute an untagged V2 PDF. |
| Preference conflict | Refresh preference state and explicitly reapply. |
| Incomplete report not saved | Acknowledge the exact failed sections/revision; inspect unsaved report state. |
| Corrupt/unsupported report version | Preserve payload for investigation; do not auto-migrate by overwriting it. |

Some existing UI captions still describe older behavior (for example, no automatic retries or
charts awaiting implementation). For control-flow decisions use the implementation paths and
the limitations below, not a stale caption alone.
## Testing and evaluation

### Test organization

| Location | Coverage |
|---|---|
| [unit](../../tests/unit) | Models, schema/catalog, compiler, config/auth, budget, state, visual rules |
| [integration](../../tests/integration) | DuckDB data/results, daily/weather semantics, report/history/consent, provider failures, exports |
| [browser](../../tests/browser) | Streamlit `AppTest` workflows and control behavior |
| [accessibility](../../tests/accessibility) | Labels/status alternatives and tagged-PDF structure checks |
| [performance](../../tests/performance) | Stage timing and explicitly authorized real-provider baseline |
| [fixtures](../../tests/fixtures) | Synthetic source snapshots, gold cases, historical reports and visual fixtures |
| [exploration_oracles.py](../../tests/exploration_oracles.py) | Independent expected analytical calculations |

The directory name `browser` does not mean every test is a real browser/Playwright run.
Streamlit AppTest does not certify screen-reader behavior, OIDC production integration,
native browser rendering or full end-user accessibility.

The autouse fixture removes local `AIRPORT_*` values and disables dotenv loading so a
developer's configuration does not contaminate test expectations.
Missing PDF runtime produces an explicit test skip. Read skipped-test reasons: an all-green
run with skipped PDF tests is not proof tagged export works on that machine.

### Commands

Full collection:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m ruff check src tests app.py
.\.venv\Scripts\python.exe -m ruff format --check src tests app.py
```

Known working baseline used during recent implementation, **with an explicit exclusion**:

```powershell
..\beon\Scripts\python.exe -m pytest tests -q -p no:cacheprovider `
  --deselect tests/unit/test_visual_preferences.py
```

The last preceding recorded run was 681 passed, one opt-in live-provider test skipped and
29 preference tests deselected. This documentation task does not claim that baseline was
rerun or that the excluded preference feature is complete.

Focused examples:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\integration\test_model_failure_modes.py tests\unit\test_budget.py -q
.\.venv\Scripts\python.exe -m pytest tests\integration\test_exploration_daily_metrics.py tests\integration\test_exploration_pair_metrics.py -q
.\.venv\Scripts\python.exe -m pytest tests\integration\test_report_exports.py tests\accessibility\test_visual_pdf_accessibility.py -q
```

Equivalent container test runtime:

```powershell
docker build --target test -t airport-analytics:test .
docker run --rm airport-analytics:test
```

The test-stage default runs the full collection, including unfinished preference tests.
It does not silently adopt the development exclusion above.

### Explicit provider evaluation

The internal CLI is available with:

```powershell
.\.venv\Scripts\python.exe -m airport_analytics.analytics.evaluation --help
```

Legacy live evaluation, only after authorizing provider usage:

```powershell
.\.venv\Scripts\python.exe -m airport_analytics.analytics.evaluation `
  --run-live --acknowledge-hosted-processing --suite legacy12
```

V2 additionally requires `--corpus`, `--gold`, and `--corpus-version`.
Inputs must have unique identities, matching corpus versions and valid gold references.
Tracing must be disabled. These commands send real requests and consume quota/budget;
ordinary documentation validation does not require running them.

V2 numeric/semantic gates include 100 unambiguous cases across ten families, at least 90
overall passes and eight per family, negative cases, airport-question variants, and all
generated results matching their gold. Human-independent review/freeze is a separate gate.
The current V2 CLI deliberately reports release blocked and exits nonzero even if numerical
thresholds pass, because independent release acceptance has not been verified.

Some evaluation metadata still describes zero automatic retries/older chart status; dispatch
now has the bounded 429 policy documented above. Do not treat that metadata as an exact
description of current provider transport without reconciling it.

---

[Documentation home](README.md) | [Previous: Local setup and deployment](deployment.md) | [Next: Extension guide, limitations, and glossary](engineering-guide.md)
