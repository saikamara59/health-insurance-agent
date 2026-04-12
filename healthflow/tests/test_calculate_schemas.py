import pytest
from healthflow.models.schemas import (
    CalculateRequest,
    CostBreakdown,
    PlanCostResult,
    PrescriptionDetail,
    PrescriptionInput,
    ProcedureDetail,
    ProcedureInput,
    UsageInput,
)


def test_usage_input_valid():
    usage = UsageInput(
        doctor_visits_per_year=12,
        prescriptions=[PrescriptionInput(name="Metformin", fills_per_year=12)],
        procedures=[ProcedureInput(name="MRI", count=2)],
    )
    assert usage.doctor_visits_per_year == 12
    assert len(usage.prescriptions) == 1
    assert len(usage.procedures) == 1


def test_usage_input_zero_visits():
    usage = UsageInput(doctor_visits_per_year=0)
    assert usage.doctor_visits_per_year == 0


def test_usage_input_visits_too_high():
    with pytest.raises(ValueError):
        UsageInput(doctor_visits_per_year=366)


def test_prescription_input_fills_too_low():
    with pytest.raises(ValueError):
        PrescriptionInput(name="Metformin", fills_per_year=0)


def test_procedure_input_count_too_high():
    with pytest.raises(ValueError):
        ProcedureInput(name="MRI", count=366)


def test_calculate_request_with_session():
    req = CalculateRequest(
        session_id="abc-123",
        usage=UsageInput(doctor_visits_per_year=6),
    )
    assert req.session_id == "abc-123"
    assert req.zip_code is None


def test_calculate_request_with_zip():
    req = CalculateRequest(
        zip_code="10001",
        income_level="low",
        usage=UsageInput(doctor_visits_per_year=6),
    )
    assert req.zip_code == "10001"
    assert req.session_id is None


def test_calculate_request_missing_both():
    with pytest.raises(ValueError, match="session_id.*zip_code"):
        CalculateRequest(
            usage=UsageInput(doctor_visits_per_year=6),
        )


def test_calculate_request_zip_without_income():
    with pytest.raises(ValueError, match="income_level"):
        CalculateRequest(
            zip_code="10001",
            usage=UsageInput(doctor_visits_per_year=6),
        )


def test_cost_breakdown_model():
    breakdown = CostBreakdown(
        premium_total=0.0,
        deductible_spent=0.0,
        doctor_visit_costs=240.0,
        prescription_costs=60.0,
        procedure_costs=300.0,
        total_before_oop_cap=600.0,
        oop_cap_applied=False,
        final_care_cost=600.0,
    )
    assert breakdown.final_care_cost == 600.0
    assert breakdown.oop_cap_applied is False


def test_plan_cost_result_model():
    result = PlanCostResult(
        plan_name="Test Plan",
        plan_id="H0001-001",
        annual_premium=0.0,
        annual_care_cost=600.0,
        total_annual_cost=600.0,
        breakdown=CostBreakdown(
            premium_total=0.0,
            deductible_spent=0.0,
            doctor_visit_costs=240.0,
            prescription_costs=60.0,
            procedure_costs=300.0,
            total_before_oop_cap=600.0,
            oop_cap_applied=False,
            final_care_cost=600.0,
        ),
        prescription_details=[
            PrescriptionDetail(name="Metformin", cost_per_fill=5.0, annual_cost=60.0)
        ],
        procedure_details=[
            ProcedureDetail(name="MRI", cost_per_visit=150.0, annual_cost=300.0)
        ],
    )
    assert result.total_annual_cost == 600.0
