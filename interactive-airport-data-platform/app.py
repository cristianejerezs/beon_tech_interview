"""Streamlit interface for the Interactive Airport Data Platform."""

from __future__ import annotations

import logging
import os
import uuid
from collections.abc import Mapping
from dataclasses import replace

import streamlit as st

from airport_analytics.analytics.budget import BudgetLedger
from airport_analytics.analytics.execution import DuckDBExecutor
from airport_analytics.analytics.model_client import FollowUpContext, LangChainPlanClient
from airport_analytics.analytics.provider_policy import (
    ProviderDescriptor,
    has_disclosed,
    mark_disclosed,
)
from airport_analytics.auth import (
    AnalystIdentity,
    resolve_analyst_identity,
    resolve_development_identity,
)
from airport_analytics.config import Settings
from airport_analytics.consent.repository import ConsentPurpose, ConsentRepository
from airport_analytics.consent.service import ConsentService
from airport_analytics.errors import PlatformError, user_safe_message
from airport_analytics.history.repository import ReportRepository
from airport_analytics.observability.tracing import TracingConfig
from airport_analytics.reports.export import export_report_csv, export_report_pdf
from airport_analytics.reports.generation import ReportGenerator
from airport_analytics.reports.rendering import render_report
from airport_analytics.storage import Storage

LOGGER = logging.getLogger(__name__)
NO_REPORT = "(No report selected)"
TRACING_ACK_KEY = "airport_langsmith_disclosure_acknowledged"
DEV_SIGN_IN_KEY = "airport_development_signed_in"
PROVIDER_LABELS = {"ollama": "Ollama (local)", "openai": "OpenAI (hosted)"}
PURPOSE_LABELS: dict[ConsentPurpose, str] = {
    "faq": "FAQ examples",
    "system_improvement": "System improvement",
}


@st.cache_resource(show_spinner=False)
def _storage(database_path: str) -> Storage:
    return Storage(database_path)


@st.cache_resource(show_spinner="Validating the local source data...")
def _executor(source_data_dir: str, timeout_seconds: int) -> DuckDBExecutor:
    return DuckDBExecutor(source_data_dir, timeout_seconds=timeout_seconds)


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
        settings.model_name if settings.model_provider == "openai" else "",
    ).strip()
    return replace(settings, model_provider="openai", model_name=hosted_model)


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
    with st.expander("Optional sharing and reuse controls"):
        st.write(
            "Private analysis works without consent. If enabled, only the question, "
            "answer, metric definition, scope, and up to ten result rows are shared; "
            "your analyst identity is omitted. Withdrawal stops future reuse but does "
            "not remove material already shared."
        )
        for purpose, label in PURPOSE_LABELS.items():
            active = service.is_active(identity, session_id, purpose, st.session_state)
            st.write(f"**{label}:** {'Enabled for this session' if active else 'Off'}")
            disabled = not service.shared_reuse_enabled
            if disabled:
                st.caption("Shared reuse is disabled by deployment configuration.")
            if service.production and not service.retention_policy_approved:
                st.caption(
                    "Production reuse is blocked until retention and deletion "
                    "procedures are approved."
                )
            if active:
                if st.button(
                    f"Withdraw {label} consent",
                    key=f"withdraw_{purpose}",
                    disabled=disabled,
                ):
                    service.set_consent(
                        identity,
                        session_id,
                        purpose,
                        False,
                        st.session_state,
                        notice_version="v1",
                    )
                    st.rerun()
            elif st.button(
                f"Enable {label} reuse",
                key=f"grant_{purpose}",
                disabled=disabled,
            ):
                service.set_consent(
                    identity,
                    session_id,
                    purpose,
                    True,
                    st.session_state,
                    notice_version="v1",
                )
                st.rerun()


def _provider_controls(settings: Settings, budget: BudgetLedger) -> str:
    choices = ["ollama"]
    hosted_model = os.getenv(
        "AIRPORT_OPENAI_MODEL_NAME",
        settings.model_name if settings.model_provider == "openai" else "",
    ).strip()
    if settings.openai_api_key and hosted_model:
        choices.append("openai")
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
    st.sidebar.metric("Hosted budget remaining this UTC month", f"${budget.remaining_usd():.2f}")
    if selected == "openai":
        provider_settings = _client_settings(settings, selected)
        provider = ProviderDescriptor(
            provider_id="openai",
            model_id=provider_settings.model_name,
            product_improvement_terms=settings.hosted_product_improvement_terms,
            hosted=True,
        )
        st.sidebar.warning(
            f"Hosted request notice: your question and the minimal plan schema/catalog "
            f"will be sent to the configured OpenAI-compatible service "
            f"({provider.model_id}) at "
            f"{settings.openai_base_url or 'https://api.openai.com/v1'}. "
            f"No source rows, database "
            f"access, analyst identifier, or saved report history are sent. "
            f"Product-improvement terms: {provider.product_improvement_terms}."
        )
        if has_disclosed(st.session_state, provider):
            st.sidebar.success("Hosted-provider notice acknowledged for this configuration.")
        elif st.sidebar.button(
            "I understand and acknowledge hosted processing",
            key=f"ack_provider_{provider.provider_id}_{provider.model_id}",
        ):
            mark_disclosed(st.session_state, provider)
            st.rerun()
    return selected


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
            st.json(artifact.content["definitions"])
            st.json(artifact.content["scope"])
            st.dataframe(artifact.content["summary_rows"], hide_index=True)
            if st.button("Use this FAQ question", key=f"faq_{artifact.artifact_id}"):
                st.session_state["airport_question"] = artifact.content["question"]


