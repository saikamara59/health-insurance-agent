from healthflow.models.schemas import (
    PlanSummary,
    PrescriptionInput,
    ProcedureInput,
    UsageInput,
)
from healthflow.tools.cost_modeler import CostModeler


def _make_plan(
    plan_type: str = "HMO",
    monthly_premium: float = 0.0,
    annual_deductible: float = 0.0,
    out_of_pocket_max: float = 5000.0,
) -> PlanSummary:
    return PlanSummary(
        plan_name="Test Plan",
        plan_id="H0001-001",
        monthly_premium=monthly_premium,
        annual_deductible=annual_deductible,
        out_of_pocket_max=out_of_pocket_max,
        star_rating=4.0,
        plan_type=plan_type,
        drug_coverage=True,
    )


def test_zero_usage_only_premium():
    modeler = CostModeler()
    plan = _make_plan(monthly_premium=50.0)
    usage = UsageInput(doctor_visits_per_year=0)
    result = modeler.calculate(plan, usage)
    assert result.annual_premium == 600.0
    assert result.annual_care_cost == 0.0
    assert result.total_annual_cost == 600.0


def test_doctor_visits_hmo_copay():
    modeler = CostModeler()
    plan = _make_plan(plan_type="HMO")
    usage = UsageInput(doctor_visits_per_year=12)
    result = modeler.calculate(plan, usage)
    assert result.breakdown.doctor_visit_costs == 240.0


def test_doctor_visits_ppo_copay():
    modeler = CostModeler()
    plan = _make_plan(plan_type="PPO")
    usage = UsageInput(doctor_visits_per_year=12)
    result = modeler.calculate(plan, usage)
    assert result.breakdown.doctor_visit_costs == 480.0


def test_prescription_costs():
    modeler = CostModeler()
    plan = _make_plan(plan_type="HMO")
    usage = UsageInput(
        doctor_visits_per_year=0,
        prescriptions=[PrescriptionInput(name="Metformin", fills_per_year=12)],
    )
    result = modeler.calculate(plan, usage)
    assert result.breakdown.prescription_costs == 60.0
    assert len(result.prescription_details) == 1
    assert result.prescription_details[0].cost_per_fill == 5.0
    assert result.prescription_details[0].annual_cost == 60.0


def test_procedure_costs():
    modeler = CostModeler()
    plan = _make_plan(plan_type="HMO")
    usage = UsageInput(
        doctor_visits_per_year=0,
        procedures=[ProcedureInput(name="MRI", count=2)],
    )
    result = modeler.calculate(plan, usage)
    assert result.breakdown.procedure_costs == 300.0
    assert len(result.procedure_details) == 1
    assert result.procedure_details[0].cost_per_visit == 150.0
    assert result.procedure_details[0].annual_cost == 300.0


def test_oop_max_cap_applied():
    modeler = CostModeler()
    plan = _make_plan(plan_type="HMO", out_of_pocket_max=200.0)
    usage = UsageInput(
        doctor_visits_per_year=0,
        prescriptions=[PrescriptionInput(name="Humira", fills_per_year=12)],
    )
    result = modeler.calculate(plan, usage)
    assert result.breakdown.oop_cap_applied is True
    assert result.annual_care_cost == 200.0
    assert result.breakdown.final_care_cost == 200.0


def test_unknown_drug_default_copay():
    modeler = CostModeler()
    plan = _make_plan(plan_type="HMO")
    usage = UsageInput(
        doctor_visits_per_year=0,
        prescriptions=[PrescriptionInput(name="UnknownDrug999", fills_per_year=4)],
    )
    result = modeler.calculate(plan, usage)
    assert result.breakdown.prescription_costs == 100.0
    assert result.prescription_details[0].cost_per_fill == 25.0


def test_unknown_procedure_default_copay():
    modeler = CostModeler()
    plan = _make_plan(plan_type="HMO")
    usage = UsageInput(
        doctor_visits_per_year=0,
        procedures=[ProcedureInput(name="Brain Transplant", count=1)],
    )
    result = modeler.calculate(plan, usage)
    assert result.breakdown.procedure_costs == 100.0
    assert result.procedure_details[0].cost_per_visit == 100.0


def test_total_cost_includes_premium_and_care():
    modeler = CostModeler()
    plan = _make_plan(monthly_premium=25.0, plan_type="HMO")
    usage = UsageInput(
        doctor_visits_per_year=6,
        prescriptions=[PrescriptionInput(name="Metformin", fills_per_year=12)],
    )
    result = modeler.calculate(plan, usage)
    assert result.annual_premium == 300.0
    assert result.annual_care_cost == 180.0
    assert result.total_annual_cost == 480.0


def test_deductible_tracking():
    modeler = CostModeler()
    plan = _make_plan(annual_deductible=250.0, plan_type="HMO")
    usage = UsageInput(doctor_visits_per_year=6)
    result = modeler.calculate(plan, usage)
    assert result.breakdown.deductible_spent == 120.0
    assert result.breakdown.doctor_visit_costs == 120.0
