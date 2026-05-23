"""Opt-in live RxNav integration test. Skipped unless RXNAV_LIVE_TESTS=1.

Run with:
    RXNAV_LIVE_TESTS=1 .venv/bin/python -m pytest healthflow/tests/integration/test_rxnav_live.py -v

Detects RxNav response-shape drift on demand without burdening CI with a
network dependency.
"""
import os

import pytest

from healthflow.tools.rxnav_client import RxNavClient


_LIVE_TESTS_ENABLED = os.getenv("RXNAV_LIVE_TESTS") == "1"


@pytest.mark.skipif(
    not _LIVE_TESTS_ENABLED,
    reason="Live RxNav test; set RXNAV_LIVE_TESTS=1 to enable",
)
@pytest.mark.asyncio
async def test_live_search_returns_metformin(tmp_path):
    """Hit the real RxNav for 'metformin' and assert at least one Metformin
    match is returned with a valid RxCUI."""
    async with RxNavClient(cache_dir=tmp_path) as client:
        matches = await client.search("metformin", limit=10)

    assert len(matches) > 0, "expected at least one match from live RxNav"
    assert all(m.rxcui.isdigit() for m in matches), \
        f"every RxCUI should be numeric; got {[m.rxcui for m in matches]}"
    assert any("metformin" in m.name.lower() for m in matches), \
        f"expected Metformin in the results; got {[m.name for m in matches]}"
