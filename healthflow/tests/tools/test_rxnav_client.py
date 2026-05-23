"""RxNavClient unit tests — all HTTP stubbed via httpx.MockTransport,
no live network calls in CI.
"""
import os
import pytest
import httpx

from healthflow.tools.rxnav_client import RxNavClient


_METFORMIN_EXACT_PAYLOAD = {
    "drugGroup": {
        "name": "metformin",
        "conceptGroup": [
            {
                "tty": "SCD",
                "conceptProperties": [
                    {
                        "rxcui": "860975",
                        "name": "Metformin hydrochloride 500 MG Oral Tablet",
                        "synonym": "",
                        "tty": "SCD",
                    }
                ],
            },
            {
                "tty": "SBD",
                "conceptProperties": [
                    {
                        "rxcui": "861007",
                        "name": "Glucophage 500 MG Oral Tablet",
                        "synonym": "",
                        "tty": "SBD",
                    }
                ],
            },
        ],
    }
}


_EMPTY_EXACT_PAYLOAD = {"drugGroup": {"name": "metfromn", "conceptGroup": []}}


_APPROXIMATE_PAYLOAD = {
    "approximateGroup": {
        "candidate": [
            {
                "rxcui": "860975",
                "name": "Metformin hydrochloride 500 MG Oral Tablet",
                "score": "100",
                "rank": "1",
                "tty": "SCD",
            }
        ]
    }
}


def _mock_transport(responses):
    """Build an httpx.MockTransport from a list of (status, json) tuples,
    in the order they should be served."""
    iterator = iter(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        status, payload = next(iterator)
        return httpx.Response(status_code=status, json=payload)

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_search_returns_matches_for_known_drug(tmp_path):
    transport = _mock_transport([(200, _METFORMIN_EXACT_PAYLOAD)])
    http_client = httpx.AsyncClient(transport=transport)
    client = RxNavClient(http_client=http_client, cache_dir=tmp_path)

    matches = await client.search("metformin", limit=10)

    assert len(matches) == 2
    assert matches[0].rxcui == "860975"
    assert matches[0].term_type == "SCD"
    assert matches[0].is_brand is False
    assert matches[1].rxcui == "861007"
    assert matches[1].term_type == "SBD"
    assert matches[1].is_brand is True
    await http_client.aclose()


@pytest.mark.asyncio
async def test_search_falls_back_to_approximate_when_empty(tmp_path):
    transport = _mock_transport([
        (200, _EMPTY_EXACT_PAYLOAD),
        (200, _APPROXIMATE_PAYLOAD),
    ])
    http_client = httpx.AsyncClient(transport=transport)
    client = RxNavClient(http_client=http_client, cache_dir=tmp_path)

    matches = await client.search("metfromn", limit=10)

    assert len(matches) == 1
    assert matches[0].rxcui == "860975"
    assert matches[0].term_type == "SCD"
    await http_client.aclose()


@pytest.mark.asyncio
async def test_search_returns_empty_on_timeout(tmp_path, caplog):
    def raise_timeout(request):
        raise httpx.ConnectTimeout("simulated timeout")

    transport = httpx.MockTransport(raise_timeout)
    http_client = httpx.AsyncClient(transport=transport)
    client = RxNavClient(http_client=http_client, cache_dir=tmp_path)

    import logging
    with caplog.at_level(logging.WARNING, logger="healthflow.tools.rxnav_client"):
        matches = await client.search("metformin", limit=10)

    assert matches == []
    assert any("rxnav.search_exact failed" in r.getMessage() for r in caplog.records)
    await http_client.aclose()


@pytest.mark.asyncio
async def test_cache_hit_skips_http(tmp_path):
    call_count = {"n": 0}

    def handler(request):
        call_count["n"] += 1
        return httpx.Response(200, json=_METFORMIN_EXACT_PAYLOAD)

    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)
    client = RxNavClient(http_client=http_client, cache_dir=tmp_path)

    first = await client.search("metformin", limit=10)
    second = await client.search("metformin", limit=10)

    assert call_count["n"] == 1
    assert len(first) == 2
    assert first == second
    await http_client.aclose()


@pytest.mark.asyncio
async def test_cache_miss_after_ttl(tmp_path):
    call_count = {"n": 0}

    def handler(request):
        call_count["n"] += 1
        return httpx.Response(200, json=_METFORMIN_EXACT_PAYLOAD)

    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)
    client = RxNavClient(http_client=http_client, cache_dir=tmp_path)

    await client.search("metformin", limit=10)
    assert call_count["n"] == 1

    # Backdate every cache file by 25 hours so it counts as expired.
    backdated = (
        os.path.getmtime(tmp_path.iterdir().__next__())  # any cache file
        - 25 * 3600
    )
    for f in tmp_path.iterdir():
        if f.suffix == ".json":
            os.utime(f, (backdated, backdated))

    await client.search("metformin", limit=10)
    assert call_count["n"] == 2
    await http_client.aclose()
