import pytest
from healthflow.models.schemas import (
    FormularyResult,
    PlanNetworkResult,
    ProviderInput,
    ProviderResult,
    VerifyRequest,
    VerifyResponse,
)


def test_provider_input_with_npi():
    p = ProviderInput(name="Dr. Sarah Chen", npi="1234567890")
    assert p.name == "Dr. Sarah Chen"
    assert p.npi == "1234567890"


def test_provider_input_without_npi():
    p = ProviderInput(name="Dr. Sarah Chen")
    assert p.npi is None


def test_verify_request_with_session():
    req = VerifyRequest(
        session_id="abc-123",
        providers=[ProviderInput(name="Dr. Sarah Chen", npi="1234567890")],
        prescriptions=["Metformin"],
    )
    assert req.session_id == "abc-123"
    assert req.zip_code is None


def test_verify_request_with_zip():
    req = VerifyRequest(
        zip_code="10001",
        income_level="low",
        providers=[ProviderInput(name="Dr. Sarah Chen")],
        prescriptions=["Metformin"],
    )
    assert req.zip_code == "10001"
    assert req.session_id is None


def test_verify_request_missing_both():
    with pytest.raises(ValueError, match="session_id.*zip_code"):
        VerifyRequest(
            providers=[ProviderInput(name="Dr. Sarah Chen")],
            prescriptions=["Metformin"],
        )


def test_verify_request_zip_without_income():
    with pytest.raises(ValueError, match="income_level"):
        VerifyRequest(
            zip_code="10001",
            providers=[ProviderInput(name="Dr. Sarah Chen")],
            prescriptions=["Metformin"],
        )


def test_verify_request_invalid_zip():
    with pytest.raises(ValueError, match="5 digits"):
        VerifyRequest(
            zip_code="123",
            income_level="low",
            providers=[],
            prescriptions=[],
        )


def test_verify_request_empty_providers_and_prescriptions():
    req = VerifyRequest(
        zip_code="10001",
        income_level="low",
    )
    assert req.providers == []
    assert req.prescriptions == []


def test_provider_result_in_network():
    r = ProviderResult(
        name="Dr. Sarah Chen",
        npi="1234567890",
        npi_verified=True,
        specialty="Internal Medicine",
        in_network=True,
        warning=None,
    )
    assert r.in_network is True
    assert r.npi_verified is True
    assert r.warning is None


def test_provider_result_not_found():
    r = ProviderResult(
        name="Dr. Unknown",
        npi=None,
        npi_verified=False,
        specialty=None,
        in_network=False,
        warning="Provider not found in NPI registry. Verify name and credentials.",
    )
    assert r.npi_verified is False
    assert r.warning is not None


def test_formulary_result_on_formulary():
    r = FormularyResult(
        drug_name="Metformin",
        on_formulary=True,
        tier="Tier 1 - Generic",
        copay=5.0,
        prior_auth_required=False,
        warning=None,
    )
    assert r.on_formulary is True
    assert r.copay == 5.0


def test_formulary_result_excluded():
    r = FormularyResult(
        drug_name="Humira",
        on_formulary=False,
        tier=None,
        copay=None,
        prior_auth_required=False,
        warning="This drug is not on this plan's formulary.",
    )
    assert r.on_formulary is False
    assert r.warning is not None


def test_plan_network_result():
    r = PlanNetworkResult(
        plan_name="Test Plan",
        plan_id="H3312-034",
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
    assert len(r.provider_results) == 1
    assert len(r.formulary_results) == 1


def test_verify_response():
    r = VerifyResponse(
        session_id="abc-123",
        plans=[],
        recommendation="Plan A has the best network coverage.",
        disclaimer="Network status is based on publicly available data.",
    )
    assert r.session_id == "abc-123"
    assert r.recommendation != ""
    assert r.disclaimer != ""
