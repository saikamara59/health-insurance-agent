import pytest
from pydantic import ValidationError
from healthflow.models.schemas import (
    AppealRequest,
    AppealResponse,
    CoverageArgument,
    DenialAnalysis,
)


def test_appeal_request_valid():
    req = AppealRequest(denial_text="Your claim has been denied under CO-50.")
    assert req.denial_text == "Your claim has been denied under CO-50."
    assert req.additional_context == ""


def test_appeal_request_with_context():
    req = AppealRequest(
        denial_text="Denied",
        additional_context="Patient has documented history.",
    )
    assert req.additional_context == "Patient has documented history."


def test_appeal_request_empty_denial_text():
    with pytest.raises(ValidationError):
        AppealRequest(denial_text="")


def test_appeal_request_whitespace_only_denial_text():
    with pytest.raises(ValidationError):
        AppealRequest(denial_text="   ")


def test_appeal_request_denial_text_too_long():
    with pytest.raises(ValidationError):
        AppealRequest(denial_text="x" * 50001)


def test_appeal_request_context_too_long():
    with pytest.raises(ValidationError):
        AppealRequest(denial_text="Denied", additional_context="x" * 1001)


def test_denial_analysis_all_fields():
    da = DenialAnalysis(
        denial_reason_code="CO-50",
        denial_reason="Not medically necessary",
        treatment_denied="MRI of lumbar spine",
        policy_section_cited="LCD L35936",
        appeal_deadline="60 days",
        denial_date="03/15/2026",
    )
    assert da.denial_reason_code == "CO-50"
    assert da.treatment_denied == "MRI of lumbar spine"


def test_denial_analysis_optional_fields_none():
    da = DenialAnalysis(
        denial_reason_code=None,
        denial_reason="Unknown reason",
        treatment_denied="Physical therapy",
        policy_section_cited=None,
        appeal_deadline=None,
        denial_date=None,
    )
    assert da.denial_reason_code is None
    assert da.policy_section_cited is None


def test_coverage_argument():
    ca = CoverageArgument(
        cms_rule="Medicare covers services when medically necessary.",
        common_appeal_grounds=["Provide clinical documentation"],
        success_precedents=["42 CFR 405.940"],
    )
    assert len(ca.common_appeal_grounds) == 1
    assert len(ca.success_precedents) == 1


def test_appeal_response_full():
    da = DenialAnalysis(
        denial_reason_code="CO-50",
        denial_reason="Not medically necessary",
        treatment_denied="MRI",
        policy_section_cited=None,
        appeal_deadline=None,
        denial_date=None,
    )
    ca = CoverageArgument(
        cms_rule="Section 1862(a)(1)(A)",
        common_appeal_grounds=["Provide documentation"],
        success_precedents=["42 CFR 405.940"],
    )
    resp = AppealResponse(
        session_id="abc-123",
        denial_analysis=da,
        coverage_argument=ca,
        appeal_letter="Dear Appeals Committee...",
        disclaimer="For educational purposes only.",
    )
    assert resp.session_id == "abc-123"
    assert resp.appeal_letter.startswith("Dear")
    assert resp.disclaimer == "For educational purposes only."
