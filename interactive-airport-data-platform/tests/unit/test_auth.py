import pytest

from airport_analytics.auth import (
    require_owner,
    resolve_analyst_identity,
    resolve_development_identity,
)
from airport_analytics.errors import AuthorizationError


def test_identity_is_derived_from_stable_oidc_issuer_and_subject() -> None:
    first = resolve_analyst_identity("https://issuer.example", "subject-123")
    same = resolve_analyst_identity("https://issuer.example", "subject-123")
    changed_email_is_not_an_identity_input = resolve_analyst_identity(
        "https://issuer.example", "subject-123"
    )
    assert first.analyst_id == same.analyst_id == changed_email_is_not_an_identity_input.analyst_id
    assert (
        first.analyst_id
        != resolve_analyst_identity("https://issuer.example", "subject-456").analyst_id
    )


@pytest.mark.parametrize(("issuer", "subject"), [(None, "sub"), ("issuer", None), ("", "")])
def test_missing_oidc_claims_fail_closed(issuer: str | None, subject: str | None) -> None:
    with pytest.raises(AuthorizationError):
        resolve_analyst_identity(issuer, subject)


def test_ownership_guard_rejects_another_analyst() -> None:
    alice = resolve_analyst_identity("issuer", "alice")
    bob = resolve_analyst_identity("issuer", "bob")
    require_owner(alice, alice.analyst_id)
    with pytest.raises(AuthorizationError):
        require_owner(alice, bob.analyst_id)


@pytest.mark.parametrize("address", ["localhost", "127.0.0.1", "::1"])
def test_development_identity_is_stable_and_distinct_from_oidc(address: str) -> None:
    identity = resolve_development_identity(production=False, server_address=address)
    assert identity == resolve_development_identity(production=False, server_address="127.0.0.1")
    oidc_identity = resolve_analyst_identity("https://issuer.example", identity.subject)
    assert identity.analyst_id != oidc_identity.analyst_id
    with pytest.raises(AuthorizationError):
        require_owner(identity, oidc_identity.analyst_id)


@pytest.mark.parametrize("address", [None, "", "0.0.0.0", "::", "192.168.1.10"])
def test_development_identity_requires_explicit_loopback_binding(address: str | None) -> None:
    with pytest.raises(AuthorizationError):
        resolve_development_identity(production=False, server_address=address)


def test_development_identity_is_prohibited_in_production() -> None:
    with pytest.raises(AuthorizationError):
        resolve_development_identity(production=True, server_address="127.0.0.1")
