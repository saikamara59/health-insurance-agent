from healthflow.models.schemas import PlanSummary


SCORING_WEIGHTS = {
    "low": {"premium": 0.5, "deductible": 0.3, "star_rating": 0.2},
    "medium": {"premium": 0.3, "deductible": 0.3, "star_rating": 0.4},
    "high": {"premium": 0.1, "deductible": 0.2, "star_rating": 0.7},
}

MAX_PREMIUM = 175.0
MAX_DEDUCTIBLE = 500.0
MAX_STAR = 5.0


class PlanParser:
    def parse_and_rank(
        self, raw_plans: list[dict], income_level: str
    ) -> list[PlanSummary]:
        weights = SCORING_WEIGHTS[income_level]
        scored: list[tuple[float, PlanSummary]] = []

        for raw in raw_plans:
            plan = PlanSummary(
                plan_name=raw["plan_name"],
                plan_id=raw["plan_id"],
                monthly_premium=raw["monthly_premium"],
                annual_deductible=raw["annual_deductible"],
                out_of_pocket_max=raw["out_of_pocket_max"],
                star_rating=raw["star_rating"],
                plan_type=raw["plan_type"],
                drug_coverage=raw["drug_coverage"],
                estimated_medication_costs=None,
                estimated_procedure_costs=None,
            )

            premium_score = 1.0 - (plan.monthly_premium / MAX_PREMIUM) if MAX_PREMIUM else 1.0
            deductible_score = 1.0 - (plan.annual_deductible / MAX_DEDUCTIBLE) if MAX_DEDUCTIBLE else 1.0
            star_score = plan.star_rating / MAX_STAR

            total_score = (
                weights["premium"] * premium_score
                + weights["deductible"] * deductible_score
                + weights["star_rating"] * star_score
            )
            scored.append((total_score, plan))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [plan for _, plan in scored[:5]]
