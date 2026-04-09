from healthflow.models.schemas import FormularyResult
from healthflow.tools.cost_estimator import CostEstimator

# Certain specialty drugs are excluded from specific plan formularies.
# Most drugs are on formulary for all plans; these are the exceptions.
PLAN_FORMULARY_EXCLUSIONS: dict[str, list[str]] = {
    "H1032-064": ["Humira", "Dupixent"],
    "H1032-070": ["Humira", "Ozempic"],
    "H2228-071": ["Dupixent", "Ozempic"],
    "H9622-005": ["Humira", "Dupixent", "Ozempic"],
    "H8245-002": ["Humira", "Ozempic"],
    "H7322-008": ["Dupixent"],
    "H6105-012": ["Humira", "Dupixent", "Ozempic"],
}


class FormularyChecker:
    def __init__(self) -> None:
        self._estimator = CostEstimator()

    def check(self, drug_name: str, plan_id: str, plan_type: str) -> FormularyResult:
        # Check if drug exists in our medication database via CostEstimator
        estimate = self._estimator.estimate(drug_name, "medication", plan_type)

        if estimate is None:
            return FormularyResult(
                drug_name=drug_name,
                on_formulary=False,
                tier=None,
                copay=None,
                prior_auth_required=False,
                warning="Drug not found in formulary database.",
            )

        # Check plan-specific exclusions
        excluded_drugs = PLAN_FORMULARY_EXCLUSIONS.get(plan_id, [])
        if estimate["item_name"] in excluded_drugs:
            return FormularyResult(
                drug_name=estimate["item_name"],
                on_formulary=False,
                tier=None,
                copay=None,
                prior_auth_required=False,
                warning="This drug is not on this plan's formulary.",
            )

        cost_details = estimate["cost_details"]
        return FormularyResult(
            drug_name=estimate["item_name"],
            on_formulary=True,
            tier=cost_details.get("formulary_tier"),
            copay=cost_details.get("copay"),
            prior_auth_required=cost_details.get("prior_auth_required", False),
            warning=None,
        )
