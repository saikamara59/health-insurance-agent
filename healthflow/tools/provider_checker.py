from healthflow.models.schemas import ProviderResult
from healthflow.tools.npi_client import NPIClient
from healthflow.tools.provider_cache import InMemoryProviderCache
from healthflow.tools.provider_network import ProviderNetworkDB


class ProviderChecker:
    def __init__(self, cache: InMemoryProviderCache | None = None) -> None:
        self._cache = cache or InMemoryProviderCache()
        self._npi_client = NPIClient(cache=self._cache)
        self._network_db = ProviderNetworkDB()

    def _parse_name(self, full_name: str) -> tuple[str, str]:
        """Parse a full name into (first_name, last_name), stripping 'Dr.' prefix."""
        cleaned = full_name.strip()
        if cleaned.lower().startswith("dr."):
            cleaned = cleaned[3:].strip()
        elif cleaned.lower().startswith("dr "):
            cleaned = cleaned[3:].strip()

        parts = cleaned.split()
        if len(parts) == 0:
            return ("", "")
        if len(parts) == 1:
            return ("", parts[0])
        return (parts[0], parts[-1])

    def check(self, provider_name: str, npi: str | None, plan_id: str) -> ProviderResult:
        npi_data: dict | None = None
        verified = False
        specialty: str | None = None
        resolved_npi: str | None = npi

        if npi:
            npi_data = self._npi_client.lookup_by_npi(npi)
            if npi_data:
                verified = True
                specialty = npi_data.get("specialty")
        else:
            first_name, last_name = self._parse_name(provider_name)
            if last_name:
                results = self._npi_client.search_by_name(first_name, last_name)
                if results:
                    npi_data = results[0]
                    verified = True
                    specialty = npi_data.get("specialty")
                    resolved_npi = npi_data.get("npi")

        if not verified:
            return ProviderResult(
                name=provider_name,
                npi=resolved_npi,
                npi_verified=False,
                specialty=None,
                in_network=False,
                warning="Provider not found in NPI registry. Verify name and credentials.",
            )

        # Check curated network data
        in_network = False
        if resolved_npi:
            in_network = self._network_db.lookup_by_npi(resolved_npi, plan_id)

        if not in_network:
            # Also try name-based lookup in curated data
            name_result = self._network_db.lookup_by_name(provider_name, plan_id)
            if name_result and name_result.get("in_network"):
                in_network = True

        return ProviderResult(
            name=provider_name,
            npi=resolved_npi,
            npi_verified=True,
            specialty=specialty,
            in_network=in_network,
            warning=None,
        )
