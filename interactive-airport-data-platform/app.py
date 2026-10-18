"""Streamlit interface for the Interactive Airport Data Platform."""

from __future__ import annotations

import logging
import os
import uuid
from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import streamlit as st

from airport_analytics.analytics.budget import BudgetLedger
from airport_analytics.analytics.execution import DuckDBExecutor
from airport_analytics.analytics.interpretation import apply_clarification_choice, correct_summary
from airport_analytics.analytics.model_client import FollowUpContext, LangChainPlanClient
from airport_analytics.analytics.provider_policy import (
    ProviderDescriptor,
    has_disclosed,
    mark_disclosed,
    revoke_disclosure,
)
from airport_analytics.analytics.query_compiler import listing_columns
from airport_analytics.analytics.request_state import (
    PENDING_REQUEST_KEY,
    AnswerEvent,
    ExplorationRequest,
    stop_request,
)
from airport_analytics.auth import (
    AnalystIdentity,
    resolve_analyst_identity,
    resolve_development_identity,
)
from airport_analytics.config import Settings
from airport_analytics.consent.repository import ConsentPurpose, ConsentRepository
from airport_analytics.consent.service import ConsentService
from airport_analytics.data.catalog import EXPLORATION_MEASURES, EXPLORATION_OPERATIONS
from airport_analytics.data.loader import DatasetLoader
from airport_analytics.errors import (
    DatasetUnavailableError,
    PdfRuntimeUnavailableError,
    PlatformError,
    user_safe_message,
)
from airport_analytics.history.repository import ReportRepository
from airport_analytics.models import (
    BrowsePage,
    CompositeReportV2,
    ExplorationOrder,
    FieldProvenance,
    GroupedResult,
    IncompleteAcknowledgement,
    IntentProposalV2,
    ListingResult,
    ProposedSharedScope,
    ReportContent,
    RequestDraft,
    ScalarResult,
    ScopeEdit,
    SectionPresentationPreference,
    SectionProposal,
    TimeRange,
)
from airport_analytics.observability.timing import timed_stage
from airport_analytics.observability.tracing import TracingConfig
from airport_analytics.reports.export import (
    bundle_export_selection,
    export_listing_csv,
    export_report_bundle,
    export_report_csv,
    export_report_pdf,
    listing_export_selection,
)
from airport_analytics.reports.generation import (
    ExplorationOutcome,
    ExplorationReportGenerator,
    ReportGenerator,
)
from airport_analytics.reports.rendering import render_report, section_evidence
from airport_analytics.storage import Storage

LOGGER = logging.getLogger(__name__)
NO_REPORT = "(No report selected)"
TRACING_ACK_KEY = "airport_langsmith_disclosure_acknowledged"
DEV_SIGN_IN_KEY = "airport_development_signed_in"
PROVIDER_LABELS = {
    "ollama": "Ollama (local)",
    "openai": "OpenAI (hosted)",
    "groq": "Groq (hosted, verified free plan)",
}
PURPOSE_LABELS: dict[ConsentPurpose, str] = {
    "faq": "FAQ examples",
    "system_improvement": "System improvement",
}


@st.cache_resource(show_spinner=False)
def _storage(database_path: str) -> Storage:
    return Storage(database_path)


@st.cache_resource(show_spinner="Validating the local source data...", max_entries=2)
def _snapshot_executor(
    source_data_dir: str,
    timeout_seconds: int,
    fingerprint: tuple[tuple[str, str], ...],
    coverage_path: str | None = None,
    coverage_content: bytes | None = None,
    weather_units_path: str | None = None,
    weather_units_content: bytes | None = None,
) -> DuckDBExecutor:
    executor = DuckDBExecutor(
        source_data_dir,
        timeout_seconds=timeout_seconds,
        coverage_path=coverage_path,
        weather_units_path=weather_units_path,
    )
    if DatasetLoader(source_data_dir).fingerprint() != fingerprint:
        executor.close()
        raise DatasetUnavailableError("Source files changed during validation; retry after saving.")
    return executor


def _executor(source_data_dir: str, timeout_seconds: int) -> DuckDBExecutor:
    fingerprint = DatasetLoader(source_data_dir).fingerprint()
    coverage_path = os.getenv("AIRPORT_COVERAGE_PATH") or None
    content = None
    if coverage_path:
        try:
            content = Path(coverage_path).read_bytes()
        except OSError:
            content = b""
            st.warning(
                "Configured coverage evidence is unavailable; complete-day coverage is unknown."
            )
    weather_units_path = os.getenv("AIRPORT_WEATHER_UNITS_PATH") or None
    units_content = None
    if weather_units_path:
        try:
            units_content = Path(weather_units_path).read_bytes()
        except OSError:
            units_content = b""
            st.warning("Configured weather units are unavailable; weather correlation is blocked.")
    return _snapshot_executor(
        source_data_dir,
        timeout_seconds,
        fingerprint,
        coverage_path,
        content,
        weather_units_path,
        units_content,
    )


def _identity() -> AnalystIdentity | None:
    if not getattr(st.user, "is_logged_in", False):
        return None
    claims = st.user.to_dict()
    issuer = claims.get("iss")
    subject = claims.get("sub")
    if not isinstance(issuer, str) or not isinstance(subject, str):
        return None
    return resolve_analyst_identity(issuer, subject)


def _client_settings(settings: Settings, provider: str) -> Settings:
    if provider == "ollama":
        local_model = os.getenv(
            "AIRPORT_OLLAMA_MODEL_NAME",
            settings.model_name if settings.model_provider == "ollama" else "llama3.1:8b",
        ).strip()
        return replace(settings, model_provider="ollama", model_name=local_model)
    hosted_model = os.getenv(
        "AIRPORT_OPENAI_MODEL_NAME",
        settings.model_name if settings.model_provider in {"openai", "groq"} else "",
    ).strip()
    if provider == "groq":
        hosted_model = st.session_state.get("selected_groq_model", hosted_model)
    return replace(settings, model_provider=provider, model_name=hosted_model)


def _report_label(report_id: str, labels: dict[str, str]) -> str:
    return labels.get(report_id, report_id)


def _safe_error(error: Exception) -> None:
    if isinstance(error, PlatformError):
        st.error(user_safe_message(error))
        return
    LOGGER.exception("Unhandled application error", exc_info=error)
    st.error(user_safe_message(error))


def _consent_panel(
    identity: AnalystIdentity,
    session_id: str,
    service: ConsentService,
) -> None:
    with st.expander("Optional sharing and reuse controls", expanded=True):
        st.write(
            "Session reuse choices default to on where deployment policy permits. "
            "Private analysis works without consent. If enabled, only the question, "
            "answer, metric definition, scope, and up to ten result rows are shared; "
            "your analyst identity is omitted. Withdrawal stops future reuse but does "
            "not remove material already shared."
        )
        for purpose, label in PURPOSE_LABELS.items():
            active = service.is_active(identity, session_id, purpose, st.session_state)
            disabled = not service.shared_reuse_enabled or (
                service.production and not service.retention_policy_approved
            )
            if not service.shared_reuse_enabled:
                st.caption("Shared reuse is disabled by deployment configuration.")
            if service.production and not service.retention_policy_approved:
                st.caption(
                    "Production reuse is blocked until retention and deletion "
                    "procedures are approved."
                )
            latest = service.events.latest_event(identity, session_id, purpose)
            enabled = st.toggle(
                f"Enable {label} reuse",
                value=not disabled and (active if latest is not None else True),
                key=f"reuse_{session_id}_{purpose}",
                disabled=disabled,
            )
            enabled = enabled and not disabled
            if enabled != active:
                service.set_consent(
                    identity,
                    session_id,
                    purpose,
                    enabled,
                    st.session_state,
                    notice_version="v2-default-on",
                )
            st.write(f"**{label}:** {'Enabled for this session' if enabled else 'Off'}")


