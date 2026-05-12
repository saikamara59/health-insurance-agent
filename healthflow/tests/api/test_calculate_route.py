from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from healthflow.main import app

client = TestClient(app)


@patch("healthflow.api.routes.CostCalculatorAgent")
def test_calculate_with_zip_code(mock_agent_cls):
    mock_agent = MagicMock()
    mock_results = [MagicMock()]
    mock_results[0].model_dump.return_value = {
        "plan_name": "Test Plan",
        "plan_id": "H0001-001",
        "annual_premium": 0.0,
        "annual_care_cost": 240.0,
        "total_annual_cost": 240.0,
        "breakdown": {
            "premium_total": 0.0,
            "deductible_spent": 0.0,
            "doctor_visit_costs": 240.0,
            "prescription_costs": 0.0,
            "procedure_costs": 0.0,
            "total_before_oop_cap": 240.0,
            "oop_cap_applied": False,
            "final_care_cost": 240.0,
        },
        "prescription_details": [],
        "procedure_details": [],
    }
    mock_agent.calculate.return_value = (mock_results, "Test Plan is cheapest.")
    mock_agent_cls.return_value = mock_agent

    response = client.post(
        "/calculate",
        json={
            "zip_code": "10001",
            "income_level": "low",
            "usage": {
                "doctor_visits_per_year": 12,
                "prescriptions": [{"name": "Metformin", "fills_per_year": 12}],
                "procedures": [],
            },
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "plans" in data
    assert "recommendation" in data
    assert "disclaimer" in data
    assert "session_id" in data


def test_calculate_missing_both_session_and_zip():
    response = client.post(
        "/calculate",
        json={
            "usage": {"doctor_visits_per_year": 6},
        },
    )
    assert response.status_code == 422


def test_calculate_zip_without_income():
    response = client.post(
        "/calculate",
        json={
            "zip_code": "10001",
            "usage": {"doctor_visits_per_year": 6},
        },
    )
    assert response.status_code == 422


@patch("healthflow.api.routes.CostCalculatorAgent")
def test_calculate_with_session_id(mock_agent_cls):
    with patch("healthflow.api.routes.ComparisonAgent") as mock_compare_cls:
        mock_compare = MagicMock()
        mock_compare.recommend.return_value = "Plan A is best."
        mock_compare_cls.return_value = mock_compare

        compare_resp = client.post(
            "/compare",
            json={"zip_code": "10001", "age": 65, "income_level": "low"},
        )
        session_id = compare_resp.json()["session_id"]

    mock_agent = MagicMock()
    mock_agent.calculate.return_value = ([], "No plans.")
    mock_agent_cls.return_value = mock_agent

    response = client.post(
        "/calculate",
        json={
            "session_id": session_id,
            "usage": {"doctor_visits_per_year": 6},
        },
    )
    assert response.status_code == 200


@patch("healthflow.api.routes.CostCalculatorAgent")
def test_calculate_invalid_session_id(mock_agent_cls):
    response = client.post(
        "/calculate",
        json={
            "session_id": "nonexistent-session",
            "usage": {"doctor_visits_per_year": 6},
        },
    )
    assert response.status_code == 404


@patch("healthflow.api.routes.CostCalculatorAgent")
def test_calculate_response_has_disclaimer(mock_agent_cls):
    mock_agent = MagicMock()
    mock_agent.calculate.return_value = ([], "Recommendation.")
    mock_agent_cls.return_value = mock_agent

    response = client.post(
        "/calculate",
        json={
            "zip_code": "10001",
            "income_level": "low",
            "usage": {"doctor_visits_per_year": 0},
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "estimate" in data["disclaimer"].lower() or "not medical advice" in data["disclaimer"].lower()
