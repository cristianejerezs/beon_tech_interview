"""Input bounds enforced before model invocation or budget reservation."""

from airport_analytics.errors import InvalidQuestionError

MAX_QUESTION_CODE_POINTS = 2000


def validate_question(value: object) -> str:
    if not isinstance(value, str):
        raise InvalidQuestionError()
    trimmed = value.strip()
    if not trimmed or len(trimmed) > MAX_QUESTION_CODE_POINTS:
        raise InvalidQuestionError()
    return trimmed
