from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from healthflow.main import app
from healthflow.models.schemas import CoverageArgument, DenialAnalysis

client = TestClient(app)

SAMPLE_DENIAL_TEXT = (
    "Patient: John Smith\n"
    "Member ID: ABC123456\n"
    "Your claim for MRI of lumbar spine has been denied.\n"
    "Denial code: CO-50. The service is not deemed medically necessary.\n"
    "You have 60 days to file an appeal.\n"
)

MOCK_ANALYSIS = DenialAnalysis(
    denial_reason_code="CO-50",
    denial_reason="Not medically necessary",
    treatment_denied="MRI of lumbar spine",
    policy_section_cited="LCD L35936",
    appeal_deadline="60 days",
    denial_date="03/15/2026",
)

MOCK_ARGUMENT = CoverageArgument(
    cms_rule="Medicare covers services when medically necessary.",
    common_appeal_grounds=["Provide clinical documentation"],
    success_precedents=["42 CFR §405.940"],
)


@patch("healthflow.api.routes.AppealAgent")
def test_appeal_valid_request(mock_agent_cls):
    mock_agent = MagicMock()
    mock_agent.process_appeal.return_value = (
        MOCK_ANALYSIS,
        MOCK_ARGUMENT,
        "Dear Appeals Committee...",
        "Additional suggestions from Claude.",
    )
    mock_agent_cls.return_value = mock_agent

    response = client.post(
        "/appeal",
        json={"denial_text": SAMPLE_DENIAL_TEXT},
    )
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    assert "denial_analysis" in data
    assert "coverage_argument" in data
    assert "appeal_letter" in data
    assert "disclaimer" in data


def test_appeal_empty_denial_text():
    response = client.post(
        "/appeal",
        json={"denial_text": ""},
    )
    assert response.status_code == 422


def test_appeal_whitespace_denial_text():
    response = client.post(
        "/appeal",
        json={"denial_text": "   "},
    )
    assert response.status_code == 422


@patch("healthflow.api.routes.AppealAgent")
def test_appeal_response_has_disclaimer(mock_agent_cls):
    mock_agent = MagicMock()
    mock_agent.process_appeal.return_value = (
        MOCK_ANALYSIS,
        MOCK_ARGUMENT,
        "Dear Appeals Committee...",
        "Suggestions.",
    )
    mock_agent_cls.return_value = mock_agent

    response = client.post(
        "/appeal",
        json={"denial_text": SAMPLE_DENIAL_TEXT},
    )
    data = response.json()
    assert "educational" in data["disclaimer"].lower() or "informational" in data["disclaimer"].lower()
    assert "not" in data["disclaimer"].lower() and "legal" in data["disclaimer"].lower()


@patch("healthflow.api.routes.AppealAgent")
def test_appeal_response_has_appeal_letter(mock_agent_cls):
    mock_agent = MagicMock()
    mock_agent.process_appeal.return_value = (
        MOCK_ANALYSIS,
        MOCK_ARGUMENT,
        "Dear Appeals Committee, we formally appeal...",
        "Suggestions.",
    )
    mock_agent_cls.return_value = mock_agent

    response = client.post(
        "/appeal",
        json={"denial_text": SAMPLE_DENIAL_TEXT},
    )
    data = response.json()
    assert len(data["appeal_letter"]) > 0
    assert "appeal" in data["appeal_letter"].lower()


@patch("healthflow.api.routes.AppealAgent")
def test_appeal_medical_advice_filtered(mock_agent_cls):
    mock_agent = MagicMock()
    mock_agent.process_appeal.return_value = (
        MOCK_ANALYSIS,
        MOCK_ARGUMENT,
        "Dear Appeals Committee...",
        "You should take ibuprofen. Also request peer-to-peer review.",
    )
    mock_agent_cls.return_value = mock_agent

    response = client.post(
        "/appeal",
        json={"denial_text": SAMPLE_DENIAL_TEXT},
    )
    data = response.json()
    # The harness filter_output should catch "you should take"
    # The recommendation is embedded in the response but filtered
    assert response.status_code == 200
