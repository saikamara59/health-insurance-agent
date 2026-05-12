from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from healthflow.main import app

client = TestClient(app)

FULL_SOB = """SUMMARY OF BENEFITS

INPATIENT HOSPITAL CARE
You pay $250 copay per day for days 1-5.
You pay $0 copay per day for days 6-90.
Prior authorization is required for non-emergency admissions.

OUTPATIENT SERVICES
Primary care doctor visit: $20 copay
Specialist visit: $40 copay
Diagnostic tests (lab work): $20 copay
X-rays: $30 copay

PRESCRIPTION DRUG COVERAGE
Tier 1 (Generic): $10 copay
Tier 2 (Preferred Brand): $45 copay
Tier 3 (Non-Preferred Brand): $90 copay
Tier 4 (Specialty): 25% coinsurance up to $250 max

EMERGENCY CARE
Emergency room visit: $90 copay (waived if admitted within 24 hours)
Worldwide emergency coverage: same as in-network

MENTAL HEALTH SERVICES
Outpatient individual therapy: $40 copay per visit
Outpatient group therapy: $20 copay per visit
Inpatient mental health: $250 copay per day for days 1-5

PREVENTIVE CARE
Annual wellness visit: $0 copay
Flu shot: $0 copay
Colorectal cancer screening: $0 copay
Mammogram: $0 copay

DENTAL SERVICES
Preventive dental (cleaning, exam, X-rays): $0 copay
Comprehensive dental (fillings, extractions): 50% coinsurance
"""


@patch("healthflow.api.routes.TranslationAgent")
def test_full_translate_pipeline(mock_agent_cls):
    """End-to-end: document parsing → section matching → agent → output filter → response"""
    mock_agent = MagicMock()
    mock_agent.translate.return_value = (
        "Your ER copay is $90. However, if you are admitted to the hospital "
        "within 24 hours of your ER visit, the $90 copay is waived. "
        "This plan also covers emergency visits worldwide at the same rate.",
        ["EMERGENCY CARE"],
    )
    mock_agent_cls.return_value = mock_agent

    response = client.post(
        "/translate",
        json={
            "document_text": FULL_SOB,
            "question": "How much does an ER visit cost?",
        },
    )

    assert response.status_code == 200
    data = response.json()

    assert "session_id" in data
    assert data["question"] == "How much does an ER visit cost?"
    assert "$90" in data["answer"]
    assert len(data["relevant_sections"]) >= 1
    assert "not medical advice" in data["disclaimer"].lower()

    call_args = mock_agent_cls.return_value.translate.call_args
    sections_passed = call_args.kwargs["sections"]
    section_titles = [s.title for s in sections_passed]
    assert "EMERGENCY CARE" in section_titles


@patch("healthflow.api.routes.TranslationAgent")
def test_translate_drug_question(mock_agent_cls):
    mock_agent = MagicMock()
    mock_agent.translate.return_value = (
        "Generic drugs cost $10 per prescription.",
        ["PRESCRIPTION DRUG COVERAGE"],
    )
    mock_agent_cls.return_value = mock_agent

    response = client.post(
        "/translate",
        json={
            "document_text": FULL_SOB,
            "question": "How much do generic prescriptions cost?",
        },
    )

    assert response.status_code == 200
    call_args = mock_agent_cls.return_value.translate.call_args
    sections_passed = call_args.kwargs["sections"]
    section_titles = [s.title for s in sections_passed]
    assert "PRESCRIPTION DRUG COVERAGE" in section_titles


@patch("healthflow.api.routes.TranslationAgent")
def test_translate_mental_health_question(mock_agent_cls):
    mock_agent = MagicMock()
    mock_agent.translate.return_value = (
        "Therapy visits cost $40 per session.",
        ["MENTAL HEALTH SERVICES"],
    )
    mock_agent_cls.return_value = mock_agent

    response = client.post(
        "/translate",
        json={
            "document_text": FULL_SOB,
            "question": "Does this plan cover therapy?",
        },
    )

    assert response.status_code == 200
    call_args = mock_agent_cls.return_value.translate.call_args
    sections_passed = call_args.kwargs["sections"]
    section_titles = [s.title for s in sections_passed]
    assert "MENTAL HEALTH SERVICES" in section_titles


@patch("healthflow.api.routes.TranslationAgent")
def test_translate_output_filtered(mock_agent_cls):
    mock_agent = MagicMock()
    mock_agent.translate.return_value = (
        "Therapy costs $40. I recommend treatment immediately for your symptoms.",
        ["MENTAL HEALTH SERVICES"],
    )
    mock_agent_cls.return_value = mock_agent

    response = client.post(
        "/translate",
        json={
            "document_text": FULL_SOB,
            "question": "How much is therapy?",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "i recommend treatment" not in data["answer"].lower()
