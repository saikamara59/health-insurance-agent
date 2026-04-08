import pytest
from healthflow.agents.harness import Harness, ValidationError


def test_validate_valid_input():
    harness = Harness()
    result = harness.validate_input("10001", 65, "low", ["Metformin"], ["MRI"])
    assert result["zip_code"] == "10001"
    assert result["age"] == 65
    assert result["income_level"] == "low"


def test_validate_invalid_zip_short():
    harness = Harness()
    with pytest.raises(ValidationError, match="5 digits"):
        harness.validate_input("123", 65, "low")


def test_validate_invalid_zip_non_numeric():
    harness = Harness()
    with pytest.raises(ValidationError, match="5 digits"):
        harness.validate_input("abcde", 65, "low")


def test_validate_invalid_age_too_low():
    harness = Harness()
    with pytest.raises(ValidationError, match="between 18 and 120"):
        harness.validate_input("10001", 15, "low")


def test_validate_invalid_age_too_high():
    harness = Harness()
    with pytest.raises(ValidationError, match="between 18 and 120"):
        harness.validate_input("10001", 200, "low")


def test_validate_invalid_income():
    harness = Harness()
    with pytest.raises(ValidationError, match="income"):
        harness.validate_input("10001", 65, "rich")


def test_validate_too_many_medications():
    harness = Harness()
    meds = [f"Drug{i}" for i in range(11)]
    with pytest.raises(ValidationError, match="10"):
        harness.validate_input("10001", 65, "low", medications=meds)


def test_validate_too_many_procedures():
    harness = Harness()
    procs = [f"Proc{i}" for i in range(11)]
    with pytest.raises(ValidationError, match="10"):
        harness.validate_input("10001", 65, "low", procedures=procs)


def test_validate_empty_medication_string():
    harness = Harness()
    with pytest.raises(ValidationError, match="empty"):
        harness.validate_input("10001", 65, "low", medications=[""])


def test_filter_output_clean_text():
    harness = Harness()
    text = "Plan A has a lower premium of $0/month and a 4.5 star rating."
    result = harness.filter_output(text)
    assert "Plan A has a lower premium" in result
    assert "not medical advice" in result.lower()


def test_filter_output_blocks_medication_advice():
    harness = Harness()
    text = "Based on your profile, you should take Metformin daily."
    result = harness.filter_output(text)
    assert "you should take" not in result.lower()
    assert "[redacted" in result.lower() or "not medical advice" in result.lower()


def test_filter_output_blocks_diagnostic_suggestion():
    harness = Harness()
    text = "Your symptoms suggest you might have diabetes."
    result = harness.filter_output(text)
    assert "symptoms suggest" not in result.lower()


def test_filter_output_blocks_treatment_advice():
    harness = Harness()
    text = "I recommend treatment with insulin for your condition."
    result = harness.filter_output(text)
    assert "i recommend treatment" not in result.lower()


def test_filter_output_always_has_disclaimer():
    harness = Harness()
    text = "Plan B is the best value option."
    result = harness.filter_output(text)
    assert "not medical advice" in result.lower()
