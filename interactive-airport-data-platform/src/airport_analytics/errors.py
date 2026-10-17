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


class ProviderError(PlatformError):
    code = "provider_error"
    user_message = "The configured model provider is unavailable or returned an invalid response."


class ProviderRequestError(ProviderError):
    code = "provider_request_error"

    def __init__(self, status_code: int) -> None:
        guidance = {
            400: "The provider rejected the request format or output schema.",
            401: "The provider rejected the API key. Check the key in your local configuration.",
            403: "The provider denied access. Check your account and model permissions.",
            404: (
                "The provider endpoint or model was not found. Check the configured URL and model."
            ),
            413: "The provider rejected the request size. Reduce the question or active context.",
            422: "The provider could not process the request format or model parameters.",
            429: "The provider rate or token quota was reached. Check account limits and wait.",
        }
        self.user_message = (
            f"Model provider HTTP {status_code}: "
            + guidance.get(status_code, "The provider service failed. Check its service status.")
            + " No automatic retry or provider switch was performed."
        )
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
