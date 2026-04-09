from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from healthflow.cli import cli


MOCK_VERIFY_RESPONSE = {
    "session_id": "test-session-123",
    "plans": [
        {
            "plan_name": "Test Plan HMO",
            "plan_id": "H3312-034",
            "provider_results": [
                {
                    "name": "Dr. Sarah Chen",
                    "npi": "1234567890",
                    "npi_verified": True,
                    "specialty": "Internal Medicine",
                    "in_network": True,
                    "warning": None,
                }
            ],
            "formulary_results": [
                {
                    "drug_name": "Metformin",
                    "on_formulary": True,
                    "tier": "Tier 1 - Generic",
                    "copay": 5.0,
                    "prior_auth_required": False,
                    "warning": None,
                }
            ],
        }
    ],
    "recommendation": "Test Plan HMO offers the best network coverage.",
    "disclaimer": "This is not medical advice.",
}


@patch("healthflow.cli.httpx.post")
def test_verify_with_zip_code(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = MOCK_VERIFY_RESPONSE
    mock_resp.raise_for_status.return_value = None
    mock_post.return_value = mock_resp

    runner = CliRunner()
    result = runner.invoke(cli, [
        "verify",
        "--zip-code", "10001",
        "--income", "low",
        "--providers", "Dr. Sarah Chen:1234567890",
        "--prescriptions", "Metformin",
    ])
    assert result.exit_code == 0
    assert "Dr. Sarah Chen" in result.output
    assert "Metformin" in result.output
    assert "IN-NETWORK" in result.output or "In-Network" in result.output or "in_network" in result.output.lower()


@patch("healthflow.cli.httpx.post")
def test_verify_with_session_id(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = MOCK_VERIFY_RESPONSE
    mock_resp.raise_for_status.return_value = None
    mock_post.return_value = mock_resp

    runner = CliRunner()
    result = runner.invoke(cli, [
        "verify",
        "--session-id", "test-session-123",
        "--providers", "Dr. Sarah Chen:1234567890",
        "--prescriptions", "Metformin",
    ])
    assert result.exit_code == 0
    assert "Session ID: test-session-123" in result.output


def test_verify_missing_session_and_zip():
    runner = CliRunner()
    result = runner.invoke(cli, [
        "verify",
        "--providers", "Dr. Sarah Chen:1234567890",
    ])
    assert result.exit_code != 0 or "Error" in result.output


@patch("healthflow.cli.httpx.post")
def test_verify_displays_formulary_info(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = MOCK_VERIFY_RESPONSE
    mock_resp.raise_for_status.return_value = None
    mock_post.return_value = mock_resp

    runner = CliRunner()
    result = runner.invoke(cli, [
        "verify",
        "--zip-code", "10001",
        "--income", "low",
        "--prescriptions", "Metformin",
    ])
    assert result.exit_code == 0
    assert "Metformin" in result.output


@patch("healthflow.cli.httpx.post")
def test_verify_displays_recommendation(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = MOCK_VERIFY_RESPONSE
    mock_resp.raise_for_status.return_value = None
    mock_post.return_value = mock_resp

    runner = CliRunner()
    result = runner.invoke(cli, [
        "verify",
        "--zip-code", "10001",
        "--income", "low",
        "--providers", "Dr. Sarah Chen:1234567890",
    ])
    assert result.exit_code == 0
    assert "RECOMMENDATION" in result.output
    assert "best network coverage" in result.output