def _provider_controls(settings: Settings, budget: BudgetLedger) -> str:
    choices = ["ollama"]
    hosted_model = os.getenv(
        "AIRPORT_OPENAI_MODEL_NAME",
        settings.model_name if settings.model_provider in {"openai", "groq"} else "",
    ).strip()
    if settings.openai_api_key and hosted_model:
        choices.append(
            "groq"
            if settings.openai_base_url == "https://api.groq.com/openai/v1"
            or settings.model_provider == "groq"
            else "openai"
        )
    elif settings.development_sign_in:
        st.sidebar.caption(
            "Remote models are available after configuring AIRPORT_OPENAI_API_KEY and "
            "AIRPORT_OPENAI_MODEL_NAME in the server environment or .env. "
            "Paid rates/fee bounds or verified free-plan quotas are still required."
        )
    current = st.session_state.get("selected_model_provider", settings.model_provider)
    if current not in choices:
        current = settings.model_provider if settings.model_provider in choices else "ollama"
    st.session_state["selected_model_provider"] = current
    selected = st.sidebar.radio(
        "Model provider",
        choices,
        index=choices.index(current),
        format_func=lambda provider: PROVIDER_LABELS[provider],
        key="selected_model_provider",
        help=(
            "Provider changes are explicit. Local processing is sent only to the "
            "configured Ollama runtime."
        ),
    )
    if selected == "groq":
        models = ["openai/gpt-oss-20b", "openai/gpt-oss-120b"]
        current_model = st.session_state.get("selected_groq_model", hosted_model)
        if current_model not in models:
            current_model = models[0]
        selected_model = st.sidebar.selectbox(
            "Groq model",
            models,
            index=models.index(current_model),
            key="groq_model_picker",
            help=(
                "Choose explicitly before submitting. Both models require your verified "
                "free-plan configuration; availability and remaining limits are account-specific."
            ),
        )
        st.session_state["selected_groq_model"] = selected_model
        st.sidebar.caption(
            "A rate-limit error does not switch models or retry automatically. "
            "Check the selected model's quota in Groq, then submit explicitly. "
            "Switching models does not reset recorded usage or the shared spending budget."
        )
    st.sidebar.metric("Hosted budget remaining this UTC month", f"${budget.remaining_usd():.2f}")
    if selected != "ollama":
        st.sidebar.caption(
            "Development free-plan quota policy: provider limits only; local monthly "
            "request/token allowances are not enforced. Usage is still recorded and "
            "the shared spending cap remains active."
            if not budget.enforce_free_monthly_quotas
            else "Local monthly hosted request/token allowances remain enforced."
        )
        provider_settings = _client_settings(settings, selected)
        provider = ProviderDescriptor(
            provider_id=selected,
            model_id=provider_settings.model_name,
            product_improvement_terms=settings.hosted_product_improvement_terms,
            hosted=True,
        )
        st.sidebar.warning(
            f"Hosted request notice: your question, submitted free-text clarification answers, "
            f"and minimal active interpretation/schema/catalog context "
            f"will be sent to {PROVIDER_LABELS[selected]} at the configured service "
            f"({provider.model_id}) at "
            f"{settings.openai_base_url or 'https://api.openai.com/v1'}. "
            f"No source rows, database "
            f"access, analyst identifier, or saved report history are sent. "
            f"Product-improvement terms: {provider.product_improvement_terms}."
        )
        st.sidebar.caption(
            "Hosted-processing acknowledgement defaults to on. Turn it off to block submission."
        )
        signature = (provider.provider_id, provider.model_id, provider.product_improvement_terms)
        choices = st.session_state.setdefault("airport_provider_ack_choices", {})
        acknowledged = st.sidebar.toggle(
            "I understand and acknowledge hosted processing",
            value=choices.get(signature, True),
            key=f"ack_provider_{signature}",
        )
        choices[signature] = acknowledged
        if acknowledged:
            mark_disclosed(st.session_state, provider)
            st.sidebar.success("Hosted-provider notice acknowledged for this configuration.")
        else:
            revoke_disclosure(st.session_state, provider)
    return selected


def _select_faq_question(question: str) -> None:
    st.session_state["airport_question"] = question


def _faq_panel(reports: ReportRepository) -> None:
    with st.expander("Shared FAQs"):
        st.caption(
            "These are separately retained, consented shared answers, not your private history. "
            "Their scope and historical data may differ from your current question."
        )
        artifacts = reports.list_shared_artifacts("faq")
        if not artifacts:
            st.info(
                "No shared FAQs yet. Opt into FAQ reuse, generate a new report, "
                "and select Create shared copy to add one."
            )
        for artifact in artifacts:
            st.write(artifact.content["question"])
            st.write(artifact.content["answer"])
            st.table(
                [
                    {"Definition": name, "Value": str(value)}
                    for name, value in artifact.content["definitions"].items()
                ]
            )
            st.table(
                [
                    {"Scope": name, "Value": str(value)}
                    for name, value in artifact.content["scope"].items()
                ]
            )
            st.dataframe(artifact.content["summary_rows"], hide_index=True)
            for index, section in enumerate(artifact.content.get("sections", []), 1):
                st.write(f"Section {index}: {section['label']}")
                if section["status"] == "failed":
                    st.warning(section["failure"])
                    continue
                st.write(section["answer"])
                st.table(
                    [
                        {"Definition": name, "Value": str(value)}
                        for name, value in section["definition"].items()
                    ]
                )
                st.table(
                    [
                        {"Scope": name, "Value": str(value)}
                        for name, value in section["scope"].items()
                    ]
                )
                st.dataframe(section["summary_rows"], hide_index=True)
                st.caption("Shared summaries show at most ten saved evidence rows per section.")
                for limitation in section["limitations"]:
                    st.caption(limitation)
            st.button(
                "Use this FAQ question",
                key=f"faq_{artifact.artifact_id}",
                on_click=_select_faq_question,
                args=(artifact.content["question"],),
            )


def _tracing_disclosure(tracing: TracingConfig) -> bool:
    if not tracing.enabled:
        return True
    st.sidebar.warning(
        "LangSmith tracing is enabled by the deployment operator. Traces may include "
        "your question, analysis-plan context, aggregate results, and generated report text."
    )
    st.sidebar.caption("Tracing acknowledgement defaults to on; turn it off to block submission.")
    acknowledged = st.sidebar.toggle(
        "I understand and acknowledge LangSmith tracing",
        value=st.session_state.get(TRACING_ACK_KEY, True),
        key="ack_langsmith_tracing",
    )
    st.session_state[TRACING_ACK_KEY] = acknowledged
    return acknowledged


def tracing_acknowledged(tracing: TracingConfig, state: Mapping[str, object]) -> bool:
    return not tracing.enabled or state.get(TRACING_ACK_KEY) is True


def _save_exploration_report(
    report: CompositeReportV2,
    identity: AnalystIdentity,
    reports: ReportRepository,
) -> None:
    st.session_state["unsaved_exploration_report"] = report
    if report.completeness == "incomplete" and report.incomplete_acknowledgement is None:
        st.session_state["active_report_id"] = None
        return
    reports.save_report(report, identity)
    st.session_state.pop("unsaved_exploration_report", None)
    st.session_state["active_report_id"] = report.report_id
    st.session_state["reset_history_selection"] = True


