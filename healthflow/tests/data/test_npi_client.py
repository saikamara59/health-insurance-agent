from unittest.mock import MagicMock, patch

import httpx

from healthflow.tools.npi_client import NPIClient
from healthflow.tools.provider_cache import InMemoryProviderCache


SAMPLE_NPPES_RESPONSE = {
    "result_count": 1,
    "results": [
        {
            "number": "1234567890",
            "basic": {
                "first_name": "SARAH",
                "last_name": "CHEN",
                "credential": "MD",
            },
            "taxonomies": [
                {"desc": "Internal Medicine", "primary": True}
            ],
            "addresses": [],
        }
    ],
}

SAMPLE_NPPES_EMPTY = {
    "result_count": 0,
    "results": [],
}


def _make_mock_response(json_data: dict, status_code: int = 200) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    return resp


def test_lookup_by_npi_found():
    cache = InMemoryProviderCache(ttl_seconds=60)
    client = NPIClient(cache=cache)
    mock_resp = _make_mock_response(SAMPLE_NPPES_RESPONSE)

    with patch.object(client._http, "get", return_value=mock_resp) as mock_get:
        result = client.lookup_by_npi("1234567890")

    assert result is not None
    assert result["npi"] == "1234567890"
    assert result["name"] == "SARAH CHEN"
    assert result["specialty"] == "Internal Medicine"
    assert result["credential"] == "MD"
    mock_get.assert_called_once()


def test_lookup_by_npi_not_found():
    cache = InMemoryProviderCache(ttl_seconds=60)
    client = NPIClient(cache=cache)
    mock_resp = _make_mock_response(SAMPLE_NPPES_EMPTY)

    with patch.object(client._http, "get", return_value=mock_resp):
        result = client.lookup_by_npi("0000000000")

    assert result is None


def test_search_by_name_found():
    cache = InMemoryProviderCache(ttl_seconds=60)
    client = NPIClient(cache=cache)
    mock_resp = _make_mock_response(SAMPLE_NPPES_RESPONSE)

    with patch.object(client._http, "get", return_value=mock_resp):
        results = client.search_by_name("Sarah", "Chen")

    assert len(results) == 1
    assert results[0]["npi"] == "1234567890"
    assert results[0]["name"] == "SARAH CHEN"


def test_search_by_name_with_state():
    cache = InMemoryProviderCache(ttl_seconds=60)
    client = NPIClient(cache=cache)
    mock_resp = _make_mock_response(SAMPLE_NPPES_RESPONSE)

    with patch.object(client._http, "get", return_value=mock_resp) as mock_get:
        results = client.search_by_name("Sarah", "Chen", state="NY")

    assert len(results) == 1
    call_kwargs = mock_get.call_args
    assert "state" in str(call_kwargs)


def test_search_by_name_no_results():
    cache = InMemoryProviderCache(ttl_seconds=60)
    client = NPIClient(cache=cache)
    mock_resp = _make_mock_response(SAMPLE_NPPES_EMPTY)

    with patch.object(client._http, "get", return_value=mock_resp):
        results = client.search_by_name("Nonexistent", "Doctor")

    assert results == []


def test_api_error_returns_none():
    cache = InMemoryProviderCache(ttl_seconds=60)
    client = NPIClient(cache=cache)

    with patch.object(
        client._http,
        "get",
        side_effect=httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=MagicMock()
        ),
    ):
        result = client.lookup_by_npi("1234567890")

    assert result is None


def test_lookup_uses_cache():
    cache = InMemoryProviderCache(ttl_seconds=60)
    cache.set("npi:1234567890", {
        "npi": "1234567890",
        "name": "SARAH CHEN",
        "specialty": "Internal Medicine",
        "credential": "MD",
    })
    client = NPIClient(cache=cache)

    with patch.object(client._http, "get") as mock_get:
        result = client.lookup_by_npi("1234567890")

    assert result is not None
    assert result["npi"] == "1234567890"
    mock_get.assert_not_called()


def test_lookup_caches_result():
    cache = InMemoryProviderCache(ttl_seconds=60)
    client = NPIClient(cache=cache)
    mock_resp = _make_mock_response(SAMPLE_NPPES_RESPONSE)

    with patch.object(client._http, "get", return_value=mock_resp):
        client.lookup_by_npi("1234567890")

    cached = cache.get("npi:1234567890")
    assert cached is not None
    assert cached["npi"] == "1234567890"


def test_connection_error_returns_none():
    cache = InMemoryProviderCache(ttl_seconds=60)
    client = NPIClient(cache=cache)

    with patch.object(client._http, "get", side_effect=httpx.ConnectError("Connection failed")):
        result = client.lookup_by_npi("1234567890")

    assert result is None
