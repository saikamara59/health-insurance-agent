from healthflow.models.schemas import (
    CostBreakdown,
    PlanCostResult,
    PlanSummary,
    PrescriptionDetail,
    ProcedureDetail,
    UsageInput,
)
from healthflow.tools.cost_estimator import CostEstimator

DOCTOR_VISIT_COPAY = {"HMO": 20.0, "PPO": 40.0}
DEFAULT_DRUG_COPAY = 25.0
DEFAULT_PROCEDURE_COPAY = 100.0


class CostModeler:
    def __init__(self) -> None:
        self.estimator = CostEstimator()

    def calculate(self, plan: PlanSummary, usage: UsageInput) -> PlanCostResult:
        annual_premium = plan.monthly_premium * 12

        visit_copay = DOCTOR_VISIT_COPAY.get(plan.plan_type, 40.0)
        doctor_visit_costs = visit_copay * usage.doctor_visits_per_year

        prescription_details: list[PrescriptionDetail] = []
        prescription_costs = 0.0
        for rx in usage.prescriptions:
            estimate = self.estimator.estimate(rx.name, "medication", plan.plan_type)
            if estimate is not None:
                cost_per_fill = estimate["estimated_cost"]
            else:
                cost_per_fill = DEFAULT_DRUG_COPAY
            annual_cost = cost_per_fill * rx.fills_per_year
            prescription_costs += annual_cost
            prescription_details.append(
                PrescriptionDetail(
                    name=rx.name,
                    cost_per_fill=cost_per_fill,
                    annual_cost=annual_cost,
                )
            )

        procedure_details: list[ProcedureDetail] = []
        procedure_costs = 0.0
        for proc in usage.procedures:
            estimate = self.estimator.estimate(proc.name, "procedure", plan.plan_type)
            if estimate is not None:
                cost_per_visit = estimate["estimated_cost"]
            else:
                cost_per_visit = DEFAULT_PROCEDURE_COPAY
            annual_cost = cost_per_visit * proc.count
            procedure_costs += annual_cost
            procedure_details.append(
                ProcedureDetail(
                    name=proc.name,
                    cost_per_visit=cost_per_visit,
                    annual_cost=annual_cost,
                )
            )

        total_care = doctor_visit_costs + prescription_costs + procedure_costs
        deductible_spent = min(plan.annual_deductible, total_care)
        oop_cap_applied = total_care > plan.out_of_pocket_max
        final_care_cost = min(total_care, plan.out_of_pocket_max)

        return PlanCostResult(
            plan_name=plan.plan_name,
            plan_id=plan.plan_id,
            annual_premium=annual_premium,
            annual_care_cost=final_care_cost,
            total_annual_cost=annual_premium + final_care_cost,
            breakdown=CostBreakdown(
                premium_total=annual_premium,
                deductible_spent=deductible_spent,
                doctor_visit_costs=doctor_visit_costs,
                prescription_costs=prescription_costs,
                procedure_costs=procedure_costs,
                total_before_oop_cap=total_care,
                oop_cap_applied=oop_cap_applied,
                final_care_cost=final_care_cost,
            ),
            prescription_details=prescription_details,
            procedure_details=procedure_details,
        )
