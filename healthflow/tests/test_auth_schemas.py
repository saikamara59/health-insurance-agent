import pytest
from healthflow.models.schemas import (
    BrokerCreate,
    BrokerResponse,
    LoginRequest,
    TokenResponse,
    ClientCreate,
    ClientResponse,
    ClientUpdate,
)


def test_broker_create_valid():
    b = BrokerCreate(
        email="broker@example.com",
        password="securepass123",
        full_name="Test Broker",
    )
    assert b.email == "broker@example.com"
    assert b.password == "securepass123"
    assert b.full_name == "Test Broker"


def test_broker_create_short_password():
    with pytest.raises(ValueError, match="8"):
        BrokerCreate(
            email="broker@example.com",
            password="short",
            full_name="Test Broker",
        )


def test_broker_create_invalid_email():
    with pytest.raises(ValueError):
        BrokerCreate(
            email="not-an-email",
            password="securepass123",
            full_name="Test Broker",
        )


def test_broker_response():
    b = BrokerResponse(
        id="550e8400-e29b-41d4-a716-446655440000",
        email="broker@example.com",
        full_name="Test Broker",
        role="broker",
        is_active=True,
        created_at="2026-04-09T12:00:00Z",
    )
    assert b.id == "550e8400-e29b-41d4-a716-446655440000"
    assert b.role == "broker"


def test_login_request():
    req = LoginRequest(email="broker@example.com", password="securepass123")
    assert req.email == "broker@example.com"
    assert req.password == "securepass123"


def test_token_response():
    t = TokenResponse(
        access_token="abc.def.ghi",
        refresh_token="jkl.mno.pqr",
        token_type="bearer",
    )
    assert t.token_type == "bearer"
    assert t.access_token == "abc.def.ghi"


def test_client_create_valid():
    c = ClientCreate(
        full_name="Jane Doe",
        zip_code="10001",
        age=45,
        income_level="medium",
        doctors=[{"name": "Dr. Chen", "npi": "1234567890"}],
        prescriptions=["Metformin"],
        procedures=["MRI"],
    )
    assert c.full_name == "Jane Doe"
    assert c.age == 45


def test_client_create_invalid_zip():
    with pytest.raises(ValueError, match="5 digits"):
        ClientCreate(
            full_name="Jane Doe",
            zip_code="123",
            age=45,
            income_level="medium",
            doctors=[],
            prescriptions=[],
            procedures=[],
        )


def test_client_create_age_too_young():
    with pytest.raises(ValueError):
        ClientCreate(
            full_name="Jane Doe",
            zip_code="10001",
            age=5,
            income_level="medium",
            doctors=[],
            prescriptions=[],
            procedures=[],
        )


def test_client_create_age_too_old():
    with pytest.raises(ValueError):
        ClientCreate(
            full_name="Jane Doe",
            zip_code="10001",
            age=200,
            income_level="medium",
            doctors=[],
            prescriptions=[],
            procedures=[],
        )


def test_client_create_invalid_income():
    with pytest.raises(ValueError, match="Income level"):
        ClientCreate(
            full_name="Jane Doe",
            zip_code="10001",
            age=45,
            income_level="mega-rich",
            doctors=[],
            prescriptions=[],
            procedures=[],
        )


def test_client_response():
    c = ClientResponse(
        id="550e8400-e29b-41d4-a716-446655440000",
        broker_id="660e8400-e29b-41d4-a716-446655440000",
        full_name="Jane Doe",
        zip_code="10001",
        age=45,
        income_level="medium",
        doctors=[{"name": "Dr. Chen", "npi": "1234567890"}],
        prescriptions=["Metformin"],
        procedures=["MRI"],
        created_at="2026-04-09T12:00:00Z",
        updated_at="2026-04-09T12:00:00Z",
    )
    assert c.id == "550e8400-e29b-41d4-a716-446655440000"
    assert c.broker_id == "660e8400-e29b-41d4-a716-446655440000"


def test_client_update_partial():
    u = ClientUpdate(age=50, zip_code="90210")
    assert u.age == 50
    assert u.zip_code == "90210"
    assert u.full_name is None
    assert u.income_level is None
    assert u.doctors is None


def test_client_update_empty():
    u = ClientUpdate()
    assert u.full_name is None
    assert u.age is None