def _pending_exploration(
    generator: ExplorationReportGenerator,
    identity: AnalystIdentity,
    reports: ReportRepository,
    session_id: str,
    dispatch_enabled: bool,
) -> None:
    state = st.session_state.get(PENDING_REQUEST_KEY)
    if not isinstance(state, ExplorationRequest) or state.draft.session_binding != session_id:
        return
    if state.draft.state in {"completed", "incomplete", "cancelled", "superseded"}:
        return
    st.subheader("Pending analysis")
    st.write(state.draft.original_question)
    st.caption(
        f"State: {state.draft.state}. Answered clarification turns for this section: "
        f"{state.active_section.answered_turns}/3. A new question replaces this pending analysis."
    )
    if state.proposal is not None:
        with st.expander("Pending interpretation details"):
            st.dataframe(
                [
                    {
                        "Section": section.position,
                        "Question": section.original_clause,
                        "Status": section.status.replace("_", " "),
                        "Measures": ", ".join(
                            measure.replace("_", " ") for measure in section.measure_ids
                        ),
                        "Clarification": (
                            section.clarification.question if section.clarification else ""
                        ),
                    }
                    for section in state.proposal.sections
                ],
                hide_index=True,
                alt="Pending analysis sections; not yet executable",
            )

    def accept(outcome: ExplorationOutcome) -> None:
        if outcome.report is not None:
            _save_exploration_report(outcome.report, identity, reports)
        st.rerun()

    if len(state.draft.sections) > 1:
        remove_id = st.selectbox(
            "Section to remove explicitly",
            [section.section_id for section in state.draft.sections],
            format_func=lambda value: next(
                item.original_clause for item in state.draft.sections if item.section_id == value
            ),
            key=f"remove_section_{state.draft.request_id}_{state.draft.revision}",
        )
        confirm_remove = st.checkbox(
            "I confirm removal of this requested section",
            key=f"confirm_remove_{state.draft.request_id}_{state.draft.revision}_{remove_id}",
        )
        if st.button("Remove selected section", disabled=not confirm_remove):
            try:
                accept(
                    generator.remove_section(
                        section_id=remove_id,
                        analyst_id=identity.analyst_id,
                        session_id=session_id,
                        session_state=st.session_state,
                        request_id=state.draft.request_id,
                        revision=state.draft.revision,
                    )
                )
            except Exception as exc:
                _safe_error(exc)
    if st.button("Cancel analysis", key=f"cancel_{state.draft.request_id}"):
        st.session_state[PENDING_REQUEST_KEY] = stop_request(state, "cancelled")
        st.rerun()
    if st.button("Restart analysis", key=f"restart_{state.draft.request_id}"):
        st.session_state[PENDING_REQUEST_KEY] = stop_request(state, "superseded")
        st.info("Edit the retained Question and select Generate report to start again.")
        return
    if state.proposal and state.proposal.status == "requires_selection":
        st.warning(state.proposal.selection_reason)
        with st.form(f"selected_subset_{state.draft.request_id}_{state.draft.revision}"):
            subset = st.text_area(
                "Selected subset (up to four analyses)",
                max_chars=2000,
            )
            confirmed = st.checkbox(
                "I select only this subset; other questions are excluded "
                "and will not run automatically",
            )
            submit_subset = st.form_submit_button(
                "Analyze the explicitly selected subset",
                disabled=not dispatch_enabled,
            )
        if submit_subset:
            if not confirmed or not subset.strip():
                st.error("Enter the selected questions and confirm the explicit exclusions.")
            else:
                try:
                    accept(
                        generator.generate(
                            subset,
                            analyst_id=identity.analyst_id,
                            session_id=session_id,
                            session_state=st.session_state,
                        )
                    )
                except Exception as exc:
                    _safe_error(exc)
        return
    if state.proposal and state.draft.state in {"failed", "guided_correction"}:
        for index, candidate in enumerate(state.proposal.sections):
            if candidate.operation_id != "distribution":
                continue
            section_id = state.draft.sections[index].section_id
            with st.form(
                f"pending_bin_{state.draft.request_id}_{state.draft.revision}_{section_id}"
            ):
                accepted_width = st.number_input(
                    f"Accepted bin width for section {index + 1}",
                    min_value=0.000001,
                    value=candidate.binning.width
                    if candidate.binning
                    else 250.0
                    if candidate.measure_ids == ["distance"]
                    else 15.0,
                )
                accept_width = st.form_submit_button("Accept bin width and recompute")
            if accept_width:
                try:
                    accept(
                        generator.accept_bin_width(
                            width=float(accepted_width),
                            section_id=section_id,
                            analyst_id=identity.analyst_id,
                            session_id=session_id,
                            session_state=st.session_state,
                        )
                    )
                except Exception as exc:
                    _safe_error(exc)
    if state.draft.state == "failed":
        if state.draft.last_failure is not None:
            st.error(state.draft.last_failure.message)
        st.caption(
            "No automatic retry was made. Retry rechecks disclosure, quota, budget and source "
            "binding. Failed clarification does not consume an answered turn."
        )
        if st.button("Retry interpretation", disabled=not dispatch_enabled):
            if not dispatch_enabled:
                st.error("Acknowledge the provider and tracing notices before retrying.")
                return
            try:
                accept(
                    generator.retry(
                        state,
                        analyst_id=identity.analyst_id,
                        session_id=session_id,
                        session_state=st.session_state,
                    )
                )
            except Exception as exc:
                _safe_error(exc)
            return
    if state.draft.state == "clarification_pending":
        spec = state.active_section.clarification
        if spec is not None:
            st.info(spec.question)
            valid_choices = {}
            for choice in spec.choices:
                try:
                    if state.proposal is None:
                        raise ValueError("No candidate is available.")
                    apply_clarification_choice(
                        state.proposal,
                        state.active_section.position,
                        choice,
                        generator.executor.entity_directory(),
                    )
                    valid_choices[choice.choice_id] = choice.label
                except ValueError:
                    st.warning(
                        "An offered choice could not be validated locally and is not selectable. "
                        "Use free text or guided correction instead."
                    )
            with st.form(f"clarify_{state.question_id}"):
                choices = valid_choices
                selected = (
                    st.selectbox(
                        "Clarification choice",
                        list(choices),
                        format_func=choices.__getitem__,
                    )
                    if choices
                    else None
                )
                text = st.text_area("Clarification answer", max_chars=2000)
                choose = st.form_submit_button("Use selected choice", disabled=not choices)
                submit = st.form_submit_button(
                    "Submit clarification",
                    disabled=not dispatch_enabled,
                )
            if choose or submit:
                if submit and not dispatch_enabled:
                    st.error("Acknowledge the provider and tracing notices before submitting.")
                    return
                event = AnswerEvent(
                    session_binding=session_id,
                    request_id=state.draft.request_id,
                    revision=state.draft.revision,
                    section_id=state.active_section.section_id,
                    question_id=state.question_id,
                    choice_id=selected if choose else None,
                    text=text if submit else None,
                )
                try:
                    accept(
                        generator.answer(
                            state,
                            event,
                            analyst_id=identity.analyst_id,
                            session_id=session_id,
                            session_state=st.session_state,
                        )
                    )
                except ValueError:
                    st.error(
                        "The clarification choice or scope is invalid or stale. "
                        "Review the current question or use guided correction."
                    )
                except Exception as exc:
                    _safe_error(exc)
                    st.rerun()
                return
    if state.draft.state == "guided_correction":
        st.warning(
            "Use structured correction, restart or cancel. No fourth free-text clarification "
            "will be sent. No unresolved section executes."
        )
    if state.draft.state in {"guided_correction", "failed", "clarification_pending"}:
        st.write("Guided summary correction")
        st.caption(
            f"Apply explicitly corrects section {state.active_section.position} to a "
            "scalar/grouped summary. Other requested sections and unshown filters remain."
        )
        candidate = (
            state.proposal.sections[state.active_section.position - 1] if state.proposal else None
        )
        options = sorted(EXPLORATION_OPERATIONS["aggregate"])
        initial_measure = (
            candidate.measure_ids[0]
            if candidate and candidate.measure_ids and candidate.measure_ids[0] in options
            else "flight_count"
        )
        with st.form(f"guided_{state.question_id}"):
            measure = st.selectbox(
                "Corrected measure", options, index=options.index(initial_measure)
            )
            groups = st.multiselect(
                "Corrected grouping",
                sorted(
                    set().union(*(item.dimensions for item in EXPLORATION_MEASURES.values()))
                    - {"weekday"}
                ),
                default=candidate.grouping if candidate else [],
                max_selections=2,
            )
            directory = generator.executor.entity_directory()
            origins = sorted(directory.airports.keys() | directory.observed["origin"])
            origin = st.selectbox(
                "Corrected origin",
                ["Keep current scope", "All observed origins", *origins],
            )
            destination = st.selectbox(
                "Corrected destination",
                [
                    "Keep current scope",
                    "All observed destinations",
                    *sorted(directory.airports.keys() | directory.observed["destination"]),
                ],
            )
            airline = st.selectbox(
                "Corrected airline",
                [
                    "Keep current scope",
                    "All observed airlines",
                    *sorted(directory.airlines.keys() | directory.observed["airline"]),
                ],
            )
            start = st.text_input("Corrected start date (YYYY-MM-DD; empty retains scope)")
            end = st.text_input("Corrected end date (YYYY-MM-DD; empty retains scope)")
            clear_dates = st.checkbox("Remove all date restrictions")
            selection = st.number_input(
                "Corrected output bound",
                min_value=1,
                max_value=500,
                value=candidate.bound if candidate and candidate.bound is not None else 500,
                step=1,
            )
            ordering = st.selectbox(
                "Corrected ordering",
                ["Category order", "Highest measure", "Lowest measure"],
            )
            apply = st.form_submit_button("Apply guided correction")
        if apply:
            try:
                edits = list(candidate.scope_edits) if candidate else []
                mentions = list(candidate.entity_mentions) if candidate else []
                for field, selected, all_label, kinds in [
                    ("origin", origin, "All observed origins", {"origin", "origin_region"}),
                    ("destination", destination, "All observed destinations", {"destination"}),
                    ("carrier", airline, "All observed airlines", {"airline"}),
                ]:
                    if selected == "Keep current scope":
                        continue
                    edits = [edit for edit in edits if edit.field_id != field]
                    mentions = [mention for mention in mentions if mention.kind not in kinds]
                    edits.append(
                        ScopeEdit(
                            field_id=field,
                            action="remove" if selected == all_label else "replace",
                            operator=None if selected == all_label else "eq",
                            value=None if selected == all_label else selected,
                        )
                    )
                scope = (
                    state.proposal.shared_scope.model_copy(deep=True) if state.proposal else None
                )
                if clear_dates:
                    edits = [
                        edit
                        for edit in edits
                        if edit.field_id
                        not in {
                            "flight_date",
                            "flight_year",
                            "flight_month_number",
                        }
                    ]
                    edits.append(
                        ScopeEdit(
                            field_id="flight_date",
                            action="remove",
                            operator=None,
                            value=None,
                        )
                    )
                    if scope is not None:
                        scope.dates = None
                elif start or end:
                    if scope is None:
                        scope = ProposedSharedScope()
                    scope.dates = TimeRange(start=start or None, end=end or None)
                order = (
                    ExplorationOrder(
                        field_id=measure,
                        direction="desc" if ordering == "Highest measure" else "asc",
                    )
                    if ordering != "Category order"
                    else None
                )
                section = SectionProposal(
                    position=1,
                    original_clause=state.draft.original_question,
                    status="proposed",
                    family="grouped_summary" if groups else "overall_summary",
                    operation_id="aggregate",
                    measure_ids=[measure],
                    population="flights",
                    scope_edits=edits,
                    entity_mentions=mentions,
                    grouping=groups,
                    comparison=None,
                    binning=None,
                    pairing=None,
                    order=order,
                    bound=int(selection),
                    rounding=candidate.rounding if candidate else None,
                    clarification=None,
                    unsupported_reason=None,
                )
                proposal = IntentProposalV2(
                    intent_version=2,
                    status="proposed",
                    shared_scope=scope or {},
                    sections=[section],
                    selection_reason=None,
                )
                accept(
                    generator.correct_pending(
                        state,
                        proposal,
                        analyst_id=identity.analyst_id,
                        session_id=session_id,
                        session_state=st.session_state,
                    )
                )
            except ValueError:
                st.error(
                    "The selected measure, grouping or scope is incompatible. "
                    "Correct the selections; no analytical query was run."
                )
            except Exception as exc:
                _safe_error(exc)


