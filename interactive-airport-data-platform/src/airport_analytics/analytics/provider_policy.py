"""Per-session hosted-provider processing disclosures, independent of reuse consent."""

from __future__ import annotations

from collections.abc import MutableMapping
from dataclasses import dataclass

from airport_analytics.errors import DisclosureRequiredError

DISCLOSURES_KEY = "airport_provider_disclosures"


@dataclass(frozen=True)
class ProviderDescriptor:
    provider_id: str
    model_id: str
    product_improvement_terms: str
    hosted: bool = True


def _signature(provider: ProviderDescriptor) -> tuple[str, str]:
    return provider.model_id, provider.product_improvement_terms


def has_disclosed(session_state: MutableMapping[str, object], provider: ProviderDescriptor) -> bool:
    if not provider.hosted:
        return False
    disclosures = session_state.get(DISCLOSURES_KEY, {})
    if not isinstance(disclosures, dict):
        raise ValueError("Hosted-provider disclosure state has an invalid shape.")
    return disclosures.get(provider.provider_id) == _signature(provider)


def mark_disclosed(
    session_state: MutableMapping[str, object], provider: ProviderDescriptor
) -> None:
    if not provider.hosted:
        return
    disclosures = session_state.setdefault(DISCLOSURES_KEY, {})
    if not isinstance(disclosures, dict):
        raise ValueError("Hosted-provider disclosure state has an invalid shape.")
    disclosures[provider.provider_id] = _signature(provider)


def require_disclosed(
    session_state: MutableMapping[str, object], provider: ProviderDescriptor
) -> None:
    if provider.hosted and not has_disclosed(session_state, provider):
        raise DisclosureRequiredError()
