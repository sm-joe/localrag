from app.services.retrieval import RetrievalService


def test_extract_filename_from_query():
    assert (
        RetrievalService._extract_filename(
            "What is in Behavioural_questions.docx?"
        )
        == "Behavioural_questions.docx"
    )


def test_extract_quoted_filename_from_query():
    assert (
        RetrievalService._extract_filename(
            'Summarize "Behavioural_questions.docx"'
        )
        == "Behavioural_questions.docx"
    )


def test_extract_filename_returns_none_for_normal_query():
    assert (
        RetrievalService._extract_filename(
            "What is retrieval augmented generation?"
        )
        is None
    )