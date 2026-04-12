import pytest
from healthflow.models.schemas import (
    CompareRequest,
    CostDetails,
    EstimateRequest,
    PlanSummary,
)


def test_compare_request_valid():
    req = CompareRequest(zip_code="10001", age=65, income_level="low")
    assert req.zip_code == "10001"
    assert req.age == 65
    assert req.income_level == "low"
    assert req.medications == []
    assert req.procedures == []


def test_compare_request_with_meds_and_procedures():
    req = CompareRequest(
        zip_code="90210",
        age=70,
        income_level="high",
        medications=["Metformin", "Lisinopril"],
        procedures=["Annual physical"],
    )
    assert len(req.medications) == 2
    assert len(req.procedures) == 1


def test_compare_request_invalid_zip():
    with pytest.raises(ValueError):
        CompareRequest(zip_code="123", age=65, income_level="low")


def test_compare_request_invalid_zip_non_numeric():
    with pytest.raises(ValueError):
        CompareRequest(zip_code="abcde", age=65, income_level="low")


def test_compare_request_invalid_age_too_low():
    with pytest.raises(ValueError):
        CompareRequest(zip_code="10001", age=17, income_level="low")


def test_compare_request_invalid_age_too_high():
    with pytest.raises(ValueError):
        CompareRequest(zip_code="10001", age=121, income_level="low")


def test_compare_request_invalid_income():
    with pytest.raises(ValueError):
        CompareRequest(zip_code="10001", age=65, income_level="rich")


def test_estimate_request_valid():
    req = EstimateRequest(
        plan_id="H1234-001", item_name="Metformin", item_type="medication"
    )
    assert req.plan_id == "H1234-001"
    assert req.item_type == "medication"


def test_estimate_request_invalid_type():
    with pytest.raises(ValueError):
        EstimateRequest(
            plan_id="H1234-001", item_name="Metformin", item_type="vitamin"
        )


def test_plan_summary_model():
    plan = PlanSummary(
        plan_name="Aetna Medicare Eagle Plus (HMO)",
        plan_id="H1234-001",
        monthly_premium=0.0,
        annual_deductible=250.0,
        out_of_pocket_max=4500.0,
        star_rating=4.5,
        plan_type="HMO",
        drug_coverage=True,
        estimated_medication_costs=None,
        estimated_procedure_costs=None,
    )
    assert plan.star_rating == 4.5
    assert plan.drug_coverage is True


def test_cost_details_model():
    details = CostDetails(
        formulary_tier="Tier 1 - Generic",
        copay=10.0,
        coinsurance_pct=None,
        prior_auth_required=False,
        quantity_limit="90-day supply",
    )
    assert details.copay == 10.0
    assert details.prior_auth_required is False
