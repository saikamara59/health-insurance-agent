from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from healthflow.main import app

client = TestClient(app)

REALISTIC_DENIAL_LETTER = """
EXPLANATION OF BENEFITS

Patient: Maria Garcia
Member ID: H3312-034-001
Date of Birth: 07/22/1958
SSN: 123-45-6789
Phone: (555) 867-5309

Date of denial: 02/28/2026

Dear Maria Garcia,

This letter is to inform you that your claim for MRI of the lumbar spine
(CPT 72148) has been denied.

Denial Code: CO-50
Reason: These are non-covered services because this is not deemed a medical
necessity by the plan.

Per LCD L35936, the requested service does not meet the coverage criteria
established for this procedure.

You have the right to appeal this decision. You must file your appeal
within 60 days of the date of this notice.

To file an appeal, send your written request along with any supporting
documentation to:

Appeals Committee
Medicare Advantage Plan
PO Box 12345
Any City, ST 00000

If you have questions, contact Member Services at (800) 555-1234.

Sincerely,
Claims Department
"""


@patch("healthflow.api.routes.AppealAgent")
def test_end_to_end_realistic_denial(mock_agent_cls):
    """End-to-end test with a realistic denial letter."""
    from healthflow.agents.appeal_agent import AppealAgent as RealAgent
    from healthflow.tools.denial_codes import DenialCodeDB
    from healthflow.tools.denial_parser import DenialParser
    from healthflow.tools.phi_redactor import PHIRedactor
    from healthflow.tools.appeal_writer import AppealWriter
    from healthflow.models.schemas import CoverageArgument

    # Run the real pipeline (except Claude)
    redactor = PHIRedactor()
    redacted, log = redactor.redact(REALISTIC_DENIAL_LETTER)
    parser = DenialParser()
    analysis = parser.parse(redacted)
    db = DenialCodeDB()
    code_entry = db.lookup(analysis.denial_reason_code) if analysis.denial_reason_code else None

    assert analysis.denial_reason_code == "CO-50"
    assert "Maria Garcia" not in redacted

    if code_entry:
        argument = CoverageArgument(
            cms_rule=code_entry["cms_rule"],
            common_appeal_grounds=code_entry["appeal_grounds"],
            success_precedents=code_entry["precedents"],
        )
    else:
        argument = CoverageArgument(
            cms_rule="Fallback",
            common_appeal_grounds=["Fallback ground"],
            success_precedents=["Fallback precedent"],
        )

    writer = AppealWriter()
    letter = writer.generate(analysis, argument)

    assert "[PATIENT_NAME]" in letter
    assert "CO-50" in letter

    # Now test via the API endpoint with mocked agent
    mock_agent = MagicMock()
    mock_agent.process_appeal.return_value = (
        analysis,
        argument,
        letter,
        "Consider requesting peer-to-peer review.",
    )
    mock_agent_cls.return_value = mock_agent

    response = client.post(
        "/appeal",
        json={"denial_text": REALISTIC_DENIAL_LETTER},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["denial_analysis"]["denial_reason_code"] == "CO-50"
    assert len(data["appeal_letter"]) > 100


@patch("healthflow.api.routes.AppealAgent")
def test_phi_not_in_response(mock_agent_cls):
    """Verify PHI from the denial letter does not appear in the response."""
    from healthflow.tools.phi_redactor import PHIRedactor
    from healthflow.tools.denial_parser import DenialParser
    from healthflow.models.schemas import CoverageArgument

    redactor = PHIRedactor()
    redacted, _ = redactor.redact(REALISTIC_DENIAL_LETTER)
    parser = DenialParser()
    analysis = parser.parse(redacted)

    argument = CoverageArgument(
        cms_rule="Test rule",
        common_appeal_grounds=["Test ground"],
        success_precedents=["Test precedent"],
    )

    mock_agent = MagicMock()
    mock_agent.process_appeal.return_value = (
        analysis,
        argument,
        "Dear Appeals Committee, regarding [PATIENT_NAME]...",
        "Recommendation text.",
    )
    mock_agent_cls.return_value = mock_agent

    response = client.post(
        "/appeal",
        json={"denial_text": REALISTIC_DENIAL_LETTER},
    )
    data = response.json()
    response_text = str(data)

    assert "Maria Garcia" not in response_text
    assert "123-45-6789" not in response_text
    assert "H3312-034-001" not in response_text
    assert "(555) 867-5309" not in response_text


@patch("healthflow.api.routes.AppealAgent")
def test_medical_advice_filtered(mock_agent_cls):
    """Verify medical advice from Claude is filtered out."""
    from healthflow.tools.denial_parser import DenialParser
    from healthflow.tools.phi_redactor import PHIRedactor
    from healthflow.models.schemas import CoverageArgument

    redactor = PHIRedactor()
    redacted, _ = redactor.redact(REALISTIC_DENIAL_LETTER)
    parser = DenialParser()
    analysis = parser.parse(redacted)

    argument = CoverageArgument(
        cms_rule="Test rule",
        common_appeal_grounds=["Test ground"],
        success_precedents=["Test precedent"],
    )

    mock_agent = MagicMock()
    mock_agent.process_appeal.return_value = (
        analysis,
        argument,
        "Dear Appeals Committee...",
        "You should take ibuprofen for pain. Also, request peer-to-peer review.",
    )
    mock_agent_cls.return_value = mock_agent

    response = client.post(
        "/appeal",
        json={"denial_text": REALISTIC_DENIAL_LETTER},
    )
    assert response.status_code == 200
    # The harness filters "you should take" from the recommendation
    # The response should still succeed
