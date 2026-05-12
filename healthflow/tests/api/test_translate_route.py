from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from healthflow.main import app

client = TestClient(app)

SAMPLE_SOB = """SUMMARY OF BENEFITS

INPATIENT HOSPITAL CARE
You pay $250 copay per day for days 1-5.
Prior authorization required.

EMERGENCY CARE
Emergency room: $90 copay (waived if admitted)
Ambulance: $250 copay

PRESCRIPTION DRUG COVERAGE
Tier 1 (Generic): $10 copay
Tier 2 (Preferred Brand): $45 copay
"""


@patch("healthflow.api.routes.TranslationAgent")
def test_translate_valid_request(mock_agent_cls):
    mock_agent = MagicMock()
    mock_agent.translate.return_value = (
        "The ER copay is $90. If you are admitted, the copay is waived.",
        ["EMERGENCY CARE"],
    )
    mock_agent_cls.return_value = mock_agent

    response = client.post(
        "/translate",
        json={
            "document_text": SAMPLE_SOB,
            "question": "What is the ER copay?",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "session_id" in data
    assert "relevant_sections" in data
    assert "disclaimer" in data
    assert data["question"] == "What is the ER copay?"


@patch("healthflow.api.routes.TranslationAgent")
def test_translate_filters_medical_advice(mock_agent_cls):
    mock_agent = MagicMock()
    mock_agent.translate.return_value = (
        "Your ER copay is $90. Also, you should take aspirin before going.",
        ["EMERGENCY CARE"],
    )
    mock_agent_cls.return_value = mock_agent

    response = client.post(
        "/translate",
        json={
            "document_text": SAMPLE_SOB,
            "question": "What is the ER copay?",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "you should take" not in data["answer"].lower()


def test_translate_empty_document():
    response = client.post(
        "/translate",
        json={"document_text": "", "question": "What is covered?"},
    )
    assert response.status_code == 422


def test_translate_empty_question():
    response = client.post(
        "/translate",
        json={"document_text": SAMPLE_SOB, "question": ""},
    )
    assert response.status_code == 422


def test_translate_document_too_long():
    response = client.post(
        "/translate",
        json={"document_text": "x" * 50001, "question": "What is covered?"},
    )
    assert response.status_code == 422


@patch("healthflow.api.routes.TranslationAgent")
def test_translate_response_has_disclaimer(mock_agent_cls):
    mock_agent = MagicMock()
    mock_agent.translate.return_value = ("Answer text.", ["EMERGENCY CARE"])
    mock_agent_cls.return_value = mock_agent

    response = client.post(
        "/translate",
        json={"document_text": SAMPLE_SOB, "question": "ER copay?"},
    )
    data = response.json()
    assert "not medical advice" in data["disclaimer"].lower()
