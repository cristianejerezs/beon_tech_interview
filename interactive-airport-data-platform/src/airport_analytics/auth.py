"""Stable OIDC identity derivation and ownership authorization."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from airport_analytics.errors import AuthorizationError


@dataclass(frozen=True)
class AnalystIdentity:
    analyst_id: str
    issuer: str
    subject: str


def resolve_analyst_identity(issuer: str | None, subject: str | None) -> AnalystIdentity:
    if not issuer or not subject or not issuer.strip() or not subject.strip():
        raise AuthorizationError("OIDC issuer and subject are required.")
    normalized_issuer = issuer.strip()
    stable_subject = subject.strip()
    material = f"airport-analytics-analyst-v1\0{normalized_issuer}\0{stable_subject}"
    analyst_id = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return AnalystIdentity(analyst_id, normalized_issuer, stable_subject)


def require_owner(identity: AnalystIdentity, resource_owner_id: str) -> None:
    if identity.analyst_id != resource_owner_id:
        raise AuthorizationError()


def resolve_development_identity(
    *, production: bool, server_address: str | None
) -> AnalystIdentity:
    if production:
        raise AuthorizationError("Development sign-in is prohibited in production.")
    if server_address not in {"localhost", "127.0.0.1", "::1"}:
        raise AuthorizationError("Development sign-in requires --server.address=127.0.0.1.")
    return resolve_analyst_identity("urn:airport-analytics:development", "local-developer")