def _summary_editor(
    report: CompositeReportV2,
    identity: AnalystIdentity,
    reports: ReportRepository,
    session_id: str,
    generator: ExplorationReportGenerator,
) -> None:
    interpretation = report.sections[0].interpretation
    st.subheader("Logical interpretation")
    st.table(
        [
            {"Item": label, "Value": str(value)}
            for label, value in {
                "Measure": ", ".join(
                    measure.replace("_", " ") for measure in interpretation.measure_ids
                )
                or (
                    "Distinct neighbouring airports (arrivals and departures)"
                    if interpretation.population == "airport_connections"
                    else "Listing"
                ),
                "Population": interpretation.population.replace("_", " "),
                "Groups": ", ".join(interpretation.grouping) or "all combined",
                "Requested dates": (
                    f"{interpretation.date_scope.start or 'First recorded date'} to "
                    f"{interpretation.date_scope.end or 'Last recorded date'}"
                    if interpretation.date_scope
                    else "all recorded dates"
                ),
                "Filters": "; ".join(
                    f"{item.field_id.replace('_', ' ')} {item.operator} "
                    + (
                        ", ".join(str(value) for value in item.value)
                        if isinstance(item.value, list)
                        else str(item.value)
                    )
                    for item in interpretation.filters
                )
                or "None",
                "Ordering": "; ".join(
                    f"{item.field_id.replace('_', ' ')} {item.direction}"
                    for item in interpretation.order
                )
                or "Stable identity order",
                "Output bound": interpretation.selection,
                "Denominator": interpretation.denominator_basis,
            }.items()
        ]
    )
    st.caption(
        "Field sources: "
        + ", ".join(
            f"{field}: {value.source}" for field, value in interpretation.field_provenance.items()
        )
    )
    edit_key = f"editing_interpretation_{report.report_id}"
    if st.button("Edit interpretation", key=f"edit_{report.report_id}"):
        st.session_state[edit_key] = True
    if not st.session_state.get(edit_key):
        return
    st.caption(
        "Edits do not change saved evidence until Apply. Apply computes a new revision locally; "
        "Cancel keeps the original report. Unchanged controls and unshown filters retain their "
        "restrictions. Changing inclusion codes replaces that field's restrictions; "
        "use Remove restrictions to explicitly clear them. Date bounds intersect retained filters."
    )
    directory = generator.executor.entity_directory()
    with st.form(f"interpretation_form_{report.report_id}"):
        measure = st.selectbox(
            "Measure",
            sorted(EXPLORATION_OPERATIONS["aggregate"]),
            index=sorted(EXPLORATION_OPERATIONS["aggregate"]).index(interpretation.measure_ids[0]),
            format_func=lambda key: key.replace("_", " "),
        )
        group_options = sorted(
            set().union(*(definition.dimensions for definition in EXPLORATION_MEASURES.values()))
            - {"weekday"}
        )
        grouping = st.multiselect(
            "Group by",
            group_options,
            default=interpretation.grouping,
            max_selections=2,
            format_func=lambda key: key.replace("_", " "),
            help=(
                "Airport groups by any airport that appears as an origin or destination "
                "(FAA code). It applies to distinct connected airport count and flight count."
            ),
        )
        origins = sorted(directory.airports.keys() | directory.observed["origin"])
        carriers = sorted(directory.airlines.keys() | directory.observed["airline"])
        origin_value = next(
            (
                item.value
                for item in interpretation.filters
                if item.field_id == "origin" and item.operator in {"eq", "in"}
            ),
            None,
        )
        carrier_value = next(
            (
                item.value
                for item in interpretation.filters
                if item.field_id == "carrier" and item.operator in {"eq", "in"}
            ),
            None,
        )
        initial_codes = {
            field: value if isinstance(value, list) else [value] if value else []
            for field, value in [("origin", origin_value), ("carrier", carrier_value)]
        }
        selected_origins = st.multiselect(
            "Origin inclusion codes",
            origins,
            default=initial_codes["origin"],
        )
        remove_origin = st.checkbox("Remove origin restrictions")
        selected_carriers = st.multiselect(
            "Airline inclusion codes",
            carriers,
            default=initial_codes["carrier"],
        )
        remove_carrier = st.checkbox("Remove airline restrictions")
        start = st.text_input(
            "Additional inclusive start date (YYYY-MM-DD; empty means no lower range bound)",
            value=str(interpretation.date_scope.start or "") if interpretation.date_scope else "",
        )
        end = st.text_input(
            "Additional inclusive end date (YYYY-MM-DD; empty means no upper range bound)",
            value=str(interpretation.date_scope.end or "") if interpretation.date_scope else "",
        )
        selection = st.number_input(
            "Maximum output groups",
            min_value=1,
            max_value=500,
            value=interpretation.selection,
            step=1,
        )
        order_options = ["category order", "highest measure first", "lowest measure first"]
        initial_order = (
            1
            if interpretation.order
            and interpretation.order[0].field_id in interpretation.measure_ids
            and interpretation.order[0].direction == "desc"
            else 2
            if interpretation.order
            and interpretation.order[0].field_id in interpretation.measure_ids
            else 0
        )
        order = st.selectbox("Order", order_options, index=initial_order)
        apply = st.form_submit_button("Apply interpretation")
        cancel = st.form_submit_button("Cancel edits")
    if cancel:
        st.session_state[edit_key] = False
        st.rerun()
    if apply:
        try:
            edits = [
                ScopeEdit(
                    field_id=field,
                    action="replace" if codes and not remove else "remove",
                    operator="in" if codes and not remove else None,
                    value=codes if codes and not remove else None,
                )
                for field, codes, remove in [
                    ("origin", selected_origins, remove_origin),
                    ("carrier", selected_carriers, remove_carrier),
                ]
                if remove or set(codes) != set(initial_codes[field])
            ]
            date_scope = TimeRange(start=start or None, end=end or None) if start or end else None
            typed_order = (
                ExplorationOrder(
                    field_id=measure,
                    direction="desc" if order == order_options[1] else "asc",
                )
                if order != order_options[0]
                else ExplorationOrder(field_id=grouping[0], direction="asc")
                if grouping
                else None
            )
            draft, corrected = correct_summary(
                interpretation,
                question=report.question,
                session_binding=session_id,
                directory=directory,
                measure=measure,
                grouping=grouping,
                edits=edits,
                date_scope=date_scope,
                selection=int(selection),
                order=typed_order,
            )
        except ValueError:
            st.error(
                "The selected measure, groups, dates or scope are incompatible. No query was run."
            )
            return
        generated = generator.execute_interpretations(
            draft.model_copy(
                update={
                    "shared_scope": report.shared_scope,
                    "removed_sections": report.removed_sections,
                }
            ),
            [corrected],
            analyst_id=identity.analyst_id,
            session_id=session_id,
            parent_report_id=report.report_id,
        )
        if generated.report is not None:
            _save_exploration_report(generated.report, identity, reports)
            st.session_state[edit_key] = False
            st.rerun()


