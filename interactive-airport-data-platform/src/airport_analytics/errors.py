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


class UnsupportedAnalysisError(PlatformError):
    code = "unsupported_analysis"
    user_message = "This analysis is not supported by the available data."


class ProviderError(PlatformError):
    code = "provider_error"
    user_message = "The configured model provider is unavailable or returned an invalid response."


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
