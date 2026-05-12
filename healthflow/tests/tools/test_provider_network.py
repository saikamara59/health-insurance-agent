from healthflow.tools.provider_network import ProviderNetworkDB, PROVIDER_NETWORK


def test_provider_network_has_40_entries():
    assert len(PROVIDER_NETWORK) >= 40


def test_provider_network_covers_10_specialties():
    specialties = {p["specialty"] for p in PROVIDER_NETWORK}
    expected = {
        "Internal Medicine",
        "Family Medicine",
        "Cardiology",
        "Orthopedics",
        "Dermatology",
        "Psychiatry",
        "Neurology",
        "Oncology",
        "Endocrinology",
        "Pulmonology",
    }
    assert expected.issubset(specialties)


def test_provider_network_covers_10_zip_codes():
    all_zips = set()
    for p in PROVIDER_NETWORK:
        all_zips.update(p["zip_codes"])
    expected_zips = {
        "10001", "90210", "60601", "33101", "77001",
        "85001", "98101", "30301", "02101", "75201",
    }
    assert expected_zips.issubset(all_zips)


def test_lookup_by_npi_in_network():
    db = ProviderNetworkDB()
    first_provider = PROVIDER_NETWORK[0]
    npi = first_provider["npi"]
    plan_id = first_provider["in_network_plans"][0]
    result = db.lookup_by_npi(npi, plan_id)
    assert result is True


def test_lookup_by_npi_out_of_network():
    db = ProviderNetworkDB()
    first_provider = PROVIDER_NETWORK[0]
    npi = first_provider["npi"]
    result = db.lookup_by_npi(npi, "FAKE-PLAN-999")
    assert result is False


def test_lookup_by_npi_unknown_npi():
    db = ProviderNetworkDB()
    result = db.lookup_by_npi("0000000000", "H3312-034")
    assert result is False


def test_lookup_by_name_found():
    db = ProviderNetworkDB()
    first_provider = PROVIDER_NETWORK[0]
    name = first_provider["name"]
    plan_id = first_provider["in_network_plans"][0]
    result = db.lookup_by_name(name, plan_id)
    assert result is not None
    assert "npi" in result
    assert "in_network" in result


def test_lookup_by_name_not_found():
    db = ProviderNetworkDB()
    result = db.lookup_by_name("Dr. Nonexistent Person", "H3312-034")
    assert result is None


def test_lookup_by_name_partial_match():
    db = ProviderNetworkDB()
    first_provider = PROVIDER_NETWORK[0]
    # Use just the last name portion
    last_name = first_provider["name"].split()[-1]
    plan_id = first_provider["in_network_plans"][0]
    result = db.lookup_by_name(last_name, plan_id)
    assert result is not None


def test_every_provider_has_required_fields():
    for p in PROVIDER_NETWORK:
        assert "npi" in p and len(p["npi"]) == 10
        assert "name" in p and len(p["name"]) > 0
        assert "specialty" in p and len(p["specialty"]) > 0
        assert "zip_codes" in p and len(p["zip_codes"]) > 0
        assert "in_network_plans" in p and len(p["in_network_plans"]) > 0
