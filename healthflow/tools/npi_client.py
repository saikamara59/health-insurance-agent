import httpx

from healthflow.tools.provider_cache import InMemoryProviderCache

NPPES_BASE_URL = "https://npiregistry.cms.hhs.gov/api/?version=2.1"


class NPIClient:
    def __init__(self, cache: InMemoryProviderCache | None = None) -> None:
        self._http = httpx.Client(timeout=10.0)
        self._cache = cache or InMemoryProviderCache()

    def _parse_result(self, result: dict) -> dict:
        basic = result.get("basic", {})
        taxonomies = result.get("taxonomies", [])
        specialty = taxonomies[0]["desc"] if taxonomies else None

        return {
            "npi": result["number"],
            "name": f"{basic.get('first_name', '')} {basic.get('last_name', '')}",
            "specialty": specialty,
            "credential": basic.get("credential", ""),
        }

    def lookup_by_npi(self, npi: str) -> dict | None:
        cache_key = f"npi:{npi}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            response = self._http.get(
                NPPES_BASE_URL,
                params={"number": npi},
            )
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException):
            return None

        if data.get("result_count", 0) == 0:
            return None

        parsed = self._parse_result(data["results"][0])
        self._cache.set(cache_key, parsed)
        return parsed

    def search_by_name(
        self, first_name: str, last_name: str, state: str | None = None
    ) -> list[dict]:
        params: dict[str, str] = {
            "first_name": first_name,
            "last_name": last_name,
        }
        if state:
            params["state"] = state

        cache_key = f"name:{first_name.lower()}:{last_name.lower()}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached.get("results", [])

        try:
            response = self._http.get(NPPES_BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException):
            return []

        if data.get("result_count", 0) == 0:
            return []

        results = [self._parse_result(r) for r in data["results"]]
        self._cache.set(cache_key, {"results": results})
        return results
