from healthflow.tools.phi_redactor import PHIRedactor


def test_redacts_patient_name():
    redactor = PHIRedactor()
    text = "Patient: John Smith\nDiagnosis: back pain"
    redacted, log = redactor.redact(text)
    assert "[PATIENT_NAME]" in redacted
    assert "John Smith" not in redacted


def test_redacts_member_name():
    redactor = PHIRedactor()
    text = "Member: Jane Doe\nClaim denied"
    redacted, log = redactor.redact(text)
    assert "[PATIENT_NAME]" in redacted
    assert "Jane Doe" not in redacted


def test_redacts_dear_name():
    redactor = PHIRedactor()
    text = "Dear Robert Johnson,\nWe regret to inform you"
    redacted, log = redactor.redact(text)
    assert "[PATIENT_NAME]" in redacted
    assert "Robert Johnson" not in redacted


def test_redacts_dob():
    redactor = PHIRedactor()
    text = "DOB: 01/15/1960\nMember ID: ABC123"
    redacted, log = redactor.redact(text)
    assert "[DOB]" in redacted
    assert "01/15/1960" not in redacted


def test_redacts_member_id():
    redactor = PHIRedactor()
    text = "Member ID: XYZ789456\nDenial reason: CO-50"
    redacted, log = redactor.redact(text)
    assert "[MEMBER_ID]" in redacted
    assert "XYZ789456" not in redacted


def test_redacts_subscriber_id():
    redactor = PHIRedactor()
    text = "Subscriber ID: H3312-034-001\nStatus: Denied"
    redacted, log = redactor.redact(text)
    assert "[MEMBER_ID]" in redacted
    assert "H3312-034-001" not in redacted


def test_redacts_ssn():
    redactor = PHIRedactor()
    text = "SSN: 123-45-6789\nClaim number: 100200"
    redacted, log = redactor.redact(text)
    assert "[SSN]" in redacted
    assert "123-45-6789" not in redacted


def test_redacts_phone():
    redactor = PHIRedactor()
    text = "Phone: (555) 123-4567\nCall us"
    redacted, log = redactor.redact(text)
    assert "[PHONE]" in redacted
    assert "(555) 123-4567" not in redacted


def test_redacts_phone_without_parens():
    redactor = PHIRedactor()
    text = "Contact: 555-123-4567 for questions"
    redacted, log = redactor.redact(text)
    assert "[PHONE]" in redacted
    assert "555-123-4567" not in redacted


def test_redaction_log_has_positions():
    redactor = PHIRedactor()
    text = "Patient: Alice Brown\nMember ID: M12345"
    redacted, log = redactor.redact(text)
    assert len(log) >= 2
    for entry in log:
        assert "placeholder" in entry
        assert "pattern" in entry
        assert "position" in entry
        assert isinstance(entry["position"], int)


def test_no_phi_unchanged():
    redactor = PHIRedactor()
    text = "Your claim for MRI has been denied under CO-50."
    redacted, log = redactor.redact(text)
    assert redacted == text
    assert log == []


def test_multiple_phi_instances():
    redactor = PHIRedactor()
    text = (
        "Patient: John Smith\n"
        "DOB: 03/15/1955\n"
        "Member ID: ABC123456\n"
        "SSN: 123-45-6789\n"
        "Phone: (555) 987-6543\n"
        "Dear John Smith,\n"
        "Your claim has been denied."
    )
    redacted, log = redactor.redact(text)
    assert "John Smith" not in redacted
    assert "03/15/1955" not in redacted
    assert "ABC123456" not in redacted
    assert "123-45-6789" not in redacted
    assert "(555) 987-6543" not in redacted
    assert len(log) >= 5
