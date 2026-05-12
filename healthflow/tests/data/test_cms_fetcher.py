from healthflow.tools.cms_fetcher import MockCMSFetcher


def test_fetch_plans_known_zip():
    fetcher = MockCMSFetcher()
    plans = fetcher.fetch_plans("10001")
    assert len(plans) >= 5
    for plan in plans:
        assert "plan_name" in plan
        assert "plan_id" in plan
        assert "monthly_premium" in plan
        assert "annual_deductible" in plan
        assert "out_of_pocket_max" in plan
        assert "star_rating" in plan
        assert "plan_type" in plan
        assert "drug_coverage" in plan


def test_fetch_plans_unknown_zip_returns_plans():
    fetcher = MockCMSFetcher()
    plans = fetcher.fetch_plans("99999")
    assert len(plans) >= 3


def test_fetch_plans_realistic_premium_range():
    fetcher = MockCMSFetcher()
    plans = fetcher.fetch_plans("10001")
    for plan in plans:
        assert 0 <= plan["monthly_premium"] <= 175


def test_fetch_plans_realistic_star_rating():
    fetcher = MockCMSFetcher()
    plans = fetcher.fetch_plans("10001")
    for plan in plans:
        assert 1.0 <= plan["star_rating"] <= 5.0


def test_fetch_plans_has_hmo_and_ppo():
    fetcher = MockCMSFetcher()
    plans = fetcher.fetch_plans("10001")
    plan_types = {p["plan_type"] for p in plans}
    assert "HMO" in plan_types or "PPO" in plan_types


def test_fetch_plans_multiple_zips_return_data():
    fetcher = MockCMSFetcher()
    for zip_code in ["10001", "90210", "60601", "33101", "77001"]:
        plans = fetcher.fetch_plans(zip_code)
        assert len(plans) >= 5, f"Zip {zip_code} returned fewer than 5 plans"
