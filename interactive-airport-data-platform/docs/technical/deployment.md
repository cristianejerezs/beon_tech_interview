# Local setup and deployment

[Documentation home](README.md) | [Previous: Configuration reference](configuration.md) | [Next: Testing, evaluation, and observability](testing-and-observability.md)

Implementation reference: 2026-10-18. See [scope and status](README.md#scope-and-status).

- [Runtime setup](#runtime-setup)
  - [Windows development](#windows-development)
  - [OIDC configuration](#oidc-configuration)
  - [PDF prerequisites](#pdf-prerequisites)
  - [Docker](#docker)
  - [Operating boundaries](#operating-boundaries)

## Runtime setup

### Windows development

Create an environment only if needed. The existing project-adjacent `beon` environment can
instead be invoked directly with `..\beon\Scripts\python.exe`.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
}
```

For local Ollama, start the service and provision the configured model:

```powershell
ollama pull llama3.1:8b
Invoke-RestMethod "http://localhost:11434/api/tags"
```

For trusted-machine development only, set the development/production flags appropriately and run:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address=127.0.0.1
```

The UI is available at `http://127.0.0.1:8501`. Stop with Ctrl+C.

### OIDC configuration

Normal deployment uses a local, uncommitted `.streamlit\secrets.toml`:

```toml
[auth]
redirect_uri = "http://localhost:8501/oauth2callback"
cookie_secret = "REPLACE_WITH_A_LOCALLY_GENERATED_RANDOM_SECRET"
client_id = "REPLACE_WITH_REGISTERED_CLIENT_ID"
client_secret = "REPLACE_WITH_REGISTERED_CLIENT_SECRET"
server_metadata_url = "https://YOUR_ISSUER/.well-known/openid-configuration"
```

Register the exact redirect URI with the provider. Production needs HTTPS and corresponding
redirect/cookie/proxy configuration. The current app calls unnamed `st.login()`, so use the
default `[auth]` configuration. Require issuer/subject claims.

Generate secrets locally, never in a committed example. Missing Authlib should be addressed
by installing the declared authentication dependencies into the **same interpreter** running
Streamlit, not by installing into an unrelated Python environment.

### PDF prerequisites

- Linux: install Pango, PangoFT2 and HarfBuzz subset libraries.
- macOS: install Pango through the supported local package manager.
- Windows: install MSYS2 UCRT64 Pango and use the documented DLL discovery/override.
- Docker: the supplied image installs the required native libraries and checks runtime loading.

The browser can continue without these, but V2 PDF exports cannot.

### Docker

[Dockerfile](../../Dockerfile) defines `runtime` and `test` stages based on
`python:3.12-slim-bookworm`. It installs native PDF libraries, creates non-root UID 10001,
copies source/schema/data, installs the project editable, and checks the PDF runtime.

Build:

```powershell
docker build --target runtime -t airport-analytics .
```

Use normal OIDC, not the development bypass. A container binds `0.0.0.0`; external networking
must be limited by deployment/firewall/proxy policy.
The following PowerShell example mounts secrets and durable storage, without baking them in:

```powershell
$secretsPath = (Resolve-Path ".\.streamlit\secrets.toml").Path
New-Item -ItemType Directory -Path ".\var" -Force | Out-Null
$statePath = (Resolve-Path ".\var").Path
docker run --rm -p 127.0.0.1:8501:8501 --env-file ".env" `
  --mount "type=bind,source=$secretsPath,target=/app/.streamlit/secrets.toml,readonly" `
  --mount "type=bind,source=$statePath,target=/app/var" `
  airport-analytics
```

Ensure the container user can write mounted state. Container environment paths must refer
to container locations, not Windows host paths. On Docker Desktop, host Ollama generally
uses `http://host.docker.internal:11434`, not container `localhost`.

The Docker health check requests `/_stcore/health` every 30 seconds after a startup grace
period. An `ok` response proves Streamlit responds; it does not verify OIDC, credentials,
source correctness, model acceptance, or a successful report export.

[.dockerignore](../../.dockerignore) excludes local secrets/state, report artifacts and tooling.
The image includes the supplied source dataset. Decide whether that is appropriate before
distributing an image to another environment.

### Operating boundaries

This is a single-host MVP with no HA/throughput/uptime SLA. SQLite WAL, process-local pacing,
process-local caches and a cached DuckDB executor are not a distributed deployment design.
Do not scale replicas without a deliberate shared-ledger, concurrency, source-binding and
provider-rate coordination design.

---

[Documentation home](README.md) | [Previous: Configuration reference](configuration.md) | [Next: Testing, evaluation, and observability](testing-and-observability.md)
