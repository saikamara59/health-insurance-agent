from unittest.mock import MagicMock, patch

from healthflow.tools.provider_checker import ProviderChecker
from healthflow.tools.provider_cache import InMemoryProviderCache


def test_npi_verified_and_in_network():
    cache = InMemoryProviderCache(ttl_seconds=60)
    checker = ProviderChecker(cache=cache)

    mock_npi_result = {
        "npi": "1234567890",
        "name": "SARAH CHEN",
        "specialty": "Internal Medicine",
        "credential": "MD",
    }

    with patch.object(checker._npi_client, "lookup_by_npi", return_value=mock_npi_result):
        result = checker.check("Dr. Sarah Chen", "1234567890", "H3312-034")

    assert result.npi_verified is True
    assert result.in_network is True
    assert result.specialty == "Internal Medicine"
    assert result.npi == "1234567890"
    assert result.warning is None


def test_npi_verified_but_out_of_network():
    cache = InMemoryProviderCache(ttl_seconds=60)
    checker = ProviderChecker(cache=cache)

    mock_npi_result = {
        "npi": "1234567890",
        "name": "SARAH CHEN",
        "specialty": "Internal Medicine",
        "credential": "MD",
    }

    with patch.object(checker._npi_client, "lookup_by_npi", return_value=mock_npi_result):
        result = checker.check("Dr. Sarah Chen", "1234567890", "FAKE-PLAN-999")

    assert result.npi_verified is True
    assert result.in_network is False
    assert result.warning is None


def test_npi_not_found_warning():
    cache = InMemoryProviderCache(ttl_seconds=60)
    checker = ProviderChecker(cache=cache)

    with patch.object(checker._npi_client, "lookup_by_npi", return_value=None):
        result = checker.check("Dr. Unknown Person", "0000000000", "H3312-034")

    assert result.npi_verified is False
    assert result.in_network is False
    assert result.warning == "Provider not found in NPI registry. Verify name and credentials."


def test_no_npi_name_search_found():
    cache = InMemoryProviderCache(ttl_seconds=60)
    checker = ProviderChecker(cache=cache)

    mock_search_result = [
        {
            "npi": "1234567890",
            "name": "SARAH CHEN",
            "specialty": "Internal Medicine",
            "credential": "MD",
        }
    ]

    with patch.object(checker._npi_client, "search_by_name", return_value=mock_search_result):
        result = checker.check("Dr. Sarah Chen", None, "H3312-034")

    assert result.npi_verified is True
    assert result.npi == "1234567890"
    assert result.specialty == "Internal Medicine"
    assert result.in_network is True


def test_no_npi_name_search_not_found():
    cache = InMemoryProviderCache(ttl_seconds=60)
    checker = ProviderChecker(cache=cache)

    with patch.object(checker._npi_client, "search_by_name", return_value=[]):
        result = checker.check("Dr. Nobody Here", None, "H3312-034")

    assert result.npi_verified is False
    assert result.in_network is False
    assert result.warning == "Provider not found in NPI registry. Verify name and credentials."


def test_provider_in_curated_data_matches_plan():
    cache = InMemoryProviderCache(ttl_seconds=60)
    checker = ProviderChecker(cache=cache)

    mock_npi_result = {
        "npi": "2345678901",
        "name": "EMILY THOMPSON",
        "specialty": "Family Medicine",
        "credential": "MD",
    }

    with patch.object(checker._npi_client, "lookup_by_npi", return_value=mock_npi_result):
        result = checker.check("Dr. Emily Thompson", "2345678901", "H3312-034")

    assert result.npi_verified is True
    assert result.in_network is True
