PROVIDER_NETWORK: list[dict] = [
    # Internal Medicine (4 providers)
    {
        "npi": "1234567890",
        "name": "Dr. Sarah Chen",
        "specialty": "Internal Medicine",
        "zip_codes": ["10001", "02101"],
        "in_network_plans": ["H3312-034", "H1036-200", "H2228-050", "H7917-010"],
    },
    {
        "npi": "1234567891",
        "name": "Dr. James Wilson",
        "specialty": "Internal Medicine",
        "zip_codes": ["90210", "85001"],
        "in_network_plans": ["H5521-017", "H1036-180", "H5410-022", "H0524-001"],
    },
    {
        "npi": "1234567892",
        "name": "Dr. Maria Garcia",
        "specialty": "Internal Medicine",
        "zip_codes": ["60601", "30301"],
        "in_network_plans": ["H2228-063", "H7917-025", "H1032-064", "H6105-012"],
    },
    {
        "npi": "1234567893",
        "name": "Dr. Robert Kim",
        "specialty": "Internal Medicine",
        "zip_codes": ["33101", "77001"],
        "in_network_plans": ["H3312-034", "H2228-071", "H5410-038", "H3952-018"],
    },
    # Family Medicine (4 providers)
    {
        "npi": "2345678901",
        "name": "Dr. Emily Thompson",
        "specialty": "Family Medicine",
        "zip_codes": ["10001", "60601"],
        "in_network_plans": ["H3312-034", "H1036-200", "H7917-010", "H1032-064"],
    },
    {
        "npi": "2345678902",
        "name": "Dr. Michael Brown",
        "specialty": "Family Medicine",
        "zip_codes": ["90210", "75201"],
        "in_network_plans": ["H5521-017", "H1036-180", "H5410-022", "H8230-003"],
    },
    {
        "npi": "2345678903",
        "name": "Dr. Lisa Patel",
        "specialty": "Family Medicine",
        "zip_codes": ["33101", "98101"],
        "in_network_plans": ["H2228-050", "H2228-063", "H0524-001", "H7322-008"],
    },
    {
        "npi": "2345678904",
        "name": "Dr. David Martinez",
        "specialty": "Family Medicine",
        "zip_codes": ["77001", "85001"],
        "in_network_plans": ["H1032-070", "H9622-005", "H3952-018", "H8245-002"],
    },
    # Cardiology (4 providers)
    {
        "npi": "3456789012",
        "name": "Dr. Jennifer Lee",
        "specialty": "Cardiology",
        "zip_codes": ["10001", "02101"],
        "in_network_plans": ["H3312-034", "H5521-017", "H2228-050", "H7917-010"],
    },
    {
        "npi": "3456789013",
        "name": "Dr. William Chang",
        "specialty": "Cardiology",
        "zip_codes": ["90210", "85001"],
        "in_network_plans": ["H1036-200", "H1036-180", "H5410-022", "H0524-001"],
    },
    {
        "npi": "3456789014",
        "name": "Dr. Amanda White",
        "specialty": "Cardiology",
        "zip_codes": ["60601", "30301"],
        "in_network_plans": ["H2228-063", "H2228-071", "H7917-025", "H1032-064"],
    },
    {
        "npi": "3456789015",
        "name": "Dr. Christopher Davis",
        "specialty": "Cardiology",
        "zip_codes": ["33101", "98101"],
        "in_network_plans": ["H5410-038", "H7917-010", "H9622-005", "H6105-012"],
    },
    # Orthopedics (4 providers)
    {
        "npi": "4567890123",
        "name": "Dr. Patricia Moore",
        "specialty": "Orthopedics",
        "zip_codes": ["10001", "77001"],
        "in_network_plans": ["H3312-034", "H1036-200", "H2228-050", "H1032-070"],
    },
    {
        "npi": "4567890124",
        "name": "Dr. Daniel Taylor",
        "specialty": "Orthopedics",
        "zip_codes": ["90210", "75201"],
        "in_network_plans": ["H5521-017", "H1036-180", "H5410-022", "H3952-018"],
    },
    {
        "npi": "4567890125",
        "name": "Dr. Susan Anderson",
        "specialty": "Orthopedics",
        "zip_codes": ["60601", "98101"],
        "in_network_plans": ["H2228-063", "H7917-025", "H0524-001", "H8230-003"],
    },
    {
        "npi": "4567890126",
        "name": "Dr. Matthew Thomas",
        "specialty": "Orthopedics",
        "zip_codes": ["33101", "30301"],
        "in_network_plans": ["H2228-071", "H5410-038", "H7917-010", "H7322-008"],
    },
    # Dermatology (4 providers)
    {
        "npi": "5678901234",
        "name": "Dr. Rachel Green",
        "specialty": "Dermatology",
        "zip_codes": ["10001", "02101"],
        "in_network_plans": ["H3312-034", "H5521-017", "H7917-010", "H1032-064"],
    },
    {
        "npi": "5678901235",
        "name": "Dr. Andrew Jackson",
        "specialty": "Dermatology",
        "zip_codes": ["90210", "85001"],
        "in_network_plans": ["H1036-200", "H1036-180", "H0524-001", "H9622-005"],
    },
    {
        "npi": "5678901236",
        "name": "Dr. Nicole Harris",
        "specialty": "Dermatology",
        "zip_codes": ["60601", "77001"],
        "in_network_plans": ["H2228-050", "H2228-063", "H5410-022", "H1032-070"],
    },
    {
        "npi": "5678901237",
        "name": "Dr. Kevin Clark",
        "specialty": "Dermatology",
        "zip_codes": ["33101", "75201"],
        "in_network_plans": ["H2228-071", "H5410-038", "H3952-018", "H8245-002"],
    },
    # Psychiatry (4 providers)
    {
        "npi": "6789012345",
        "name": "Dr. Laura Robinson",
        "specialty": "Psychiatry",
        "zip_codes": ["10001", "30301"],
        "in_network_plans": ["H3312-034", "H1036-200", "H7917-025", "H6105-012"],
    },
    {
        "npi": "6789012346",
        "name": "Dr. Steven Wright",
        "specialty": "Psychiatry",
        "zip_codes": ["90210", "98101"],
        "in_network_plans": ["H5521-017", "H2228-050", "H0524-001", "H8230-003"],
    },
    {
        "npi": "6789012347",
        "name": "Dr. Karen Lewis",
        "specialty": "Psychiatry",
        "zip_codes": ["60601", "85001"],
        "in_network_plans": ["H1036-180", "H2228-063", "H5410-022", "H1032-064"],
    },
    {
        "npi": "6789012348",
        "name": "Dr. Brian Walker",
        "specialty": "Psychiatry",
        "zip_codes": ["33101", "02101"],
        "in_network_plans": ["H2228-071", "H5410-038", "H7917-010", "H7322-008"],
    },
    # Neurology (4 providers)
    {
        "npi": "7890123456",
        "name": "Dr. Jessica Hall",
        "specialty": "Neurology",
        "zip_codes": ["10001", "77001"],
        "in_network_plans": ["H3312-034", "H5521-017", "H1036-200", "H1032-070"],
    },
    {
        "npi": "7890123457",
        "name": "Dr. Thomas Allen",
        "specialty": "Neurology",
        "zip_codes": ["90210", "75201"],
        "in_network_plans": ["H1036-180", "H2228-050", "H5410-022", "H3952-018"],
    },
    {
        "npi": "7890123458",
        "name": "Dr. Stephanie Young",
        "specialty": "Neurology",
        "zip_codes": ["60601", "30301"],
        "in_network_plans": ["H2228-063", "H7917-025", "H9622-005", "H8230-003"],
    },
    {
        "npi": "7890123459",
        "name": "Dr. Ryan King",
        "specialty": "Neurology",
        "zip_codes": ["33101", "98101"],
        "in_network_plans": ["H2228-071", "H5410-038", "H0524-001", "H6105-012"],
    },
    # Oncology (4 providers)
    {
        "npi": "8901234567",
        "name": "Dr. Michelle Scott",
        "specialty": "Oncology",
        "zip_codes": ["10001", "85001"],
        "in_network_plans": ["H3312-034", "H1036-200", "H7917-010", "H9622-005"],
    },
    {
        "npi": "8901234568",
        "name": "Dr. Jason Adams",
        "specialty": "Oncology",
        "zip_codes": ["90210", "02101"],
        "in_network_plans": ["H5521-017", "H1036-180", "H0524-001", "H8245-002"],
    },
    {
        "npi": "8901234569",
        "name": "Dr. Samantha Baker",
        "specialty": "Oncology",
        "zip_codes": ["60601", "98101"],
        "in_network_plans": ["H2228-050", "H2228-063", "H5410-022", "H1032-064"],
    },
    {
        "npi": "8901234570",
        "name": "Dr. Eric Nelson",
        "specialty": "Oncology",
        "zip_codes": ["33101", "77001"],
        "in_network_plans": ["H2228-071", "H5410-038", "H1032-070", "H3952-018"],
    },
    # Endocrinology (4 providers)
    {
        "npi": "9012345678",
        "name": "Dr. Angela Carter",
        "specialty": "Endocrinology",
        "zip_codes": ["10001", "60601"],
        "in_network_plans": ["H3312-034", "H5521-017", "H2228-050", "H7917-025"],
    },
    {
        "npi": "9012345679",
        "name": "Dr. Mark Phillips",
        "specialty": "Endocrinology",
        "zip_codes": ["90210", "30301"],
        "in_network_plans": ["H1036-200", "H1036-180", "H7917-010", "H6105-012"],
    },
    {
        "npi": "9012345680",
        "name": "Dr. Cynthia Evans",
        "specialty": "Endocrinology",
        "zip_codes": ["33101", "75201"],
        "in_network_plans": ["H2228-063", "H5410-022", "H3952-018", "H8230-003"],
    },
    {
        "npi": "9012345681",
        "name": "Dr. Paul Turner",
        "specialty": "Endocrinology",
        "zip_codes": ["77001", "98101"],
        "in_network_plans": ["H2228-071", "H0524-001", "H1032-064", "H7322-008"],
    },
    # Pulmonology (4 providers)
    {
        "npi": "1023456789",
        "name": "Dr. Diana Collins",
        "specialty": "Pulmonology",
        "zip_codes": ["10001", "85001"],
        "in_network_plans": ["H3312-034", "H1036-200", "H5410-022", "H1032-070"],
    },
    {
        "npi": "1023456790",
        "name": "Dr. Gregory Stewart",
        "specialty": "Pulmonology",
        "zip_codes": ["90210", "02101"],
        "in_network_plans": ["H5521-017", "H1036-180", "H7917-010", "H9622-005"],
    },
    {
        "npi": "1023456791",
        "name": "Dr. Megan Morris",
        "specialty": "Pulmonology",
        "zip_codes": ["60601", "77001"],
        "in_network_plans": ["H2228-050", "H2228-063", "H0524-001", "H8245-002"],
    },
    {
        "npi": "1023456792",
        "name": "Dr. Scott Rogers",
        "specialty": "Pulmonology",
        "zip_codes": ["33101", "75201"],
        "in_network_plans": ["H2228-071", "H5410-038", "H3952-018", "H6105-012"],
    },
]


