"""LangChain structured plan generation with explicit provider, disclosure, and budget gates."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from typing import Any

import httpx
import tiktoken
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from openai import APIConnectionError, APIStatusError, APITimeoutError

from airport_analytics.analytics.budget import BudgetLedger, BudgetReservation
from airport_analytics.analytics.plan_schema import (
    SCHEMA_PATH,
    _load_schema,
    validate_analysis_plan,
)
from airport_analytics.analytics.provider_policy import (
    ProviderDescriptor,
    require_disclosed,
)
from airport_analytics.analytics.question_validation import validate_question
from airport_analytics.config import Settings
from airport_analytics.data.catalog import DIMENSIONS, FIELDS, METRICS
from airport_analytics.errors import (
    CostUnboundedError,
    InvalidPlanError,
    ProviderConnectionError,
    ProviderError,
    ProviderRequestError,
    ProviderTimeoutError,
)
from airport_analytics.models import AnalysisPlan, ProviderUsage
from airport_analytics.observability.tracing import TracingConfig

LOGGER = logging.getLogger(__name__)


def _groq_output_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Project only provider-supported shape constraints; retain full local validation."""
    allowed = {
        "title",
        "description",
        "type",
        "enum",
        "properties",
        "required",
        "additionalProperties",
        "items",
        "anyOf",
    }
    result: dict[str, Any] = {}
    for key, value in schema.items():
        if key == "properties":
            result[key] = {name: _groq_output_schema(item) for name, item in value.items()}
        elif key in {"anyOf", "oneOf"}:
            result["anyOf"] = [_groq_output_schema(item) for item in value]
        elif key == "items":
            result[key] = _groq_output_schema(value)
        elif key in allowed:
            result[key] = value
    return result


def _safe_provider_error(error: Exception) -> ProviderError:
    if isinstance(error, (APITimeoutError, httpx.TimeoutException, TimeoutError)):
        return ProviderTimeoutError()
    if isinstance(error, (APIConnectionError, httpx.ConnectError, ConnectionError)):
        return ProviderConnectionError()
    status = getattr(error, "status_code", None)
    if isinstance(error, APIStatusError):
        status = error.status_code
    if isinstance(status, int) and 400 <= status <= 599:
        return ProviderRequestError(status)
    return ProviderError()


@dataclass(frozen=True)
class FollowUpContext:
    previous_question: str
    previous_plan: AnalysisPlan

    def __post_init__(self) -> None:
        previous_question = validate_question(self.previous_question)
        object.__setattr__(self, "previous_question", previous_question)
        if self.previous_plan.status != "ready":
            raise ValueError("Follow-up context must refer to a previously validated plan.")


@dataclass(frozen=True)
class PlanGenerationResult:
    plan: AnalysisPlan
    usage: ProviderUsage
    budget_reservation_id: str | None
    trace_reservation_id: str | None


def _build_chat_model(settings: Settings) -> BaseChatModel:
    settings.validate_model_selection()
    if settings.model_provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=settings.model_name,
            base_url=settings.ollama_base_url,
            temperature=0,
            num_predict=settings.max_output_tokens,
            timeout=settings.model_timeout_seconds,
        )

    from langchain_openai import ChatOpenAI

    options: dict[str, Any] = {
        "model": settings.model_name,
        "api_key": settings.openai_api_key,
        "temperature": 0,
        "max_tokens": settings.max_output_tokens,
        "timeout": settings.model_timeout_seconds,
        "max_retries": 0,
    }
    if settings.openai_base_url:
        options["base_url"] = settings.openai_base_url
    if settings.model_provider == "groq":
        options["reasoning_effort"] = "low"
    return ChatOpenAI(**options)


def _catalog_context() -> str:
    metrics = [
        {
            "id": item.metric_id,
            "description": item.description,
            "unit": item.unit,
            "population": item.population,
            "allowed_group_by": sorted(
                item.allowed_dimensions
                if item.allowed_dimensions is not None
                else DIMENSIONS.keys()
            ),
        }
        for item in METRICS.values()
    ]
    dimensions = [{"id": item.dimension_id} for item in DIMENSIONS.values()]
    fields = [
        {"id": item.field_id, "type": item.data_type} for item in FIELDS.values() if item.filterable
    ]
    return json.dumps(
        {"metrics": metrics, "dimensions": dimensions, "filter_fields": fields},
        separators=(",", ":"),
    )


