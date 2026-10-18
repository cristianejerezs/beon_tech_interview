# Identity, authorization, and consent

[Documentation home](README.md) | [Previous: CSV, ZIP, and PDF exports](exports.md) | [Next: Configuration reference](configuration.md)

Implementation reference: 2026-10-18. See [scope and status](README.md#scope-and-status).

- [Authentication, authorization, consent, and disclosure](#authentication-authorization-consent-and-disclosure)
  - [Normal OIDC identity](#normal-oidc-identity)
  - [Development sign-in](#development-sign-in)
  - [Three independent permissions](#three-independent-permissions)
  - [Consent and shared artifacts](#consent-and-shared-artifacts)
  - [Production status](#production-status)

## Authentication, authorization, consent, and disclosure

### Normal OIDC identity

Streamlit handles the sign-in session. The app requires stable string `iss` and `sub` claims.
It derives the analyst ID as SHA-256 over a namespaced, separator-delimited issuer/subject
material. Email/display name is not the ownership key.

Private report reads/writes/deletes/preferences check this owner identity. The hash is
pseudonymous, not a claim that all stored/report text is anonymous.

### Development sign-in

The bypass requires `AIRPORT_DEV_SIGN_IN_ENABLED=true`, `AIRPORT_PRODUCTION=false`, and an
explicit `localhost`, `127.0.0.1` or `::1` server address.
Every development session shares one deterministic development identity/history.

It is not authentication. Do not expose it through a proxy, tunnel or public bind.
Sign-out clears session state but does not delete saved reports. Container binding to
`0.0.0.0` intentionally fails this bypass check.

### Three independent permissions

| Permission | Authorizes | Does not authorize |
|---|---|---|
| Sign-in/ownership | Access to the analyst's private records | Sending data to a provider or publishing shared copies |
| Hosted/tracing acknowledgement | Configured external processing/trace path | FAQ/system-improvement sharing |
| Session/purpose reuse grant | Creating the permitted separate shared copy | Access to another analyst's private history |

Provider disclosure is keyed by provider, model and declared product-improvement terms.
Changing model/terms requires the applicable signature. A cache hit still checks disclosure.

### Consent and shared artifacts

Purposes are `faq` and `system_improvement`. Grants/withdrawals are append-only events tied
to analyst, session, purpose and notice version. Active authorization requires agreement
between current session state and the latest persisted event.

Deployment reuse defaults disabled. Development sign-in enables reuse testing, but the
session/purpose controls still apply. In production, reuse also requires the explicit
retention-policy approval assertion.

Where deployment policy permits, UI reuse choices and provider/tracing acknowledgements default
on. They are disclosed default selections, **not proof of an affirmative consent click**.
The current consent notice version is `v2-default-on`. A withdrawal stops future reuse but
does not remove already-shared copies.

Shared copies are reduced summaries, not private-report access tokens. They omit analyst/session
identity and record-level listing/relationship data. Shared FAQ browsing is separate from private
history. Selecting a FAQ question fills the input; it does not bypass current generation gates.
Summary rows are bounded to ten per section (ten for a V1 summary). The authorizing grant
must belong to the report's analyst/session/purpose, still be the latest grant, and have occurred
no later than report creation. Granting consent after creating a report does not retroactively
authorize sharing that report.

### Production status

[The retention checklist](../privacy-data-retention.md) is explicitly not approved.
Keep production shared reuse disabled until the owner approves durations, deletion/backup handling,
provider terms, operator access and the default-on authorization UX.

---

[Documentation home](README.md) | [Previous: CSV, ZIP, and PDF exports](exports.md) | [Next: Configuration reference](configuration.md)