def _listing_controls(
    report: CompositeReportV2,
    identity: AnalystIdentity,
    session_id: str,
    executor: DuckDBExecutor,
    section_index: int = 0,
) -> None:
    section = report.sections[section_index]
    evidence = section_evidence(section)
    if not isinstance(evidence, ListingResult):
        return
    interpretation = section.interpretation
    prefix = (
        f"listing_{identity.analyst_id}_{session_id}_{report.report_id}_"
        f"{report.revision}_{section.section_id}"
    )
    st.subheader("Browse the matching population")
    st.caption(
        f"Population: {evidence.population.replace('_', ' ')}; exact total "
        f"{evidence.total_rows:,}. Paging and CSV preparation are local; no model call."
    )
    try:
        executor.require_current_binding(report.snapshot_id, report.context_id)
    except DatasetUnavailableError as exc:
        st.warning(user_safe_message(exc))
        st.info(
            "Saved preview remains available. Historical continuation and full listing export "
            "are disabled. Restart explicitly to analyze the currently available source."
        )
        st.button(
            "Restart listing on current source",
            key=f"{prefix}_restart",
            on_click=_select_faq_question,
            args=(report.question,),
            help="Copies this question to the form. Review it and select Generate report.",
        )
        return
    previous = st.session_state.get(f"{prefix}_page")
    if not isinstance(previous, BrowsePage):
        previous = (
            evidence.browse_page
            if evidence.browse_page is not None and evidence.browse_page.session_id == session_id
            else None
        )
    columns = listing_columns(interpretation)
    default_sort = previous.sort_field if previous else columns[0]
    with st.form(f"{prefix}_browse"):
        size = st.selectbox("Rows per page", [25, 50, 100, 500], index=2)
        sort = st.selectbox("Listing sort column", columns, index=columns.index(default_sort))
        direction = st.selectbox(
            "Listing sort direction",
            ["asc", "desc"],
            index=1 if previous and previous.direction == "desc" else 0,
        )
        index = st.number_input("Page number", min_value=1, value=1, step=1)
        load = st.form_submit_button("Load listing page")
    if load:
        try:
            page = executor.browse(
                interpretation,
                analyst_id=identity.analyst_id,
                session_id=session_id,
                page_size=size,
                page_index=index,
                sort_field=sort,
                direction=direction,
                previous=previous,
            )
            st.session_state[f"{prefix}_page"] = page
            previous = page
            st.session_state.pop(f"{prefix}_csv", None)
        except Exception as exc:
            st.session_state.pop(f"{prefix}_csv", None)
            _safe_error(exc)
    if previous is not None:
        if previous.notice:
            st.info(previous.notice)
        st.caption(
            f"Page {previous.page_index if previous.total_pages else 0} "
            f"of {previous.total_pages}; {len(previous.rows):,} visible of "
            f"{previous.total_rows:,} total; ordered by {previous.sort_field} "
            f"{previous.direction}, with stable identity tie-breaks."
        )
        st.dataframe(previous.rows, hide_index=True, alt="Current bounded listing page")

    st.subheader("Prepare a bounded listing CSV")
    st.caption(
        "Separate from the saved-preview download. Exports start at row one in the saved "
        "report order, not the current browsing page. Maximum 10,000 records. "
        "Null fields are listed in _meta_null_fields; risky spreadsheet text is reversibly escaped."
    )
    maximum = min(10000, evidence.total_rows)
    if maximum:
        allocation = int(
            st.number_input(
                "Listing export rows",
                min_value=0,
                max_value=maximum,
                value=maximum,
                step=1,
                key=f"{prefix}_allocation",
            )
        )
    else:
        allocation = 0
    page_binding = (
        f"{previous.order_hash}_{previous.scope_hash}_{previous.page_size}" if previous else "saved"
    )
    selection = listing_export_selection(
        report,
        analyst_id=identity.analyst_id,
        session_id=session_id,
        allocation=allocation,
        section_id=section.section_id,
    )
    confirmed = (
        st.checkbox(
            f"I confirm a partial listing export ({allocation:,} of {evidence.total_rows:,} rows)",
            key=f"{prefix}_confirm_{selection.confirmation_hash()}_{page_binding}",
        )
        if allocation < evidence.total_rows
        else True
    )
    if st.button("Prepare listing CSV", key=f"{prefix}_prepare", disabled=not confirmed):
        st.session_state.pop(f"{prefix}_csv", None)
        try:
            data = export_listing_csv(
                report,
                executor,
                selection.confirm() if confirmed else selection,
                analyst_id=identity.analyst_id,
                session_id=session_id,
            )
            st.session_state[f"{prefix}_csv"] = (
                selection.confirmation_hash(),
                page_binding,
                data,
            )
        except Exception as exc:
            _safe_error(exc)
    ready = st.session_state.get(f"{prefix}_csv")
    if (
        confirmed
        and isinstance(ready, tuple)
        and ready[:2]
        == (
            selection.confirmation_hash(),
            page_binding,
        )
    ):
        st.download_button(
            f"Download listing CSV ({allocation:,} of {evidence.total_rows:,} rows)",
            data=ready[2],
            file_name=f"airport-listing-{report.report_id}.csv",
            mime="text/csv",
            key=f"{prefix}_download",
        )


def _analytical_editor(report, identity, reports, session_id, generator, section_index=0):
    section = report.sections[section_index]
    interpretation = section.interpretation
    operation = interpretation.operation_id
    if operation not in {
        "daily_distinct_mean",
        "daily_capacity_mean",
        "distribution",
        "period_change",
    }:
        return
    with st.expander("Edit analytical definition"):
        st.caption(
            "Apply creates a new analytical revision locally. The saved report is unchanged."
        )
        with st.form(f"analytical_{report.report_id}_{section.section_id}"):
            basis = interpretation.denominator_basis
            width = None
            baseline_start = baseline_end = comparison_start = comparison_end = None
            if operation in {"daily_distinct_mean", "daily_capacity_mean"}:
                basis = st.selectbox(
                    "Daily denominator basis",
                    ["verified_calendar_days", "observed_operating_days"],
                    index=1 if basis == "observed_operating_days" else 0,
                    help="Observed activity is not verified complete-day availability.",
                )
            elif operation == "distribution":
                width = st.number_input(
                    "Accepted bin width",
                    min_value=0.000001,
                    value=float(interpretation.binning.width),
                    format="%f",
                )
            elif interpretation.comparison:
                from airport_analytics.analytics.multi_stage import comparison_periods

                baseline_period, _, _ = comparison_periods(interpretation.comparison)
                baseline_start = st.date_input("Baseline start", baseline_period.start)
                baseline_end = st.date_input("Baseline end", baseline_period.end)
                comparison_start = st.date_input(
                    "Comparison start", interpretation.comparison.comparison.start
                )
                comparison_end = st.date_input(
                    "Comparison end", interpretation.comparison.comparison.end
                )
            apply = st.form_submit_button("Apply analytical definition")
            cancel = st.form_submit_button("Cancel analytical edits")
        if cancel:
            st.info("Edits cancelled; saved evidence is unchanged.")
        if apply:
            try:
                payload = interpretation.model_dump()
                payload["revision"] += 1
                payload["denominator_basis"] = basis
                payload["field_provenance"] = interpretation.field_provenance | {
                    "denominator_basis": FieldProvenance(
                        source="correction",
                        revision=payload["revision"],
                    ),
                }
                if width is not None:
                    payload["binning"] = {"width": float(width), "accepted": True}
                if baseline_start is not None:
                    payload["comparison"] = {
                        "baseline": {"start": baseline_start, "end": baseline_end},
                        "comparison": {"start": comparison_start, "end": comparison_end},
                    }
                revised = type(interpretation).model_validate(payload)
                draft = RequestDraft(
                    request_id=revised.request_id,
                    revision=revised.revision,
                    original_question=report.question,
                    session_binding=session_id,
                    shared_scope=report.shared_scope,
                    removed_sections=report.removed_sections,
                )
                interpretations = [
                    revised
                    if index == section_index
                    else item.interpretation.model_copy(
                        update={"revision": revised.revision},
                    )
                    for index, item in enumerate(report.sections)
                ]
                outcome = generator.execute_interpretations(
                    draft,
                    interpretations,
                    analyst_id=identity.analyst_id,
                    session_id=session_id,
                    parent_report_id=report.report_id,
                )
                _save_exploration_report(outcome.report, identity, reports)
                st.rerun()
            except Exception as exc:
                _safe_error(exc)


