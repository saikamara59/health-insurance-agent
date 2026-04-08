from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from healthflow.main import app

client = TestClient(app)


@patch("healthflow.api.routes.ComparisonAgent")
def test_full_compare_pipeline(mock_agent_cls):
    """End-to-end test: request → validation → fetch → parse → estimate → agent → response"""
    mock_agent = MagicMock()
    mock_agent.recommend.return_value = (
        "Based on your profile as a 65-year-old with low income, "
        "Plan A offers the best value with a $0 monthly premium "
        "and strong 4.5 star rating. Your Metformin costs only $5/month."
    )
    mock_agent_cls.return_value = mock_agent

    response = client.post(
        "/compare",
        json={
            "zip_code": "10001",
            "age": 65,
            "income_level": "low",
            "medications": ["Metformin", "Lisinopril"],
            "procedures": ["Annual physical", "Blood work"],
        },
    )

    assert response.status_code == 200
    data = response.json()

    assert "session_id" in data
    assert data["zip_code"] == "10001"
    assert len(data["plans"]) <= 5
    assert len(data["plans"]) >= 1
    assert "recommendation" in data
    assert "disclaimer" in data

    plan = data["plans"][0]
    assert "plan_name" in plan
    assert "monthly_premium" in plan
    assert "star_rating" in plan

    assert plan.get("estimated_medication_costs") is not None
    assert "Metformin" in plan["estimated_medication_costs"]

    assert "not medical advice" in data["disclaimer"].lower()


@patch("healthflow.api.routes.ComparisonAgent")
def test_compare_filters_medical_advice(mock_agent_cls):
    """Verify the harness filters medical advice from Claude's response."""
    mock_agent = MagicMock()
    mock_agent.recommend.return_value = (
        "Plan A is great. Also, you should take Metformin twice daily."
    )
    mock_agent_cls.return_value = mock_agent

    response = client.post(
        "/compare",
        json={"zip_code": "10001", "age": 65, "income_level": "low"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "you should take" not in data["recommendation"].lower()


@patch("healthflow.api.routes.ComparisonAgent")
def test_compare_no_meds_or_procs(mock_agent_cls):
    """Verify compare works without medications or procedures."""
    mock_agent = MagicMock()
    mock_agent.recommend.return_value = "Plan A is the best value."
    mock_agent_cls.return_value = mock_agent

    response = client.post(
        "/compare",
        json={"zip_code": "90210", "age": 70, "income_level": "high"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["plans"]) <= 5


def test_estimate_medication_integration():
    """End-to-end estimate for a known medication."""
    response = client.post(
        "/estimate",
        json={
            "plan_id": "H3312-034",
            "item_name": "Ozempic",
            "item_type": "medication",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["estimated_cost"] > 0
    assert data["cost_details"]["formulary_tier"] == "Tier 4 - Specialty"
    assert data["cost_details"]["prior_auth_required"] is True


def test_estimate_procedure_integration():
    """End-to-end estimate for a known procedure."""
    response = client.post(
        "/estimate",
        json={
            "plan_id": "H3312-034",
            "item_name": "ER visit",
            "item_type": "procedure",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["estimated_cost"] > 0
