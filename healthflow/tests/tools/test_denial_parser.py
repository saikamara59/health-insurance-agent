from healthflow.tools.denial_parser import DenialParser


def test_extracts_co_code():
    parser = DenialParser()
    text = "Your claim was denied with reason code CO-50. The service is not medically necessary."
    result = parser.parse(text)
    assert result.denial_reason_code == "CO-50"


def test_extracts_pr_code():
    parser = DenialParser()
    text = "Adjustment reason PR-1 applied to your claim for the deductible amount."
    result = parser.parse(text)
    assert result.denial_reason_code == "PR-1"


def test_extracts_oa_code():
    parser = DenialParser()
    text = "Claim adjusted per OA-18 duplicate claim rules."
    result = parser.parse(text)
    assert result.denial_reason_code == "OA-18"


def test_extracts_treatment_denied():
    parser = DenialParser()
    text = "The following service has been denied: MRI of the lumbar spine. This service is not covered."
    result = parser.parse(text)
    assert "MRI" in result.treatment_denied or "lumbar" in result.treatment_denied.lower()


def test_extracts_treatment_not_covered():
    parser = DenialParser()
    text = "Physical therapy sessions are not covered under your current plan."
    result = parser.parse(text)
    assert "physical therapy" in result.treatment_denied.lower()


def test_extracts_policy_section_lcd():
    parser = DenialParser()
    text = "Per LCD L35936, this service does not meet coverage criteria."
    result = parser.parse(text)
    assert result.policy_section_cited is not None
    assert "L35936" in result.policy_section_cited


def test_extracts_policy_section_cfr():
    parser = DenialParser()
    text = "As per 42 CFR §405.940, your appeal rights are outlined below."
    result = parser.parse(text)
    assert result.policy_section_cited is not None
    assert "CFR" in result.policy_section_cited


def test_extracts_appeal_deadline():
    parser = DenialParser()
    text = "You have 60 days from the date of this notice to file an appeal."
    result = parser.parse(text)
    assert result.appeal_deadline is not None
    assert "60" in result.appeal_deadline


def test_extracts_denial_date():
    parser = DenialParser()
    text = "Date of denial: 03/15/2026. Your claim for services has been denied."
    result = parser.parse(text)
    assert result.denial_date is not None
    assert "03/15/2026" in result.denial_date


def test_no_code_found():
    parser = DenialParser()
    text = "Your claim has been denied. Please contact us for more information."
    result = parser.parse(text)
    assert result.denial_reason_code is None


def test_multiple_codes_returns_first():
    parser = DenialParser()
    text = "Denial reasons: CO-50 for medical necessity and CO-97 for bundled service."
    result = parser.parse(text)
    assert result.denial_reason_code == "CO-50"