import hashlib

# ~70% of (npi, plan_id) pairs hash into the in-network bucket. Real carrier
# networks run 75-95% in-network; 70% gives a realistic mix of in/out for
# demos without overclaiming.
_SYNTHETIC_IN_NETWORK_THRESHOLD = 179  # 179/256 ≈ 0.699


class ProviderNetworkDB:
    def __init__(self) -> None:
        self._by_npi: dict[str, dict] = {p["npi"]: p for p in PROVIDER_NETWORK}
        self._by_name: dict[str, dict] = {}
        for p in PROVIDER_NETWORK:
            self._by_name[p["name"].lower()] = p
            # Index by last name for partial matching
            parts = p["name"].split()
            if parts:
                self._by_name[parts[-1].lower()] = p

    def lookup_by_npi(self, npi: str, plan_id: str) -> bool:
        provider = self._by_npi.get(npi)
        if provider is not None:
            return plan_id in provider["in_network_plans"]
        # NPPES-verified NPI that isn't in our curated demo list — fall through
        # to a deterministic synthetic decision. Real carrier network membership
        # isn't publicly available; this gives a stable, realistic-looking
        # in/out distribution for demos without inventing specific claims.
        return self._synthetic_membership(npi, plan_id)

    @staticmethod
    def _synthetic_membership(npi: str, plan_id: str) -> bool:
        digest = hashlib.sha256(f"{npi}:{plan_id}".encode()).digest()
        return digest[0] < _SYNTHETIC_IN_NETWORK_THRESHOLD

    def lookup_by_name(self, name: str, plan_id: str) -> dict | None:
        name_lower = name.lower().strip()

        # Exact match first
        provider = self._by_name.get(name_lower)
        if provider is None:
            # Try substring match
            for key, p in self._by_name.items():
                if name_lower in key or key in name_lower:
                    provider = p
                    break

        if provider is None:
            return None

        return {
            "npi": provider["npi"],
            "name": provider["name"],
            "specialty": provider["specialty"],
            "in_network": plan_id in provider["in_network_plans"],
        }
