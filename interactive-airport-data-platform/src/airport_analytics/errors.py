"""Typed, user-safe application errors."""


class PlatformError(Exception):
    """An expected application failure with a safe message for analysts."""

    code = "application_error"
    user_message = "The request could not be completed."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.user_message)
        self.detail = message or self.user_message


class InvalidQuestionError(PlatformError):
    code = "invalid_question"
    user_message = "Enter a non-empty question of up to 2,000 Unicode code points."


class InvalidPlanError(PlatformError):
    code = "invalid_plan"
    user_message = "The question could not be safely interpreted. Please rephrase it."

    def __init__(self, message: str | None = None) -> None:
        safe_reasons = {
            "The selected metric cannot be grouped by that dimension.": (
                "The model selected an unsupported metric/grouping combination."
            ),
            "A time range must include a start or end date.": (
                "The model returned an empty date range."
            ),
            "The plan selected a metric outside the approved catalog.": (
                "The model selected an unsupported metric."
            ),
            "The plan selected a dimension outside the approved catalog.": (
                "The model selected an unsupported grouping."
            ),
            "The plan selected a filter outside the approved catalog.": (
                "The model selected an unsupported filter."
            ),
            "The model response does not match the approved plan schema.": (
                "The model response did not match the required analysis-plan format."
            ),
            "The provider did not return a valid structured plan.": (
                "The model did not return a complete structured analysis plan."
            ),
        }
        if message in safe_reasons:
            self.user_message = (
                safe_reasons[message]
                + " No query was executed. Specify the airport (EWR, JFK, or LGA), "
                "metric, and period, or ask the model to clarify."
            )
        super().__init__(message)


class UnsupportedAnalysisError(PlatformError):
    code = "unsupported_analysis"
    user_message = "This analysis is not supported by the available data."


class PreferenceConflictError(PlatformError):
    code = "preference_conflict"
    user_message = (
        "Presentation preferences changed. Refresh the report and explicitly retry your update."
    )


class PresentationPreferenceError(PlatformError):
    code = "unsupported_presentation_preference"
    user_message = (
        "This saved presentation preference is invalid or incompatible with the available "
        "evidence. Choose a compatible view or return to the default."
    )


class VisualEvidenceError(PlatformError):
    code = "invalid_visual_evidence"
    user_message = (
        "The saved evidence cannot support this visual. Retain the report and exact results; "
        "review the analytical definition or refine the question."
    )


class MissingVisualEvidenceError(VisualEvidenceError):
    code = "missing_visual_evidence"
    user_message = (
        "Required saved visual evidence is unavailable. Available saved results remain usable. "
        "Current source data will not be substituted."
    )


class VisualRenderError(PlatformError):
    code = "visual_render_failed"
    user_message = (
        "The visual could not be rendered. Your report and exact results are unchanged. "
        "Retry explicitly or choose the evidence table."
    )


class VisualExportError(PlatformError):
    code = "visual_export_failed"
    user_message = (
        "The complete visual export could not be prepared. No partial download was produced. "
        "Your report is unchanged; check renderer resources and retry explicitly."
    )


class PdfRuntimeUnavailableError(VisualExportError):
    code = "pdf_runtime_unavailable"
    user_message = (
        "Tagged PDF export is unavailable on this machine because the Pango text runtime "
        "used by WeasyPrint is missing. CSV exports and on-screen charts still work. "
        "Run the app with the provided Docker image, or install Pango and set "
        "WEASYPRINT_DLL_DIRECTORIES (see README)."
    )


class BinWidthRequiredError(InvalidPlanError):
    code = "bin_width_confirmation_required"

    def __init__(self, width: float) -> None:
        self.suggested_width = width
        self.user_message = (
            f"More than 100 bins would be required. Explicitly accept a bin width of "
            f"{width:g} or larger, narrow the scope, or cancel."
        )
        super().__init__(self.user_message)


class WeatherUnitsRequiredError(UnsupportedAnalysisError):
    code = "weather_units_required"
    user_message = (
        "Weather correlation requires verified local units for this source snapshot. "
        "Verify the weather unit declaration or remove this comparison; unrelated analyses "
        "remain available."
    )


class ProviderError(PlatformError):
    code = "provider_error"
    user_message = "The configured model provider is unavailable or returned an invalid response."