class LangChainPlanClient:
    def __init__(
        self,
        settings: Settings,
        *,
        budget: BudgetLedger | None = None,
        tracing: TracingConfig | None = None,
        model: BaseChatModel | None = None,
    ) -> None:
        settings.validate_model_selection()
        if settings.model_provider == "groq":
            if not settings.hosted_free_plan:
                raise CostUnboundedError("Groq support requires a verified free plan.")
            if settings.openai_base_url != "https://api.groq.com/openai/v1":
                raise ValueError(
                    "Groq requires the official https://api.groq.com/openai/v1 endpoint."
                )
            if settings.model_name not in {"openai/gpt-oss-20b", "openai/gpt-oss-120b"}:
                raise ValueError("Groq support currently requires a GPT-OSS 20B or 120B model.")
        self.settings = settings
        self.budget = budget
        self.tracing = tracing or TracingConfig(enabled=False, maximum_charge_per_trace_usd=None)
        self.tracing.apply()
        self.hosted = settings.model_provider != "ollama"
        if self.hosted and budget is None:
            raise ValueError("A persistent budget ledger is required for hosted model use.")
        self.provider = ProviderDescriptor(
            provider_id=settings.model_provider,
            model_id=settings.model_name,
            product_improvement_terms=(
                settings.hosted_product_improvement_terms if self.hosted else "not applicable"
            ),
            hosted=self.hosted,
        )
        self.chat_model = model or _build_chat_model(settings)
        self.schema = _load_schema(str(SCHEMA_PATH.resolve()))
        output_options: dict[str, Any] = {"method": "json_schema", "include_raw": True}
        output_schema = self.schema
        if settings.model_provider == "groq":
            output_schema = _groq_output_schema(self.schema)
            output_schema["title"] = "airport_analysis_plan"
            output_options["strict"] = True
        self.structured_model = self.chat_model.with_structured_output(
            output_schema, **output_options
        )
        self._schema_json = json.dumps(self.schema, separators=(",", ":"))
        self._catalog_json = _catalog_context()

    def _messages(
        self, question: str, follow_up_context: FollowUpContext | None
    ) -> list[SystemMessage | HumanMessage]:
        context = (
            {
                "previous_question": follow_up_context.previous_question,
                "previous_plan": follow_up_context.previous_plan.model_dump(mode="json"),
            }
            if follow_up_context
            else None
        )
        system = (
            "Return one JSON analysis plan conforming exactly to the supplied JSON Schema. "
            "Never return or execute SQL. Use only the supplied catalog IDs. If the request is "
            "ambiguous, return needs_clarification with one concise question. If unavailable, "
            "return unsupported. The historical flight snapshot covers NYC-area origins "
            "EWR, JFK, and LGA in 2013. If a question refers to 'the airport' without naming "
            "one, and active follow-up context does not identify one, ask which airport; "
            "do not guess or substitute all airports. For needs_clarification or unsupported, "
            "set intent, metric_id, time_range, sort, and chart_intent to null, "
            "group_by and filters to empty arrays, and row_limit to 10. "
            "For ready plans, group_by must be a subset of the chosen metric's allowed_group_by. "
            "Use filters to restrict an airport, not group_by unless a breakdown is requested. "
            "For an overall aggregate use group_by=[] and chart_intent='table'. "
            "An unspecified time range must be null, never an object with two null dates. "
            "Sort only by the selected metric ID or an active group_by ID, never 'metric_value'. "
            "No source rows, private history, credentials, or analyst "
            "identifiers are available. Catalog: "
            + self._catalog_json
            + " Schema: "
            + self._schema_json
        )
        human = json.dumps(
            {"question": question, "active_follow_up_context": context},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return [SystemMessage(content=system), HumanMessage(content=human)]

    def _count_prompt_tokens(self, messages: list[SystemMessage | HumanMessage]) -> int:
        if not self.hosted:
            return 0
        try:
            if self.settings.model_provider == "groq":
                # GPT-OSS uses Harmony, not the OpenAI chat-model name lookup.
                encoding = tiktoken.get_encoding("o200k_harmony")
                prompt_count = sum(
                    len(encoding.encode(str(message.content), disallowed_special=()))
                    for message in messages
                )
                # Conservative framing allowance; actual usage is settled from the provider.
                prompt_count += 1024
            else:
                prompt_count = self.chat_model.get_num_tokens_from_messages(messages)
                encoding = tiktoken.encoding_for_model(self.settings.model_name)
            schema_count = len(encoding.encode(self._schema_json))
        except (KeyError, ValueError, NotImplementedError) as exc:
            raise CostUnboundedError(
                "The configured hosted model tokenizer is unavailable; request was not sent."
            ) from exc
        # The provider transmits the structured-output schema separately as well as in the prompt.
        total = prompt_count + schema_count + 64
        if total > self.settings.max_input_tokens:
            raise CostUnboundedError(
                "The prompt exceeds the configured hosted input-token ceiling."
            )
        return total

    @staticmethod
    def _response_parts(response: Any) -> tuple[Any, Any, Exception | None]:
        if isinstance(response, Mapping) and "parsed" in response:
            return response.get("parsed"), response.get("raw"), response.get("parsing_error")
        return response, None, None

    @staticmethod
    def _usage(raw: Any) -> ProviderUsage:
        usage: Mapping[str, Any] = {}
        if raw is not None:
            metadata = getattr(raw, "usage_metadata", None)
            if isinstance(metadata, Mapping):
                usage = metadata
            if not usage:
                response_metadata = getattr(raw, "response_metadata", None)
                if isinstance(response_metadata, Mapping):
                    token_usage = response_metadata.get("token_usage", {})
                    if isinstance(token_usage, Mapping):
                        usage = {
                            "input_tokens": token_usage.get("prompt_tokens"),
                            "output_tokens": token_usage.get("completion_tokens"),
                        }
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
        return ProviderUsage(
            input_tokens=input_tokens if isinstance(input_tokens, int) else None,
            output_tokens=output_tokens if isinstance(output_tokens, int) else None,
        )

    def _reserve_inference(self, messages: list[SystemMessage | HumanMessage]) -> BudgetReservation:
        if not self.hosted or self.budget is None:
            raise ValueError("Only hosted model calls require an inference reservation.")
        self._count_prompt_tokens(messages)
        return self.budget.reserve(
            provider_id=self.provider.provider_id,
            model_id=self.provider.model_id,
            max_input_tokens=self.settings.max_input_tokens,
            max_output_tokens=self.settings.max_output_tokens,
            input_usd_per_million=self.settings.hosted_input_usd_per_million,
            output_usd_per_million=self.settings.hosted_output_usd_per_million,
            fee_fx_multiplier=self.settings.provider_fees_fx_multiplier,
            maximum_extra_fee_usd=self.settings.max_extra_fee_usd_per_request,
            free_plan=self.settings.hosted_free_plan,
        )

    def generate_plan(
        self,
        question: object,
        *,
        session_state: MutableMapping[str, object],
        follow_up_context: FollowUpContext | None = None,
    ) -> PlanGenerationResult:
        trimmed_question = validate_question(question)
        if self.hosted:
            require_disclosed(session_state, self.provider)

        messages = self._messages(trimmed_question, follow_up_context)
        inference_reservation = self._reserve_inference(messages) if self.hosted else None
        trace_reservation: BudgetReservation | None = None
        try:
            if (
                self.tracing.enabled
                and self.tracing.maximum_charge_per_trace_usd is not None
                and self.budget is not None
            ):
                trace_reservation = self.budget.reserve_cost(
                    provider_id="langsmith-tracing",
                    model_id=self.settings.model_name,
                    maximum_charge_usd=self.tracing.maximum_charge_per_trace_usd,
                )
        except Exception:
            if inference_reservation is not None and self.budget is not None:
                self.budget.release_before_dispatch(inference_reservation.reservation_id)
            raise

        try:
            response = self.structured_model.invoke(messages)
        except Exception as exc:
            if inference_reservation is not None and self.budget is not None:
                self.budget.mark_uncertain(
                    inference_reservation.reservation_id,
                    "provider acceptance is unknown after a failed call; no automatic retry",
                )
            if trace_reservation is not None and self.budget is not None:
                self.budget.settle(
                    trace_reservation.reservation_id,
                    actual_usd=trace_reservation.reserved_usd,
                )
            safe_error = _safe_provider_error(exc)
            LOGGER.warning(
                "Model call failed: provider=%s category=%s",
                self.settings.model_provider,
                safe_error.code,
            )
            raise safe_error from exc

        parsed, raw, parsing_error = self._response_parts(response)
        usage = self._usage(raw)
        if inference_reservation is not None and self.budget is not None:
            self.budget.settle(
                inference_reservation.reservation_id,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
            )
        if trace_reservation is not None and self.budget is not None:
            self.budget.settle(
                trace_reservation.reservation_id,
                actual_usd=trace_reservation.reserved_usd,
            )
        if parsing_error is not None or parsed is None:
            raise InvalidPlanError("The provider did not return a valid structured plan.") from (
                parsing_error
            )

        payload = parsed.model_dump(mode="json") if isinstance(parsed, AnalysisPlan) else parsed
        plan = validate_analysis_plan(payload)
        return PlanGenerationResult(
            plan=plan,
            usage=usage,
            budget_reservation_id=(
                inference_reservation.reservation_id if inference_reservation else None
            ),
            trace_reservation_id=(trace_reservation.reservation_id if trace_reservation else None),
        )
