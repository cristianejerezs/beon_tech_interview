import pytest

from airport_analytics.analytics.provider_policy import (
    ProviderDescriptor,
    has_disclosed,
    mark_disclosed,
    require_disclosed,
)
from airport_analytics.errors import DisclosureRequiredError


def test_hosted_provider_requires_session_disclosure_before_each_first_call() -> None:
    session: dict[str, object] = {}
    provider = ProviderDescriptor("openai", "model-a", "may improve products")
    assert not has_disclosed(session, provider)
    with pytest.raises(DisclosureRequiredError):
        require_disclosed(session, provider)

    mark_disclosed(session, provider)
    require_disclosed(session, provider)
    assert has_disclosed(session, provider)


def test_provider_model_or_terms_change_requires_a_new_disclosure() -> None:
    session: dict[str, object] = {}
    first = ProviderDescriptor("openai", "model-a", "may improve products")
    mark_disclosed(session, first)
    assert not has_disclosed(
        session, ProviderDescriptor("openai", "model-b", "may improve products")
    )
    assert not has_disclosed(
        session, ProviderDescriptor("openai", "model-a", "does not improve products")
    )


def test_local_provider_needs_no_hosted_provider_disclosure() -> None:
    session: dict[str, object] = {}
    local = ProviderDescriptor("ollama", "local-model", "not applicable", hosted=False)
    require_disclosed(session, local)
    assert not has_disclosed(session, local)