class ProviderRequestError(ProviderError):
    code = "provider_request_error"

    def __init__(
        self,
        status_code: int,
        *,
        provider_code: object = None,
        provider_param: object = None,
        retry_after_seconds: float | None = None,
        retried: bool = False,
        daily_limit: bool = False,
    ) -> None:
        self.status_code = status_code
        self.retry_after_seconds = retry_after_seconds
        self.retried = retried
        self.daily_limit = daily_limit
        guidance = {
            400: (
                "The provider rejected the request or could not produce a valid structured "
                "response. HTTP 400 alone does not identify which."
            ),
            401: "The provider rejected the API key. Check the key in your local configuration.",
            403: "The provider denied access. Check your account and model permissions.",
            404: (
                "The provider endpoint or model was not found. Check the configured URL and model."
            ),
            413: "The provider rejected the request size. Reduce the question or active context.",
            422: "The provider could not process the request format or model parameters.",
            429: (
                "The provider's daily limit (requests or tokens per day) for this model was "
                "reached. The request was rejected and not counted against the local quota."
                if daily_limit
                else "The provider's rate limit (requests or tokens per minute) was reached. "
                "The request was rejected and not counted against the local quota."
            ),
        }
        self.user_message = f"Model provider HTTP {status_code}: " + guidance.get(
            status_code, "The provider service failed. Check its service status."
        )
        safe_codes = {
            "json_validate_failed": (
                "The generated response failed the provider's JSON/schema validation."
            ),
            "invalid_request_error": "The provider reported an invalid request.",
            "context_length_exceeded": "The request exceeded the model's context limit.",
            "model_not_found": "The configured model was not found.",
        }
        if isinstance(provider_code, str) and provider_code in safe_codes:
            self.user_message += f" Code: {provider_code}. {safe_codes[provider_code]}"
        safe_params = {
            "response_format",
            "response_format.json_schema",
            "response_format.json_schema.schema",
            "max_tokens",
            "max_completion_tokens",
            "reasoning_effort",
            "messages",
            "temperature",
        }
        if isinstance(provider_param, str) and provider_param in safe_params:
            self.user_message += f" Rejected parameter: {provider_param}."
        if status_code == 429:
            if retry_after_seconds is None:
                wait = "a minute"
            elif retry_after_seconds >= 120:
                wait = f"about {round(retry_after_seconds / 60)} minutes"
            else:
                wait = f"about {max(1, round(retry_after_seconds))} seconds"
            self.user_message += (
                f" One automatic retry after the provider's wait also failed. Retry in {wait}"
                if retried
                else f" Retry in {wait}"
            )
            self.user_message += (
                ", or choose another model; daily limits apply per model. "
                "No provider switch was made."
                if daily_limit
                else ", or choose a model with a higher per-minute limit. "
                "No provider switch was made."
            )
        else:
            self.user_message += " No automatic retry or provider switch was performed."
        super().__init__(self.user_message)


class ProviderTimeoutError(ProviderError):
    code = "provider_timeout"
    user_message = (
        "The model provider timed out. Check service availability "
        "and the configured model timeout. "
        "Hosted acceptance is unknown; its budget reservation remains held. No automatic retry."
    )


class ProviderConnectionError(ProviderError):
    code = "provider_connection_error"
    user_message = (
        "Could not connect to the configured model endpoint. Check the service, URL, and network. "
        "No automatic retry or provider switch was performed."
    )


class BudgetExceededError(PlatformError):
    code = "budget_exhausted"
    user_message = "The hosted-model budget or provider quota is exhausted."


class CostUnboundedError(PlatformError):
    code = "cost_unbounded"
    user_message = "The maximum cost of this hosted request cannot be established."


class DatasetUnavailableError(PlatformError):
    code = "dataset_unavailable"
    user_message = "The required validated source data is unavailable."


class QueryExecutionError(PlatformError):
    code = "query_execution_error"
    user_message = "The validated analysis could not be executed."


class QueryTimeoutError(QueryExecutionError):
    code = "query_timeout"
    user_message = "The analysis took too long and was stopped. Narrow the question and try again."


class AuthorizationError(PlatformError):
    code = "authorization_error"
    user_message = "You are not authorized to access this resource."


class ReportFormatError(PlatformError):
    code = "report_format_error"
    user_message = (
        "The saved report is corrupt or uses an unsupported version. It has not been modified."
    )


class IncompleteReportError(PlatformError):
    code = "incomplete_report_acknowledgement_required"
    user_message = (
        "This report has failed sections. Acknowledge the exact incomplete report "
        "before saving or exporting."
    )


class DisclosureRequiredError(PlatformError):
    code = "provider_disclosure_required"
    user_message = "Review the provider-use notice before continuing."


class ConsentError(PlatformError):
    code = "consent_error"
    user_message = "The requested reuse action could not be authorized."


def user_safe_message(error: Exception) -> str:
    """Return a deliberately non-sensitive message for expected failures."""
    if isinstance(error, PlatformError):
        return error.user_message
    return "An unexpected error occurred. Please try again or contact the deployment owner."
