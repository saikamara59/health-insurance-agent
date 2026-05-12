from unittest.mock import MagicMock, patch
from healthflow.agents.comparison_agent import ComparisonAgent
from healthflow.models.schemas import PlanSummary


SAMPLE_PLANS = [
    PlanSummary(
        plan_name="Aetna Medicare Eagle Plus (HMO)",
        plan_id="H3312-034",
        monthly_premium=0.00,
        annual_deductible=250.00,
        out_of_pocket_max=4500.00,
        star_rating=4.5,
        plan_type="HMO",
        drug_coverage=True,
        estimated_medication_costs={"Metformin": 5.0},
        estimated_procedure_costs={"MRI": 150.0},
    ),
    PlanSummary(
        plan_name="UHC Medicare Advantage Choice (PPO)",
        plan_id="H2228-050",
        monthly_premium=25.00,
        annual_deductible=150.00,
        out_of_pocket_max=5500.00,
        star_rating=4.0,
        plan_type="PPO",
        drug_coverage=True,
        estimated_medication_costs={"Metformin": 10.0},
        estimated_procedure_costs={"MRI": 250.0},
    ),
]


@patch("healthflow.agents.comparison_agent.anthropic")
def test_agent_returns_recommendation(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Plan A is the best choice for your budget.")]
    mock_client.messages.create.return_value = mock_response

    agent = ComparisonAgent()
    result = agent.recommend(
        plans=SAMPLE_PLANS,
        age=65,
        income_level="low",
        medications=["Metformin"],
        procedures=["MRI"],
    )

    assert "Plan A" in result
    mock_client.messages.create.assert_called_once()


@patch("healthflow.agents.comparison_agent.anthropic")
def test_agent_sends_system_prompt(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Recommendation text")]
    mock_client.messages.create.return_value = mock_response

    agent = ComparisonAgent()
    agent.recommend(plans=SAMPLE_PLANS, age=65, income_level="low")

    call_kwargs = mock_client.messages.create.call_args
    assert "system" in call_kwargs.kwargs
    assert "medical advice" in call_kwargs.kwargs["system"].lower()


@patch("healthflow.agents.comparison_agent.anthropic")
def test_agent_includes_plan_data_in_prompt(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Recommendation")]
    mock_client.messages.create.return_value = mock_response

    agent = ComparisonAgent()
    agent.recommend(plans=SAMPLE_PLANS, age=65, income_level="low")

    call_kwargs = mock_client.messages.create.call_args
    user_msg = call_kwargs.kwargs["messages"][0]["content"]
    assert "Aetna" in user_msg
    assert "H3312-034" in user_msg


@patch("healthflow.agents.comparison_agent.anthropic")
def test_agent_includes_cost_data_when_provided(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Recommendation")]
    mock_client.messages.create.return_value = mock_response

    agent = ComparisonAgent()
    agent.recommend(
        plans=SAMPLE_PLANS,
        age=65,
        income_level="low",
        medications=["Metformin"],
        procedures=["MRI"],
    )

    call_kwargs = mock_client.messages.create.call_args
    user_msg = call_kwargs.kwargs["messages"][0]["content"]
    assert "Metformin" in user_msg
    assert "MRI" in user_msg


@patch("healthflow.agents.comparison_agent.anthropic")
def test_agent_stubs_anthropic_call_in_test_mode(mock_anthropic, monkeypatch):
    """In HEALTHFLOW_TEST_MODE, recommend() must NOT call the Anthropic API.

    The e2e docker stack runs with a fake API key; without a stub path,
    /compare returns 500 because the API rejects the key.
    """
    monkeypatch.setenv("HEALTHFLOW_TEST_MODE", "1")
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client

    agent = ComparisonAgent()
    result = agent.recommend(
        plans=SAMPLE_PLANS,
        age=65,
        income_level="low",
    )

    assert isinstance(result, str) and result
    mock_client.messages.create.assert_not_called()
