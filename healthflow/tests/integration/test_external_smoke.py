"""Opt-in live smoke tests for external APIs HealthFlow depends on.

Skipped unless `LIVE_SMOKE_TESTS=1`. Run with:

    LIVE_SMOKE_TESTS=1 .venv/bin/python -m pytest healthflow/tests/integration/ -v

Or via the Makefile:

    make smoke-external

These catch upstream API contract drift (URL params, response shape, etc.)
that mocked unit tests can't see. Today's NPPES bug — query string silently
dropped by httpx when merged with `params=` — is exactly the class of failure
this file is here to detect on demand.
"""
import os

import pytest


_SMOKE_ENABLED = (
    os.getenv("LIVE_SMOKE_TESTS") == "1"
    or os.getenv("RXNAV_LIVE_TESTS") == "1"  # back-compat with the PR #16 toggle
)


_skip = pytest.mark.skipif(
    not _SMOKE_ENABLED,
    reason="Live external-API smoke test; set LIVE_SMOKE_TESTS=1 to enable",
)


@_skip
@pytest.mark.asyncio
async def test_rxnav_search_returns_metformin(tmp_path):
    """RxNav: 'metformin' returns ≥1 match with a numeric RxCUI containing
    'metformin' in the name. Detects RxNorm REST response-shape drift."""
    from healthflow.tools.rxnav_client import RxNavClient

    async with RxNavClient(cache_dir=tmp_path) as client:
        matches = await client.search("metformin", limit=10)

    assert len(matches) > 0, "expected at least one match from live RxNav"
    assert all(m.rxcui.isdigit() for m in matches), \
        f"every RxCUI should be numeric; got {[m.rxcui for m in matches]}"
    assert any("metformin" in m.name.lower() for m in matches), \
        f"expected Metformin in the results; got {[m.name for m in matches]}"


@_skip
def test_nppes_lookup_by_npi_returns_doctor():
    """NPPES: looking up a known seeded NPI returns a result with the expected
    fields populated. Would have caught the missing-version=2.1-param bug."""
    from healthflow.tools.npi_client import NPIClient

    # NPI 1982833471 is in scripts/real_doctors.json (Dr. Nivedita Aanur).
    # If NPPES retires or reissues this NPI, swap for any other NPI from
    # real_doctors.json — they're all live as of 2026-05.
    client = NPIClient()
    result = client.lookup_by_npi("1982833471")

    assert result is not None, "NPPES returned None — version param dropped?"
    assert result["npi"] == "1982833471"
    assert result["name"], "name field empty"
    assert result["specialty"], "specialty field empty"


@_skip
def test_nppes_search_by_name_returns_matches():
    """NPPES: searching by 'Aanur' returns at least one match. Exercises the
    search_by_name code path used when a provider has no NPI."""
    from healthflow.tools.npi_client import NPIClient

    client = NPIClient()
    results = client.search_by_name(first_name="Nivedita", last_name="Aanur")

    assert len(results) > 0, "expected at least one match for Aanur"
    assert any("aanur" in r["name"].lower() for r in results), \
        f"expected 'Aanur' in the results; got {[r['name'] for r in results]}"
