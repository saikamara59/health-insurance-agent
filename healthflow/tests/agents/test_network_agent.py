from unittest.mock import MagicMock, patch

from healthflow.agents.network_agent import NetworkAgent, SYSTEM_PROMPT
from healthflow.models.schemas import (
    FormularyResult,
    PlanSummary,
    ProviderInput,
    ProviderResult,
)


def _make_plan(name: str, plan_id: str, plan_type: str = "HMO") -> PlanSummary:
    return PlanSummary(
        plan_name=name,
        plan_id=plan_id,
        monthly_premium=0.0,
        annual_deductible=0.0,
        out_of_pocket_max=3000.0,
        star_rating=4.0,
        plan_type=plan_type,
        drug_coverage=True,
    )


def _make_provider_result(name: str, in_network: bool) -> ProviderResult:
    return ProviderResult(
        name=name,
        npi="1234567890",
        npi_verified=True,
        specialty="Internal Medicine",
        in_network=in_network,
        warning=None,
    )


def _make_formulary_result(drug: str, on_formulary: bool) -> FormularyResult:
    return FormularyResult(
        drug_name=drug,
        on_formulary=on_formulary,
        tier="Tier 1 - Generic" if on_formulary else None,
        copay=5.0 if on_formulary else None,
        prior_auth_required=False,
        warning=None if on_formulary else "Drug not on formulary.",
    )


@patch("healthflow.agents.network_agent.anthropic")
def test_agent_returns_sorted_results(mock_anthropic):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Plan B has better coverage.")]
    mock_client.messages.create.return_value = mock_response
    mock_anthropic.Anthropic.return_value = mock_client

    agent = NetworkAgent()
    plans = [
        _make_plan("Plan A", "FAKE-PLAN-999"),  # No providers in network
        _make_plan("Plan B", "H3312-034"),       # Has providers in network
    ]
    providers = [ProviderInput(name="Dr. Sarah Chen", npi="1234567890")]
    prescriptions = ["Metformin"]

    with patch.object(agent._provider_checker, "check") as mock_check:
        # Plan A: out of network. Plan B: in network.
        mock_check.side_effect = [
            _make_provider_result("Dr. Sarah Chen", False),  # Plan A
            _make_provider_result("Dr. Sarah Chen", True),   # Plan B
        ]
        with patch.object(agent._formulary_checker, "check") as mock_form:
            mock_form.side_effect = [
                _make_formulary_result("Metformin", True),  # Plan A
                _make_formulary_result("Metformin", True),  # Plan B
            ]
            results, recommendation = agent.verify(plans, providers, prescriptions)

    # Plan B should be first (more in-network providers)
    assert results[0].plan_id == "H3312-034"
    assert results[0].provider_results[0].in_network is True
    assert results[1].plan_id == "FAKE-PLAN-999"
    assert results[1].provider_results[0].in_network is False


@patch("healthflow.agents.network_agent.anthropic")
def test_agent_calls_claude_with_data(mock_anthropic):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Plan A is recommended.")]
    mock_client.messages.create.return_value = mock_response
    mock_anthropic.Anthropic.return_value = mock_client

    agent = NetworkAgent()
    plans = [_make_plan("Plan A", "H3312-034")]
    providers = [ProviderInput(name="Dr. Sarah Chen", npi="1234567890")]
    prescriptions = ["Metformin"]

    with patch.object(agent._provider_checker, "check", return_value=_make_provider_result("Dr. Sarah Chen", True)):
        with patch.object(agent._formulary_checker, "check", return_value=_make_formulary_result("Metformin", True)):
            results, recommendation = agent.verify(plans, providers, prescriptions)

    mock_client.messages.create.assert_called_once()
    call_kwargs = mock_client.messages.create.call_args
    assert call_kwargs.kwargs["system"] == SYSTEM_PROMPT
    assert recommendation == "Plan A is recommended."


def test_system_prompt_prohibits_medical_advice():
    assert "never give medical advice" in SYSTEM_PROMPT.lower() or "never" in SYSTEM_PROMPT.lower()
    assert "medical advice" in SYSTEM_PROMPT.lower()


@patch("healthflow.agents.network_agent.anthropic")
def test_plans_ranked_by_network_coverage(mock_anthropic):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Recommendation.")]
    mock_client.messages.create.return_value = mock_response
    mock_anthropic.Anthropic.return_value = mock_client

    agent = NetworkAgent()
    plans = [
        _make_plan("Plan A", "PLAN-A"),
        _make_plan("Plan B", "PLAN-B"),
        _make_plan("Plan C", "PLAN-C"),
    ]
    providers = [
        ProviderInput(name="Dr. One"),
        ProviderInput(name="Dr. Two"),
    ]
    prescriptions = ["Metformin", "Lisinopril"]

    with patch.object(agent._provider_checker, "check") as mock_prov:
        # Plan A: 0 in-network, Plan B: 2 in-network, Plan C: 1 in-network
        mock_prov.side_effect = [
            _make_provider_result("Dr. One", False),   # Plan A
            _make_provider_result("Dr. Two", False),   # Plan A
            _make_provider_result("Dr. One", True),    # Plan B
            _make_provider_result("Dr. Two", True),    # Plan B
            _make_provider_result("Dr. One", True),    # Plan C
            _make_provider_result("Dr. Two", False),   # Plan C
        ]
        with patch.object(agent._formulary_checker, "check") as mock_form:
            mock_form.return_value = _make_formulary_result("Metformin", True)
            results, _ = agent.verify(plans, providers, prescriptions)

    assert results[0].plan_name == "Plan B"  # 2 in-network
    assert results[1].plan_name == "Plan C"  # 1 in-network
    assert results[2].plan_name == "Plan A"  # 0 in-network
