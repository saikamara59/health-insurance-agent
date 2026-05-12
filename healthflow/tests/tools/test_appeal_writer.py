from healthflow.models.schemas import CoverageArgument, DenialAnalysis
from healthflow.tools.appeal_writer import AppealWriter


SAMPLE_ANALYSIS = DenialAnalysis(
    denial_reason_code="CO-50",
    denial_reason="Not medically necessary",
    treatment_denied="MRI of lumbar spine",
    policy_section_cited="LCD L35936",
    appeal_deadline="60 days",
    denial_date="03/15/2026",
)

SAMPLE_ARGUMENT = CoverageArgument(
    cms_rule="Medicare covers services when medically necessary as defined in Section 1862(a)(1)(A) of the Social Security Act.",
    common_appeal_grounds=[
        "Provide detailed clinical documentation supporting medical necessity",
        "Include physician letter explaining why the service is required",
    ],
    success_precedents=[
        "CMS Manual Chapter 13 §13.5.1 — Redetermination rights",
        "42 CFR §405.940-405.958 — Medicare appeals process",
    ],
)


def test_letter_contains_denial_details():
    writer = AppealWriter()
    letter = writer.generate(SAMPLE_ANALYSIS, SAMPLE_ARGUMENT)
    assert "CO-50" in letter
    assert "MRI of lumbar spine" in letter or "MRI" in letter
    assert "not medically necessary" in letter.lower() or "medical necessity" in letter.lower()


def test_letter_contains_coverage_argument():
    writer = AppealWriter()
    letter = writer.generate(SAMPLE_ANALYSIS, SAMPLE_ARGUMENT)
    assert "1862(a)(1)(A)" in letter or "medically necessary" in letter.lower()
    assert "clinical documentation" in letter.lower()


def test_letter_has_placeholders():
    writer = AppealWriter()
    letter = writer.generate(SAMPLE_ANALYSIS, SAMPLE_ARGUMENT)
    assert "[PATIENT_NAME]" in letter
    assert "[DOB]" in letter
    assert "[MEMBER_ID]" in letter
    assert "[PROVIDER_NAME]" in letter
    assert "[CLAIM_NUMBER]" in letter


def test_letter_has_formal_structure():
    writer = AppealWriter()
    letter = writer.generate(SAMPLE_ANALYSIS, SAMPLE_ARGUMENT)
    # Has a date
    assert "202" in letter  # Year in date
    # Has RE: line
    assert "RE:" in letter or "Re:" in letter
    # Has closing
    assert "Sincerely" in letter or "sincerely" in letter.lower()
    # Has opening appeal statement
    assert "appeal" in letter.lower()


def test_letter_includes_precedents():
    writer = AppealWriter()
    letter = writer.generate(SAMPLE_ANALYSIS, SAMPLE_ARGUMENT)
    assert "42 CFR" in letter or "CMS Manual" in letter
