from unittest.mock import MagicMock, patch
from healthflow.agents.cost_calculator_agent import CostCalculatorAgent
from healthflow.models.schemas import (
    PlanSummary,
    PrescriptionInput,
    UsageInput,
)


SAMPLE_PLANS = [
    PlanSummary(
        plan_name="Expensive Plan",
        plan_id="H0001-001",
        monthly_premium=100.0,
        annual_deductible=500.0,
        out_of_pocket_max=8000.0,
        star_rating=3.0,
        plan_type="PPO",
        drug_coverage=True,
    ),
    PlanSummary(
        plan_name="Cheap Plan",
        plan_id="H0001-002",
        monthly_premium=0.0,
        annual_deductible=0.0,
        out_of_pocket_max=4000.0,
        star_rating=4.5,
        plan_type="HMO",
        drug_coverage=True,
    ),
]

SAMPLE_USAGE = UsageInput(
    doctor_visits_per_year=12,
    prescriptions=[PrescriptionInput(name="Metformin", fills_per_year=12)],
)


@patch("healthflow.agents.cost_calculator_agent.anthropic")
def test_agent_returns_sorted_results(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Cheap Plan saves you money.")]
    mock_client.messages.create.return_value = mock_response

    agent = CostCalculatorAgent()
    results, recommendation = agent.calculate(SAMPLE_PLANS, SAMPLE_USAGE)

    assert results[0].plan_id == "H0001-002"
    assert results[0].total_annual_cost < results[1].total_annual_cost


@patch("healthflow.agents.cost_calculator_agent.anthropic")
def test_agent_calls_claude(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Recommendation text.")]
    mock_client.messages.create.return_value = mock_response

    agent = CostCalculatorAgent()
    _, recommendation = agent.calculate(SAMPLE_PLANS, SAMPLE_USAGE)

    mock_client.messages.create.assert_called_once()
    assert recommendation == "Recommendation text."


@patch("healthflow.agents.cost_calculator_agent.anthropic")
def test_agent_system_prompt_no_medical_advice(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Text")]
    mock_client.messages.create.return_value = mock_response

    agent = CostCalculatorAgent()
    agent.calculate(SAMPLE_PLANS, SAMPLE_USAGE)

    call_kwargs = mock_client.messages.create.call_args
    system = call_kwargs.kwargs["system"]
    assert "medical advice" in system.lower()


@patch("healthflow.agents.cost_calculator_agent.anthropic")
def test_agent_prompt_includes_cost_data(mock_anthropic):
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Text")]
    mock_client.messages.create.return_value = mock_response

    agent = CostCalculatorAgent()
    agent.calculate(SAMPLE_PLANS, SAMPLE_USAGE)

    call_kwargs = mock_client.messages.create.call_args
    user_msg = call_kwargs.kwargs["messages"][0]["content"]
    assert "Cheap Plan" in user_msg
    assert "Expensive Plan" in user_msg
    assert "Metformin" in user_msg