def _bundle_controls(report, identity, session_id, executor):
    listings = [
        (section, section_evidence(section))
        for section in report.sections
        if isinstance(section_evidence(section), ListingResult)
    ]
    if not listings:
        return
    try:
        executor.require_current_binding(report.snapshot_id, report.context_id)
    except DatasetUnavailableError:
        st.info(
            "Historical listing expansion is unavailable; saved-preview bundles remain readable."
        )
        return
    st.subheader("Prepare listing allocations for a CSV bundle")
    allocations = {}
    prefix = f"bundle_{identity.analyst_id}_{session_id}_{report.report_id}_{report.revision}"
    for section, evidence in listings:
        allocations[section.section_id] = int(
            st.number_input(
                f"Bundle rows for section {section.position}",
                min_value=0,
                max_value=min(10000, evidence.total_rows),
                value=min(evidence.total_rows, 10000 // len(listings)),
                step=1,
                key=f"{prefix}_{section.section_id}_allocation",
            )
        )
    if sum(allocations.values()) > 10000:
        st.error(
            "Combined listing allocations exceed 10,000 rows. Reduce the selected allocations."
        )
        return
    selection = bundle_export_selection(
        report,
        analyst_id=identity.analyst_id,
        session_id=session_id,
        allocations=allocations,
    )
    partial = any(
        allocations[section.section_id] < evidence.total_rows for section, evidence in listings
    )
    confirmed = (
        st.checkbox(
            "I confirm all partial listing populations in this bundle",
            key=f"{prefix}_{selection.confirmation_hash()}_confirm",
        )
        if partial
        else True
    )
    if st.button("Prepare allocated CSV bundle", key=f"{prefix}_prepare", disabled=not confirmed):
        st.session_state.pop(f"{prefix}_ready", None)
        try:
            data = export_report_bundle(
                report,
                analyst_id=identity.analyst_id,
                session_id=session_id,
                executor=executor,
                selection=selection.confirm(),
            )
            st.session_state[f"{prefix}_ready"] = (selection.confirmation_hash(), data)
        except Exception as exc:
            _safe_error(exc)
    ready = st.session_state.get(f"{prefix}_ready")
    if confirmed and isinstance(ready, tuple) and ready[0] == selection.confirmation_hash():
        st.download_button(
            "Download allocated CSV bundle (ZIP)",
            data=ready[1],
            file_name=f"airport-allocated-{report.report_id}.zip",
            mime="application/zip",
            key=f"{prefix}_download",
        )


def _presentation_preferences(report, identity, reports):
    unsaved = st.session_state.get("unsaved_exploration_report")
    if isinstance(unsaved, CompositeReportV2) and unsaved.report_id == report.report_id:
        return
    with st.expander("Section presentation preferences (table-only)"):
        section_id = st.selectbox(
            "Section presentation target",
            [section.section_id for section in report.sections],
            format_func=lambda value: next(
                section.label for section in report.sections if section.section_id == value
            ),
            key=f"preference_target_{report.report_id}",
        )
        current = report.presentation_preferences.get(section_id, SectionPresentationPreference())
        with st.form(f"preferences_{report.report_id}_{report.preference_version}_{section_id}"):
            family = st.selectbox(
                "Presentation",
                ["default", "table"],
                index=int(current.chart_family == "table"),
            )
            apply = st.form_submit_button("Save section presentation preference")
        if apply:
            try:
                reports.update_preferences(
                    identity,
                    report.report_id,
                    expected_version=report.preference_version,
                    preferences=report.presentation_preferences
                    | {
                        section_id: SectionPresentationPreference(chart_family=family),
                    },
                )
                st.rerun()
            except Exception as exc:
                _safe_error(exc)
        if st.button(
            "Refresh presentation preferences", key=f"refresh_preferences_{report.report_id}"
        ):
            st.rerun()
        st.caption("Presentation changes never edit evidence. Charts await specification 003.")


def _composite_scope_editor(report, identity, reports, session_id, generator):
    with st.expander("Refine the scope of selected or all sections"):
        st.caption(
            "This local correction makes a new analytical revision on the same snapshot. "
            "Unselected sections retain their meaning; every section is recalculated before saving."
        )
        directory = generator.executor.entity_directory()
        with st.form(f"composite_scope_{report.report_id}_{report.revision}"):
            target = st.selectbox(
                "Scope refinement target",
                ["all", *[section.section_id for section in report.sections]],
                format_func=lambda value: (
                    "All sections"
                    if value == "all"
                    else next(
                        section.label for section in report.sections if section.section_id == value
                    )
                ),
            )
            origin = st.selectbox(
                "Scope refinement origin",
                ["Keep", "All", *sorted(directory.observed["origin"])],
            )
            airline = st.selectbox(
                "Scope refinement airline",
                ["Keep", "All", *sorted(directory.observed["airline"])],
            )
            dates = st.selectbox("Scope refinement dates", ["Keep", "Clear", "Set"])
            start = st.text_input("Scope refinement start (YYYY-MM-DD)")
            end = st.text_input("Scope refinement end (YYYY-MM-DD)")
            apply = st.form_submit_button("Apply explicit section scope refinement")
        if apply:
            try:
                if dates == "Set" and not (start or end):
                    raise ValueError("Enter at least one date boundary before choosing Set.")
                edits = [
                    ScopeEdit(
                        field_id=field,
                        action="remove" if value == "All" else "replace",
                        operator=None if value == "All" else "eq",
                        value=None if value == "All" else value,
                    )
                    for field, value in [("origin", origin), ("carrier", airline)]
                    if value != "Keep"
                ]
                if not edits and dates == "Keep":
                    st.error("Choose a scope change before applying this correction.")
                    return
                outcome = generator.refine_scope(
                    report,
                    section_ids={section.section_id for section in report.sections}
                    if target == "all"
                    else {target},
                    edits=edits,
                    replace_dates=dates != "Keep",
                    date_scope=TimeRange(start=start or None, end=end or None)
                    if dates == "Set"
                    else None,
                    analyst_id=identity.analyst_id,
                    session_id=session_id,
                )
                _save_exploration_report(outcome.report, identity, reports)
                st.rerun()
            except Exception as exc:
                _safe_error(exc)


@timed_stage("server_preparation")
def _render_report(
    identity: AnalystIdentity,
    report_id: str,
    reports: ReportRepository,
    consent: ConsentService,
    session_id: str,
    exploration_generator: ExplorationReportGenerator | None = None,
    executor: DuckDBExecutor | None = None,
    visual_reporting_enabled: bool = False,
) -> None:
    report = reports.get_report(identity, report_id)
    st.session_state["active_report_id"] = report.report_id
    render_report(
        report,
        st,
        visual_reporting_enabled=visual_reporting_enabled,
    )
    if isinstance(report, CompositeReportV2):
        _presentation_preferences(report, identity, reports)
    summary_v2 = (
        isinstance(report, CompositeReportV2)
        and len(report.sections) == 1
        and isinstance(section_evidence(report.sections[0]), (ScalarResult, GroupedResult))
    )
    if (
        summary_v2
        and report.sections[0].interpretation.operation_id == "aggregate"
        and exploration_generator is not None
    ):
        _summary_editor(report, identity, reports, session_id, exploration_generator)
    listing_v2 = (
        isinstance(report, CompositeReportV2)
        and len(report.sections) == 1
        and isinstance(section_evidence(report.sections[0]), ListingResult)
    )
    if listing_v2 and executor is not None:
        _listing_controls(report, identity, session_id, executor)
    if isinstance(report, CompositeReportV2) and len(report.sections) > 1:
        if exploration_generator is not None:
            _composite_scope_editor(report, identity, reports, session_id, exploration_generator)
        if executor is not None:
            for index, section in enumerate(report.sections):
                if isinstance(section_evidence(section), ListingResult):
                    with st.expander(f"Browse section {index + 1}: {section.label}"):
                        _listing_controls(report, identity, session_id, executor, index)
        if exploration_generator is not None:
            target = st.selectbox(
                "Analytical section to edit",
                list(range(len(report.sections))),
                format_func=lambda index: f"{index + 1}. {report.sections[index].label}",
                key=f"analytical_target_{report.report_id}",
            )
            _analytical_editor(report, identity, reports, session_id, exploration_generator, target)
    if (
        isinstance(report, CompositeReportV2)
        and len(report.sections) == 1
        and exploration_generator is not None
    ):
        _analytical_editor(report, identity, reports, session_id, exploration_generator)
    col_csv, col_pdf, col_delete = st.columns(3)
    exportable_v2 = (
        isinstance(report, CompositeReportV2)
        and len(report.sections) == 1
        and section_evidence(report.sections[0]) is not None
    )
    if isinstance(report, ReportContent) or exportable_v2:
        csv_data = export_report_csv(report)
        try:
            pdf_data = export_report_pdf(report)
        except PdfRuntimeUnavailableError as exc:
            pdf_data = None
            pdf_unavailable = exc.user_message
        col_csv.download_button(
            "Download saved preview (CSV)" if listing_v2 else "Download result table (CSV)",
            data=csv_data,
            file_name=f"airport-report-{report.report_id}.csv",
            mime="text/csv",
            key=f"csv_{report.report_id}",
        )
        col_pdf.download_button(
            "Download report with saved preview (PDF)"
            if listing_v2
            else "Download complete report (PDF)",
            data=pdf_data or b"",
            file_name=f"airport-report-{report.report_id}.pdf",
            mime="application/pdf",
            key=f"pdf_{report.report_id}",
            disabled=pdf_data is None,
        )
        if pdf_data is None:
            col_pdf.caption(pdf_unavailable)
        if exportable_v2:
            evidence = section_evidence(report.sections[0])
            if evidence.daily_support or evidence.kind == "weather_panel":
                st.download_button(
                    "Download supporting evidence CSV bundle (ZIP)",
                    data=export_report_bundle(
                        report,
                        analyst_id=identity.analyst_id,
                        session_id=session_id,
                    ),
                    file_name=f"airport-evidence-{report.report_id}.zip",
                    mime="application/zip",
                    key=f"support_bundle_{report.report_id}",
                )
        if (isinstance(report, ReportContent) and report.result_payload.get("routes")) or (
            isinstance(report, CompositeReportV2)
            and summary_v2
            and report.sections[0].interpretation.measure_ids == ["distinct_destination_count"]
        ):
            st.download_button(
                "Download supporting routes (CSV)",
                data=export_report_csv(report, supporting_routes=True),
                file_name=f"airport-routes-{report.report_id}.csv",
                mime="text/csv",
                key=f"routes_{report.report_id}",
            )
    elif isinstance(report, CompositeReportV2):
        if executor is not None:
            _bundle_controls(report, identity, session_id, executor)
        bundle = export_report_bundle(
            report,
            analyst_id=identity.analyst_id,
            session_id=session_id,
        )
        col_csv.download_button(
            "Download saved-evidence CSV bundle (ZIP)",
            data=bundle,
            file_name=f"airport-report-{report.report_id}.zip",
            mime="application/zip",
            key=f"bundle_{report.report_id}",
        )
        try:
            composite_pdf = export_report_pdf(report)
        except PdfRuntimeUnavailableError as exc:
            composite_pdf = None
            col_pdf.caption(exc.user_message)
        col_pdf.download_button(
            "Download complete report (PDF)",
            data=composite_pdf or b"",
            file_name=f"airport-report-{report.report_id}.pdf",
            mime="application/pdf",
            key=f"pdf_{report.report_id}",
            disabled=composite_pdf is None,
        )
        st.caption(
            "Contains every requested section/status. Listing files contain saved previews only. "
            "The PDF includes every section, failed sections with their failure reason."
        )
    else:
        st.info(
            "Saved V2 evidence is readable. V2 analysis, exports and sharing remain "
            "disabled until their section-aware workflows are integrated."
        )
    if col_delete.button("Delete private report", key=f"delete_{report.report_id}"):
        reports.delete_report(identity, report.report_id)
        st.session_state["active_report_id"] = None
        st.session_state["reset_history_selection"] = True
        st.rerun()

    if isinstance(report, CompositeReportV2) and not any(
        section_evidence(section) is not None
        and section_evidence(section).kind not in {"listing", "relationship"}
        for section in report.sections
    ):
        return
    active_purposes = [
        purpose
        for purpose in PURPOSE_LABELS
        if consent.is_active(identity, session_id, purpose, st.session_state)
    ]
    if not active_purposes:
        return
    with st.expander("Share this report under active reuse consent"):
        st.caption(
            "This creates a separately retained, identity-free shared copy. "
            "Withdrawing consent later does not delete it."
        )
        purpose = st.selectbox(
            "Reuse purpose",
            active_purposes,
            format_func=lambda item: PURPOSE_LABELS[item],
            key=f"share_purpose_{report.report_id}",
        )
        if st.button("Create shared copy", key=f"share_{report.report_id}"):
            artifact = consent.create_shared_artifact(
                identity,
                report,
                purpose,
                st.session_state,
            )
            st.success(f"Shared copy created ({artifact.artifact_id[:8]}).")


def main() -> None:
    st.set_page_config(page_title="Airport Data Platform", layout="wide")
    st.title("Interactive Airport Data Platform")
    try:
        settings = Settings.from_env()
        if settings.development_sign_in:
            server_address = st.get_option("server.address")
            if settings.production or server_address not in {"localhost", "127.0.0.1", "::1"}:
                st.error(
                    "Development sign-in requires AIRPORT_PRODUCTION=false and "
                    "--server.address=127.0.0.1. Stop the app and correct its configuration."
                )
                return
            st.warning(
                "Development sign-in is enabled. This is not real authentication. "
                "All development sessions share one identity and its report history. "
                "Use only on your trusted local machine; never expose or proxy this server."
            )
            identity = (
                resolve_development_identity(
                    production=settings.production, server_address=server_address
                )
                if st.session_state.get(DEV_SIGN_IN_KEY) is True
                else None
            )
            if identity is None:
                if st.button("Sign in as local developer"):
                    st.session_state[DEV_SIGN_IN_KEY] = True
                    st.rerun()
                return
        else:
            identity = _identity()
        if identity is None:
            if getattr(st.user, "is_logged_in", False):
                st.error("The OIDC identity did not contain stable issuer and subject claims.")
                return
            st.info("Sign in with your organization account to access private analytics.")
            if st.button("Sign in"):
                st.login()
            return

        st.sidebar.caption(
            "Signed in as local developer (development bypass)."
            if settings.development_sign_in
            else "Signed in with a pseudonymous, issuer/subject-derived analyst key."
        )
        if st.sidebar.button("Sign out"):
            if settings.development_sign_in:
                st.session_state.clear()
                st.rerun()
            else:
                st.session_state.clear()
                st.logout()
            return
        session_id = st.session_state.setdefault("airport_session_id", uuid.uuid4().hex)
        storage = _storage(str(settings.database_path))
        reports = ReportRepository(storage)
        consent_repository = ConsentRepository(storage)
        consent = ConsentService(
            reports,
            consent_repository,
            shared_reuse_enabled=settings.shared_reuse_enabled,
            production=settings.production,
            retention_policy_approved=settings.retention_policy_approved,
        )
        budget = BudgetLedger(
            storage,
            monthly_cap_usd=settings.deployment_monthly_budget_usd,
            free_monthly_request_limit=settings.free_monthly_request_limit,
            free_monthly_token_limit=settings.free_monthly_token_limit,
            enforce_free_monthly_quotas=not (not settings.production and settings.hosted_free_plan),
        )
        _consent_panel(identity, session_id, consent)
        _faq_panel(reports)
        selected_provider = _provider_controls(settings, budget)

        history = reports.list_reports(identity)
        labels = {
            report.report_id: (
                f"{report.created_at.isoformat()[:16]} — {report.question[:100]}"
                if isinstance(report, CompositeReportV2)
                else f"{report.created_at[:16]} — {report.question[:100]}"
            )
            for report in history
        }
        history_options = [NO_REPORT, *labels]
        if st.session_state.pop("reset_history_selection", False):
            st.session_state["selected_history_report"] = NO_REPORT
        if st.session_state.get("selected_history_report") not in history_options:
            st.session_state["selected_history_report"] = NO_REPORT

        st.subheader("Private report history")
        selected_history = st.selectbox(
            "Open one of your saved reports",
            history_options,
            format_func=lambda report_id: (
                report_id if report_id == NO_REPORT else _report_label(report_id, labels)
            ),
            key="selected_history_report",
        )
        current_report_id = (
            selected_history
            if selected_history != NO_REPORT
            else st.session_state.get("active_report_id")
        )
        current_report = (
            reports.get_report(identity, current_report_id) if current_report_id in labels else None
        )

        try:
            executor = _executor(str(settings.source_data_dir), settings.query_timeout_seconds)
        except DatasetUnavailableError as exc:
            _safe_error(exc)
            st.info(
                "Current source data is unavailable. Saved evidence and preview downloads remain "
                "readable; new analysis, paging and full listing exports are disabled."
            )
            if current_report_id in labels:
                _render_report(
                    identity,
                    current_report_id,
                    reports,
                    consent,
                    session_id,
                    visual_reporting_enabled=settings.visual_reporting_enabled,
                )
            return
        if settings.coverage_path and executor.coverage.warning:
            st.warning(executor.coverage.warning)
        if settings.weather_units_path:
            unit_warning = dict(executor.context.unit_provenance).get("weather_warning")
            if unit_warning:
                st.warning(unit_warning)
        tracing = TracingConfig.from_env()
        model_settings = _client_settings(settings, selected_provider)
        exploration_enabled = st.toggle(
            "Use V2 summary exploration",
            value=True,
            help=(
                "Ordinary-language summaries, entity lists and individual flight records. "
                "Daily metrics, periods, distributions, relationships and up to four sections. "
                "Daily completeness and transformed weather units require local evidence. "
                "Enabled by default. Turn off to use the existing V1 workflow."
            ),
            key="exploration_preview",
        )
        client = LangChainPlanClient(
            model_settings,
            budget=budget,
            tracing=tracing,
            **({"contract_version": 2} if exploration_enabled else {}),
        )
        tracing_acknowledged = _tracing_disclosure(tracing)
        generator = (
            ExplorationReportGenerator(client, executor)
            if exploration_enabled
            else ReportGenerator(client, executor)
        )

        st.header("Ask an airport-data question")
        if selected_provider != "ollama":
            current_provider = client.provider
            provider_acknowledged = has_disclosed(st.session_state, current_provider)
            if not provider_acknowledged:
                st.warning("Acknowledge the hosted-provider notice before asking a question.")
        else:
            provider_acknowledged = True
            st.caption(
                f"Local model: {model_settings.model_name} at {model_settings.ollama_base_url}. "
                "The question is processed by that configured local runtime."
            )

        if current_report is None:
            st.caption(
                "Refinement becomes available after generating a successful report "
                "or opening one from private history."
            )
        else:
            st.caption(f"Refinement target: {current_report.question}")
        with st.form("question_form", clear_on_submit=False):
            question = st.text_area(
                "Question",
                key="airport_question",
                max_chars=2000,
                help=(
                    "Ask about connectivity, delays, airlines, or aircraft in the "
                    "supplied historical snapshot."
                ),
            )
            refine = st.checkbox(
                "Refine the currently displayed report's scope",
                disabled=not (
                    isinstance(current_report, CompositeReportV2)
                    and exploration_enabled
                    and len(current_report.sections) == 1
                    or isinstance(current_report, ReportContent)
                    and not exploration_enabled
                ),
                help="Check this, enter a follow-up in Question, then select Generate report.",
            )
            submitted = st.form_submit_button(
                "Generate report",
                disabled=not (provider_acknowledged and tracing_acknowledged),
                type="primary",
            )
        if submitted:
            pending = st.session_state.get(PENDING_REQUEST_KEY)
            if isinstance(pending, ExplorationRequest):
                st.session_state[PENDING_REQUEST_KEY] = stop_request(pending, "superseded")
            st.session_state["active_report_id"] = None
            st.session_state["reset_history_selection"] = True
            try:
                if isinstance(generator, ExplorationReportGenerator):
                    context = (
                        current_report.sections[0].interpretation
                        if refine and isinstance(current_report, CompositeReportV2)
                        else None
                    )
                    outcome = generator.generate(
                        question,
                        analyst_id=identity.analyst_id,
                        session_id=session_id,
                        session_state=st.session_state,
                        follow_up_context=context,
                    )
                else:
                    context = (
                        FollowUpContext(
                            previous_question=current_report.question,
                            previous_plan=current_report.analysis_plan,
                        )
                        if refine and isinstance(current_report, ReportContent)
                        else None
                    )
                    outcome = generator.generate(
                        question,
                        analyst_id=identity.analyst_id,
                        session_id=session_id,
                        session_state=st.session_state,
                        follow_up_context=context,
                    )
                if outcome.status == "report" and outcome.report is not None:
                    if isinstance(outcome.report, CompositeReportV2):
                        _save_exploration_report(outcome.report, identity, reports)
                    else:
                        saved = reports.save_report(outcome.report, identity)
                        st.session_state["active_report_id"] = saved.report_id
                    st.rerun()
                elif outcome.status == "needs_clarification":
                    st.info(outcome.message)
                elif outcome.status == "unsupported":
                    st.warning(outcome.message)
                else:
                    st.info(outcome.message)
            except Exception as exc:
                _safe_error(exc)

        if isinstance(generator, ExplorationReportGenerator):
            _pending_exploration(
                generator,
                identity,
                reports,
                session_id,
                provider_acknowledged and tracing_acknowledged,
            )
        active_report_id = (
            st.session_state.get("selected_history_report")
            if st.session_state.get("selected_history_report") != NO_REPORT
            else st.session_state.get("active_report_id")
        )
        if not submitted and active_report_id in labels:
            try:
                _render_report(
                    identity,
                    active_report_id,
                    reports,
                    consent,
                    session_id,
                    generator if isinstance(generator, ExplorationReportGenerator) else None,
                    executor,
                    visual_reporting_enabled=settings.visual_reporting_enabled,
                )
            except Exception as exc:
                _safe_error(exc)
        else:
            st.caption(
                "Your reports are private and visible only to your signed-in analyst identity."
            )
        unsaved = st.session_state.get("unsaved_exploration_report")
        if isinstance(unsaved, CompositeReportV2) and unsaved.analyst_id == identity.analyst_id:
            st.warning("The computed report is not saved. Its evidence remains in this session.")
            render_report(
                unsaved,
                st,
                visual_reporting_enabled=settings.visual_reporting_enabled,
            )
            acknowledged = True
            if unsaved.completeness == "incomplete":
                failed = [
                    section.section_id
                    for section in unsaved.sections
                    if section.outcome.status == "failed"
                ]
                acknowledged = st.checkbox(
                    "I acknowledge the listed failed sections and want to save "
                    "this incomplete report",
                    key=f"ack_incomplete_{session_id}_{unsaved.report_id}_{unsaved.revision}",
                )
            if st.button("Save unsaved report", disabled=not acknowledged):
                if unsaved.completeness == "incomplete":
                    unsaved = CompositeReportV2.model_validate(
                        unsaved.model_dump()
                        | {
                            "incomplete_acknowledgement": IncompleteAcknowledgement(
                                analyst_id=identity.analyst_id,
                                session_id=unsaved.session_id,
                                report_id=unsaved.report_id,
                                revision=unsaved.revision,
                                failed_section_ids=failed,
                                acknowledged_at=datetime.now(UTC),
                            ),
                        }
                    )
                _save_exploration_report(unsaved, identity, reports)
                st.rerun()
    except Exception as exc:
        _safe_error(exc)


if __name__ == "__main__":
    main()
