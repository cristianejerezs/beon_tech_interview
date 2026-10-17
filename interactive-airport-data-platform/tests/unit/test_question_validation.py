import pytest

from airport_analytics.analytics.question_validation import validate_question
from airport_analytics.errors import InvalidQuestionError


@pytest.mark.parametrize("question", ["", "   \r\n\t", None, 5])
def test_rejects_empty_whitespace_and_non_text_questions(question: object) -> None:
    with pytest.raises(InvalidQuestionError):
        validate_question(question)


def test_trims_question_and_counts_unicode_code_points() -> None:
    assert validate_question("  Which route?  ") == "Which route?"
    assert len(validate_question("😀" * 2000)) == 2000


def test_rejects_more_than_2000_code_points_after_trimming() -> None:
    with pytest.raises(InvalidQuestionError):
        validate_question(" " + ("😀" * 2001) + " ")


def test_accepts_exactly_2000_code_points_after_trimming() -> None:
    assert validate_question(" " + ("a" * 2000) + " ") == "a" * 2000
