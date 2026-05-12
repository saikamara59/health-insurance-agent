from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from healthflow.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_get_plans_known_zip():
    response = client.get("/plans/10001")
    assert response.status_code == 200
    data = response.json()
    assert "plans" in data
    assert len(data["plans"]) >= 5


def test_get_plans_invalid_zip():
    response = client.get("/plans/123")
    assert response.status_code == 422


@patch("healthflow.api.routes.ComparisonAgent")
def test_compare_valid_request(mock_agent_cls):
    mock_agent = MagicMock()
    mock_agent.recommend.return_value = "Plan A is the best value."
    mock_agent_cls.return_value = mock_agent

    response = client.post(
        "/compare",
        json={
            "zip_code": "10001",
            "age": 65,
            "income_level": "low",
            "medications": ["Metformin"],
            "procedures": ["MRI"],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "plans" in data
    assert "recommendation" in data
    assert "disclaimer" in data
    assert "session_id" in data
    assert len(data["plans"]) <= 5


@patch("healthflow.api.routes.ComparisonAgent")
def test_compare_invalid_zip(mock_agent_cls):
    response = client.post(
        "/compare",
        json={"zip_code": "abc", "age": 65, "income_level": "low"},
    )
    assert response.status_code == 422


@patch("healthflow.api.routes.ComparisonAgent")
def test_compare_invalid_age(mock_agent_cls):
    response = client.post(
        "/compare",
        json={"zip_code": "10001", "age": 10, "income_level": "low"},
    )
    assert response.status_code == 422


def test_estimate_known_medication():
    response = client.post(
        "/estimate",
        json={
            "plan_id": "H3312-034",
            "item_name": "Metformin",
            "item_type": "medication",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "estimated_cost" in data
    assert "cost_details" in data


def test_estimate_unknown_item():
    response = client.post(
        "/estimate",
        json={
            "plan_id": "H3312-034",
            "item_name": "FakeDrug999",
            "item_type": "medication",
        },
    )
    assert response.status_code == 404


def test_estimate_invalid_type():
    response = client.post(
        "/estimate",
        json={
            "plan_id": "H3312-034",
            "item_name": "Metformin",
            "item_type": "vitamin",
        },
    )
    assert response.status_code == 422
