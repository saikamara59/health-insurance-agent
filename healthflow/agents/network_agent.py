import anthropic

from healthflow.agents.harness import CLAUDE_MODEL, extract_text
from healthflow.logs.audit import AuditLogger
from healthflow.models.schemas import (
    FormularyResult,
    PlanNetworkResult,
    PlanSummary,
    ProviderInput,
    ProviderResult,
)
from healthflow.tools.formulary_checker import FormularyChecker
from healthflow.tools.provider_cache import InMemoryProviderCache
from healthflow.tools.provider_checker import ProviderChecker

SYSTEM_PROMPT = (
    "You are a health insurance network verification assistant. "
    "Summarize which plans have the best network coverage for the user's "
    "doctors and prescriptions. Highlight any providers that are out-of-network "
    "or drugs not on formulary. Never give medical advice."
)


class NetworkAgent:
    def __init__(self) -> None:
        self.client = anthropic.Anthropic()
        self.audit = AuditLogger()
        self._cache = InMemoryProviderCache()
        self._provider_checker = ProviderChecker(cache=self._cache)
        self._formulary_checker = FormularyChecker()

    def verify(
        self,
        plans: list[PlanSummary],
        providers: list[ProviderInput],
        prescriptions: list[str],
    ) -> tuple[list[PlanNetworkResult], str]:
        plan_results: list[PlanNetworkResult] = []

        for plan in plans:
            provider_results: list[ProviderResult] = []
            for provider in providers:
                result = self._provider_checker.check(
                    provider.name, provider.npi, plan.plan_id
                )
                provider_results.append(result)
                self.audit.log("provider_checked", {
                    "provider": provider.name,
                    "plan_id": plan.plan_id,
                    "in_network": result.in_network,
                })

            formulary_results: list[FormularyResult] = []
            for drug_name in prescriptions:
                result = self._formulary_checker.check(
                    drug_name, plan.plan_id, plan.plan_type
                )
                formulary_results.append(result)
                self.audit.log("formulary_checked", {
                    "drug": drug_name,
                    "plan_id": plan.plan_id,
                    "on_formulary": result.on_formulary,
                })

            plan_results.append(PlanNetworkResult(
                plan_name=plan.plan_name,
                plan_id=plan.plan_id,
                provider_results=provider_results,
                formulary_results=formulary_results,
            ))

        # Sort: most in-network providers first, then most on-formulary drugs
        plan_results.sort(
            key=lambda r: (
                sum(1 for p in r.provider_results if p.in_network),
                sum(1 for f in r.formulary_results if f.on_formulary),
            ),
            reverse=True,
        )

        recommendation = self._get_recommendation(plan_results)

        return plan_results, recommendation

    def _build_prompt(self, plan_results: list[PlanNetworkResult]) -> str:
        lines = ["Network verification results:\n"]
        for pr in plan_results:
            in_net = sum(1 for p in pr.provider_results if p.in_network)
            total_prov = len(pr.provider_results)
            on_form = sum(1 for f in pr.formulary_results if f.on_formulary)
            total_drugs = len(pr.formulary_results)

            lines.append(f"Plan: {pr.plan_name} ({pr.plan_id})")
            lines.append(f"  Providers in-network: {in_net}/{total_prov}")
            for p in pr.provider_results:
                status = "IN-NETWORK" if p.in_network else "OUT-OF-NETWORK"
                lines.append(f"    - {p.name}: {status} (NPI verified: {p.npi_verified})")
                if p.warning:
                    lines.append(f"      Warning: {p.warning}")

            lines.append(f"  Drugs on formulary: {on_form}/{total_drugs}")
            for f in pr.formulary_results:
                status = "ON FORMULARY" if f.on_formulary else "NOT ON FORMULARY"
                tier_info = f" ({f.tier}, ${f.copay}/mo)" if f.tier and f.copay else ""
                lines.append(f"    - {f.drug_name}: {status}{tier_info}")
                if f.warning:
                    lines.append(f"      Warning: {f.warning}")

            lines.append("")

        lines.append(
            "Based on these results, which plan(s) offer the best network "
            "coverage? Summarize key findings concisely."
        )
        return "\n".join(lines)

    def _get_recommendation(self, plan_results: list[PlanNetworkResult]) -> str:
        user_prompt = self._build_prompt(plan_results)

        self.audit.log(
            "tool_called",
            {"tool": "claude_api", "model": CLAUDE_MODEL, "task": "network_verify"},
        )

        response = self.client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        return extract_text(response)
