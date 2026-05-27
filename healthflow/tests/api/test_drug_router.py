"""Endpoint tests for GET /drugs/search.

Uses the existing `client` fixture + monkeypatches RxNavClient in the router
module to a fake that returns predetermined matches. No live RxNav calls.
"""
import pytest

from healthflow.tools.rxnav_client import DrugMatch


# Two known matches the fake returns when search() is called.
_FAKE_MATCHES = [
    DrugMatch(
        rxcui="860975",
        name="Metformin hydrochloride 500 MG Oral Tablet",
        term_type="SCD",
        is_brand=False,
    ),
    DrugMatch(
        rxcui="861007",
        name="Glucophage 500 MG Oral Tablet",
        term_type="SBD",
        is_brand=True,
    ),
]


class _FakeRxNavClient:
    """Drop-in for RxNavClient that records the last query + returns fixed matches."""
    def __init__(self, matches=None, raises=None):
        self._matches = matches if matches is not None else _FAKE_MATCHES
        self._raises = raises
        self.last_query: tuple[str, int] | None = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    async def search(self, query, *, limit=10):
        if self._raises is not None:
            raise self._raises
        self.last_query = (query, limit)
        return self._matches


async def _register_and_login(client, email="drugs@example.com", password="Cromulent42!"):
    reg = await client.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": "Drug Tester"},
    )
    assert reg.status_code == 201
    # Production /auth/register creates accounts as pending; flip via test router.
    act = await client.post("/__test/activate-broker", json={"email": email})
    assert act.status_code == 200, act.text
    login = await client.post(
        "/auth/login", json={"email": email, "password": password}
    )
    assert login.status_code == 200
    return login.json()["access_token"]


@pytest.mark.asyncio
async def test_search_happy_path(client, monkeypatch):
    """Bearer + ?q=metformin → 200; schema correct; fake client saw (query, limit)."""
    from healthflow.api import drug_router as drug_router_mod

    fake = _FakeRxNavClient()
    monkeypatch.setattr(drug_router_mod, "RxNavClient", lambda: fake)

    access = await _register_and_login(client)
    resp = await client.get(
        "/drugs/search?q=metformin&limit=10",
        headers={"Authorization": f"Bearer {access}"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["query"] == "metformin"
    assert len(body["matches"]) == 2
    assert body["matches"][0]["rxcui"] == "860975"
    assert body["matches"][0]["is_brand"] is False
    assert body["matches"][1]["is_brand"] is True
    assert fake.last_query == ("metformin", 10)


@pytest.mark.asyncio
async def test_search_requires_bearer(client):
    """No Authorization header → 401."""
    resp = await client.get("/drugs/search?q=metformin")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_search_rejects_empty_query(client):
    """?q= (empty) → 422 from Pydantic min_length=1."""
    access = await _register_and_login(client, email="empty@example.com")
    resp = await client.get(
        "/drugs/search?q=",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_search_returns_empty_when_rxnav_client_raises(client, monkeypatch):
    """Fake client raises → endpoint catches at boundary; 200 with empty matches."""
    from healthflow.api import drug_router as drug_router_mod

    fake = _FakeRxNavClient(raises=RuntimeError("simulated boom"))
    monkeypatch.setattr(drug_router_mod, "RxNavClient", lambda: fake)

    access = await _register_and_login(client, email="boom@example.com")
    resp = await client.get(
        "/drugs/search?q=metformin",
        headers={"Authorization": f"Bearer {access}"},
    )

    assert resp.status_code == 200
    assert resp.json() == {"query": "metformin", "matches": []}
