"""Async client for the NLM RxNav REST API.

Single responsibility: ask RxNav for drug matches, cache the answer on disk,
return them. Silent-fail on any network error or upstream 4xx/5xx — returns []
rather than raising. Autocomplete must never crash a request.
"""
import hashlib
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DrugMatch:
    rxcui: str
    name: str
    term_type: str            # RxNorm TTY: "SBD", "SCD", "IN", "PIN", "BN", etc.
    is_brand: bool            # True if term_type in {"SBD", "BN"}


class RxNavClient:
    BASE_URL = "https://rxnav.nlm.nih.gov/REST"
    DEFAULT_TIMEOUT_SECONDS = 5.0
    CACHE_TTL_SECONDS = 86_400  # 24h
    _BRAND_TTYS = frozenset({"SBD", "BN"})

    def __init__(
        self,
        http_client: httpx.AsyncClient | None = None,
        cache_dir: Path | None = None,
    ):
        self._http = http_client
        self._owns_http = http_client is None
        self._cache_dir = cache_dir or (
            Path.home() / ".cache" / "healthflow" / "rxnav"
        )
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    async def __aenter__(self) -> "RxNavClient":
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=self.DEFAULT_TIMEOUT_SECONDS)
        return self

    async def __aexit__(self, *_):
        if self._owns_http and self._http is not None:
            await self._http.aclose()
            self._http = None

    async def search(self, query: str, *, limit: int = 10) -> list[DrugMatch]:
        cache_key = self._cache_key("search", query, limit)
        cached = self._cache_get(cache_key)
        if cached is not None:
            return [DrugMatch(**m) for m in cached]

        matches = await self._search_exact(query, limit)
        if not matches:
            matches = await self._search_approximate(query, limit)

        self._cache_put(cache_key, [m.__dict__ for m in matches])
        return matches

    async def _search_exact(self, query: str, limit: int) -> list[DrugMatch]:
        try:
            resp = await self._http.get(
                f"{self.BASE_URL}/drugs.json", params={"name": query}
            )
            if resp.status_code != 200:
                return []
            data = resp.json()
        except (httpx.HTTPError, ValueError) as e:
            logger.warning("rxnav.search_exact failed: %s", e)
            return []

        out: list[DrugMatch] = []
        for group in (data.get("drugGroup") or {}).get("conceptGroup") or []:
            tty = group.get("tty", "")
            for cp in group.get("conceptProperties") or []:
                rxcui = cp.get("rxcui")
                name = cp.get("name") or cp.get("synonym")
                if not rxcui or not name:
                    continue
                out.append(DrugMatch(
                    rxcui=str(rxcui),
                    name=name,
                    term_type=tty,
                    is_brand=tty in self._BRAND_TTYS,
                ))
                if len(out) >= limit:
                    return out
        return out

    async def _search_approximate(self, query: str, limit: int) -> list[DrugMatch]:
        try:
            resp = await self._http.get(
                f"{self.BASE_URL}/approximateTerm.json",
                params={"term": query, "maxEntries": limit},
            )
            if resp.status_code != 200:
                return []
            data = resp.json()
        except (httpx.HTTPError, ValueError) as e:
            logger.warning("rxnav.search_approximate failed: %s", e)
            return []

        candidates = (data.get("approximateGroup") or {}).get("candidate") or []
        out: list[DrugMatch] = []
        for c in candidates[:limit]:
            rxcui = c.get("rxcui")
            name = c.get("name")
            if not rxcui or not name:
                continue
            tty = c.get("tty", "")
            out.append(DrugMatch(
                rxcui=str(rxcui),
                name=name,
                term_type=tty,
                is_brand=tty in self._BRAND_TTYS,
            ))
        return out

    def _cache_key(self, *parts: object) -> str:
        h = hashlib.sha256(":".join(str(p).lower() for p in parts).encode())
        return h.hexdigest()[:32]

    def _cache_get(self, key: str) -> list[dict] | None:
        path = self._cache_dir / f"{key}.json"
        if not path.exists():
            return None
        if time.time() - path.stat().st_mtime > self.CACHE_TTL_SECONDS:
            return None
        try:
            return json.loads(path.read_text())
        except (OSError, ValueError):
            return None

    def _cache_put(self, key: str, value: list[dict]) -> None:
        path = self._cache_dir / f"{key}.json"
        tmp = path.with_suffix(".json.tmp")
        try:
            tmp.write_text(json.dumps(value))
            tmp.replace(path)
        except OSError as e:
            logger.warning("rxnav.cache_put failed: %s", e)
