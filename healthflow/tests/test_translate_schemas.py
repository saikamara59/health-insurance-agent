import pytest
from healthflow.models.schemas import (
    DocumentSection,
    TranslateRequest,
    TranslateResponse,
)


def test_translate_request_valid():
    req = TranslateRequest(
        document_text="SUMMARY OF BENEFITS\nInpatient: $250 copay",
        question="What is the inpatient copay?",
    )
    assert req.document_text.startswith("SUMMARY")
    assert req.question == "What is the inpatient copay?"


def test_translate_request_empty_document():
    with pytest.raises(ValueError, match="empty"):
        TranslateRequest(document_text="", question="What is covered?")


def test_translate_request_empty_question():
    with pytest.raises(ValueError, match="empty"):
        TranslateRequest(document_text="Some document text", question="")


def test_translate_request_whitespace_only_document():
    with pytest.raises(ValueError, match="empty"):
        TranslateRequest(document_text="   ", question="What is covered?")


def test_translate_request_whitespace_only_question():
    with pytest.raises(ValueError, match="empty"):
        TranslateRequest(document_text="Some doc", question="   ")


def test_translate_request_document_too_long():
    with pytest.raises(ValueError, match="50,000"):
        TranslateRequest(document_text="x" * 50001, question="What is covered?")


def test_translate_request_question_too_long():
    with pytest.raises(ValueError, match="500"):
        TranslateRequest(document_text="Some doc", question="x" * 501)


def test_document_section_model():
    section = DocumentSection(title="Inpatient Care", content="$250 copay per day")
    assert section.title == "Inpatient Care"
    assert section.content == "$250 copay per day"


def test_translate_response_model():
    resp = TranslateResponse(
        session_id="abc-123",
        question="What is the copay?",
        answer="The copay is $250 per day.",
        relevant_sections=["Inpatient Care"],
        disclaimer="Not medical advice.",
    )
    assert resp.answer == "The copay is $250 per day."
    assert len(resp.relevant_sections) == 1