def _tracing_disclosure(tracing: TracingConfig) -> bool:
    if not tracing.enabled:
        return True
    st.sidebar.warning(
        "LangSmith tracing is enabled by the deployment operator. Traces may include "
        "your question, analysis-plan context, aggregate results, and generated report text."
    )
    if tracing_acknowledged(tracing, st.session_state):
        return True
    if st.sidebar.button(
        "I understand and acknowledge LangSmith tracing",
        key="ack_langsmith_tracing",
    ):
        st.session_state[TRACING_ACK_KEY] = True
        st.rerun()
    return False


def tracing_acknowledged(tracing: TracingConfig, state: Mapping[str, object]) -> bool:
    return not tracing.enabled or state.get(TRACING_ACK_KEY) is True


def _render_report(
    identity: AnalystIdentity,
    report_id: str,
    reports: ReportRepository,
    consent: ConsentService,
    session_id: str,
) -> None:
    report = reports.get_report(identity, report_id)
    st.session_state["active_report_id"] = report.report_id
    render_report(report, st)
    csv_data = export_report_csv(reports.get_report(identity, report.report_id))
    pdf_data = export_report_pdf(reports.get_report(identity, report.report_id))
    col_csv, col_pdf, col_delete = st.columns(3)
    col_csv.download_button(
        "Download result table (CSV)",
        data=csv_data,
        file_name=f"airport-report-{report.report_id}.csv",
        mime="text/csv",
        key=f"csv_{report.report_id}",
    )
    col_pdf.download_button(
        "Download complete report (PDF)",
        data=pdf_data,
        file_name=f"airport-report-{report.report_id}.pdf",
        mime="application/pdf",
        key=f"pdf_{report.report_id}",
    )
    if col_delete.button("Delete private report", key=f"delete_{report.report_id}"):
        reports.delete_report(identity, report.report_id)
        st.session_state["active_report_id"] = None
        st.session_state["selected_history_report"] = NO_REPORT
        st.rerun()

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
        )
        _consent_panel(identity, session_id, consent)
        _faq_panel(reports)
        selected_provider = _provider_controls(settings, budget)

        history = reports.list_reports(identity)
        labels = {
            report.report_id: f"{report.created_at[:16]} — {report.question[:100]}"
            for report in history
        }
        history_options = [NO_REPORT, *labels]
        if st.session_state.get("selected_history_report") not in history_options:
            st.session_state["selected_history_report"] = NO_REPORT

        executor = _executor(str(settings.source_data_dir), settings.query_timeout_seconds)
        tracing = TracingConfig.from_env()
        model_settings = _client_settings(settings, selected_provider)
        client = LangChainPlanClient(
            model_settings,
            budget=budget,
            tracing=tracing,
        )
        tracing_acknowledged = _tracing_disclosure(tracing)
        generator = ReportGenerator(client, executor)

        st.header("Ask an airport-data question")
        if selected_provider == "openai":
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

        current_report_id = st.session_state.get("active_report_id")
        current_report = (
            reports.get_report(identity, current_report_id) if current_report_id in labels else None
        )
        with st.form("question_form", clear_on_submit=True):
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
                disabled=current_report is None,
            )
            submitted = st.form_submit_button(
                "Generate report",
                disabled=not (provider_acknowledged and tracing_acknowledged),
                type="primary",
            )
        if submitted:
            st.session_state["active_report_id"] = None
            st.session_state["selected_history_report"] = NO_REPORT
            try:
                context = (
                    FollowUpContext(
                        previous_question=current_report.question,
                        previous_plan=current_report.analysis_plan,
                    )
                    if refine and current_report is not None
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

        st.subheader("Private report history")
        selected_history = st.selectbox(
            "Open one of your saved reports",
            history_options,
            format_func=lambda report_id: (
                report_id if report_id == NO_REPORT else _report_label(report_id, labels)
            ),
            key="selected_history_report",
        )
        active_report_id = (
            selected_history
            if selected_history != NO_REPORT
            else st.session_state.get("active_report_id")
        )
        if active_report_id in labels:
            try:
                _render_report(identity, active_report_id, reports, consent, session_id)
            except Exception as exc:
                _safe_error(exc)
        else:
            st.caption(
                "Your reports are private and visible only to your signed-in analyst identity."
            )
    except Exception as exc:
        _safe_error(exc)


if __name__ == "__main__":
    main()
