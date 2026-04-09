from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from healthflow.main import app
from healthflow.models.schemas import (
    FormularyResult,
    PlanNetworkResult,
    ProviderResult,
)

client = TestClient(app)


def _make_plan_network_result(plan_name: str, plan_id: str) -> PlanNetworkResult:
    return PlanNetworkResult(
        plan_name=plan_name,
        plan_id=plan_id,
        provider_results=[
            ProviderResult(
                name="Dr. Sarah Chen",
                npi="1234567890",
                npi_verified=True,
                specialty="Internal Medicine",
                in_network=True,
                warning=None,
            )
        ],
        formulary_results=[
            FormularyResult(
                drug_name="Metformin",
                on_formulary=True,
                tier="Tier 1 - Generic",
                copay=5.0,
                prior_auth_required=False,
                warning=None,
            )
        ],
    )


@patch("healthflow.api.routes.NetworkAgent")
def test_verify_with_zip_code(mock_agent_cls):
    mock_agent = MagicMock()
    mock_results = [_make_plan_network_result("Test Plan", "H3312-034")]
    mock_agent.verify.return_value = (mock_results, "Test Plan has best coverage.")
    mock_agent_cls.return_value = mock_agent

    response = client.post(
        "/verify",
        json={
            "zip_code": "10001",
            "income_level": "low",
            "providers": [{"name": "Dr. Sarah Chen", "npi": "1234567890"}],
            "prescriptions": ["Metformin"],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "plans" in data
    assert "recommendation" in data
    assert "disclaimer" in data
    assert "session_id" in data
    assert len(data["plans"]) == 1
    assert data["plans"][0]["plan_name"] == "Test Plan"


@patch("healthflow.api.routes.NetworkAgent")
def test_verify_with_session_id(mock_agent_cls):
    # First create a session via /compare
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
    mock_results = [_make_plan_network_result("Test Plan", "H3312-034")]
    mock_agent.verify.return_value = (mock_results, "Coverage looks good.")
    mock_agent_cls.return_value = mock_agent

    response = client.post(
        "/verify",
        json={
            "session_id": session_id,
            "providers": [{"name": "Dr. Sarah Chen"}],
            "prescriptions": ["Metformin"],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == session_id


def test_verify_missing_both_session_and_zip():
    response = client.post(
        "/verify",
        json={
            "providers": [{"name": "Dr. Sarah Chen"}],
            "prescriptions": ["Metformin"],
        },
    )
    assert response.status_code == 422


@patch("healthflow.api.routes.NetworkAgent")
def test_verify_response_has_disclaimer(mock_agent_cls):
    mock_agent = MagicMock()
    mock_agent.verify.return_value = ([], "No results.")
    mock_agent_cls.return_value = mock_agent

    response = client.post(
        "/verify",
        json={
            "zip_code": "10001",
            "income_level": "low",
            "providers": [],
            "prescriptions": [],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "not medical advice" in data["disclaimer"].lower()


@patch("healthflow.api.routes.NetworkAgent")
def test_verify_response_has_provider_and_formulary_results(mock_agent_cls):
    mock_agent = MagicMock()
    mock_results = [_make_plan_network_result("Test Plan", "H3312-034")]
    mock_agent.verify.return_value = (mock_results, "Good coverage.")
    mock_agent_cls.return_value = mock_agent

    response = client.post(
        "/verify",
        json={
            "zip_code": "10001",
            "income_level": "low",
            "providers": [{"name": "Dr. Sarah Chen", "npi": "1234567890"}],
            "prescriptions": ["Metformin"],
        },
    )
    assert response.status_code == 200
    data = response.json()
    plan = data["plans"][0]
    assert len(plan["provider_results"]) == 1
    assert plan["provider_results"][0]["npi_verified"] is True
    assert len(plan["formulary_results"]) == 1
    assert plan["formulary_results"][0]["on_formulary"] is True


@patch("healthflow.api.routes.NetworkAgent")
def test_verify_invalid_session_id(mock_agent_cls):
    response = client.post(
        "/verify",
        json={
            "session_id": "nonexistent-session",
            "providers": [{"name": "Dr. Sarah Chen"}],
            "prescriptions": ["Metformin"],
        },
    )
    assert response.status_code == 404
