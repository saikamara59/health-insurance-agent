import random
from typing import Protocol


class CMSFetcher(Protocol):
    def fetch_plans(self, zip_code: str) -> list[dict]: ...


ALL_PLANS = [
    {
        "plan_name": "Aetna Medicare Eagle Plus (HMO)",
        "plan_id": "H3312-034",
        "monthly_premium": 0.00,
        "annual_deductible": 250.00,
        "out_of_pocket_max": 4500.00,
        "star_rating": 4.5,
        "plan_type": "HMO",
        "drug_coverage": True,
    },
    {
        "plan_name": "Aetna Medicare Value (PPO)",
        "plan_id": "H5521-017",
        "monthly_premium": 45.00,
        "annual_deductible": 0.00,
        "out_of_pocket_max": 5900.00,
        "star_rating": 4.0,
        "plan_type": "PPO",
        "drug_coverage": True,
    },
    {
        "plan_name": "Humana Gold Plus (HMO-POS)",
        "plan_id": "H1036-200",
        "monthly_premium": 0.00,
        "annual_deductible": 0.00,
        "out_of_pocket_max": 3400.00,
        "star_rating": 4.5,
        "plan_type": "HMO",
        "drug_coverage": True,
    },
    {
        "plan_name": "Humana Choice (PPO)",
        "plan_id": "H1036-180",
        "monthly_premium": 75.50,
        "annual_deductible": 200.00,
        "out_of_pocket_max": 6700.00,
        "star_rating": 3.5,
        "plan_type": "PPO",
        "drug_coverage": True,
    },
    {
        "plan_name": "UHC Medicare Advantage Choice (PPO)",
        "plan_id": "H2228-050",
        "monthly_premium": 25.00,
        "annual_deductible": 150.00,
        "out_of_pocket_max": 5500.00,
        "star_rating": 4.0,
        "plan_type": "PPO",
        "drug_coverage": True,
    },
    {
        "plan_name": "UHC Medicare Advantage Star (HMO)",
        "plan_id": "H2228-063",
        "monthly_premium": 0.00,
        "annual_deductible": 0.00,
        "out_of_pocket_max": 3900.00,
        "star_rating": 5.0,
        "plan_type": "HMO",
        "drug_coverage": True,
    },
    {
        "plan_name": "UHC Dual Complete (HMO-SNP)",
        "plan_id": "H2228-071",
        "monthly_premium": 0.00,
        "annual_deductible": 0.00,
        "out_of_pocket_max": 3000.00,
        "star_rating": 4.0,
        "plan_type": "HMO",
        "drug_coverage": True,
    },
    {
        "plan_name": "Cigna Preferred Medicare (HMO)",
        "plan_id": "H5410-022",
        "monthly_premium": 35.00,
        "annual_deductible": 100.00,
        "out_of_pocket_max": 4200.00,
        "star_rating": 4.0,
        "plan_type": "HMO",
        "drug_coverage": True,
    },
    {
        "plan_name": "Cigna True Choice Medicare (PPO)",
        "plan_id": "H5410-038",
        "monthly_premium": 110.00,
        "annual_deductible": 0.00,
        "out_of_pocket_max": 5000.00,
        "star_rating": 3.5,
        "plan_type": "PPO",
        "drug_coverage": True,
    },
    {
        "plan_name": "BCBS Medicare Blue Choice (PPO)",
        "plan_id": "H7917-010",
        "monthly_premium": 55.00,
        "annual_deductible": 175.00,
        "out_of_pocket_max": 6200.00,
        "star_rating": 4.5,
        "plan_type": "PPO",
        "drug_coverage": True,
    },
    {
        "plan_name": "BCBS Medicare Essentials (HMO)",
        "plan_id": "H7917-025",
        "monthly_premium": 0.00,
        "annual_deductible": 300.00,
        "out_of_pocket_max": 4800.00,
        "star_rating": 4.0,
        "plan_type": "HMO",
        "drug_coverage": True,
    },
    {
        "plan_name": "Wellcare Value Script (HMO)",
        "plan_id": "H1032-064",
        "monthly_premium": 0.00,
        "annual_deductible": 0.00,
        "out_of_pocket_max": 4000.00,
        "star_rating": 3.5,
        "plan_type": "HMO",
        "drug_coverage": True,
    },
    {
        "plan_name": "Wellcare No Premium (HMO)",
        "plan_id": "H1032-070",
        "monthly_premium": 0.00,
        "annual_deductible": 500.00,
        "out_of_pocket_max": 5500.00,
        "star_rating": 3.0,
        "plan_type": "HMO",
        "drug_coverage": False,
    },
    {
        "plan_name": "Kaiser Permanente Senior Advantage (HMO)",
        "plan_id": "H0524-001",
        "monthly_premium": 15.00,
        "annual_deductible": 0.00,
        "out_of_pocket_max": 3200.00,
        "star_rating": 5.0,
        "plan_type": "HMO",
        "drug_coverage": True,
    },
    {
        "plan_name": "Molina Medicare Complete Care (HMO)",
        "plan_id": "H9622-005",
        "monthly_premium": 0.00,
        "annual_deductible": 0.00,
        "out_of_pocket_max": 3800.00,
        "star_rating": 3.5,
        "plan_type": "HMO",
        "drug_coverage": True,
    },
    {
        "plan_name": "Anthem MediBlue Plus (PPO)",
        "plan_id": "H3952-018",
        "monthly_premium": 89.00,
        "annual_deductible": 0.00,
        "out_of_pocket_max": 5200.00,
        "star_rating": 4.0,
        "plan_type": "PPO",
        "drug_coverage": True,
    },
    {
        "plan_name": "Centene Ambetter Medicare (HMO)",
        "plan_id": "H6105-012",
        "monthly_premium": 20.00,
        "annual_deductible": 200.00,
        "out_of_pocket_max": 4600.00,
        "star_rating": 3.0,
        "plan_type": "HMO",
        "drug_coverage": True,
    },
    {
        "plan_name": "Devoted Health Medicare (HMO)",
        "plan_id": "H8230-003",
        "monthly_premium": 0.00,
        "annual_deductible": 0.00,
        "out_of_pocket_max": 3500.00,
        "star_rating": 4.5,
        "plan_type": "HMO",
        "drug_coverage": True,
    },
    {
        "plan_name": "Clover Health Preferred (PPO)",
        "plan_id": "H7322-008",
        "monthly_premium": 30.00,
        "annual_deductible": 100.00,
        "out_of_pocket_max": 4900.00,
        "star_rating": 3.5,
        "plan_type": "PPO",
        "drug_coverage": True,
    },
    {
        "plan_name": "Oscar Medicare Advantage (HMO)",
        "plan_id": "H8245-002",
        "monthly_premium": 175.00,
        "annual_deductible": 0.00,
        "out_of_pocket_max": 3000.00,
        "star_rating": 4.0,
        "plan_type": "HMO",
        "drug_coverage": True,
    },
]

ZIP_CODE_PLAN_INDICES: dict[str, list[int]] = {
    "10001": [0, 1, 2, 4, 5, 7, 9, 17, 18, 19],
    "90210": [0, 2, 3, 5, 8, 13, 14, 15, 18, 19],
    "60601": [1, 2, 4, 6, 7, 10, 11, 14, 16, 17],
    "33101": [0, 3, 4, 5, 8, 11, 14, 17, 18, 19],
    "77001": [1, 2, 6, 7, 9, 10, 12, 15, 16, 18],
    "85001": [0, 3, 5, 8, 11, 12, 13, 14, 16, 19],
    "98101": [2, 4, 5, 6, 9, 10, 13, 15, 17, 18],
    "30301": [0, 1, 3, 7, 8, 10, 11, 14, 16, 19],
    "02101": [1, 2, 5, 6, 9, 10, 13, 17, 18, 19],
    "75201": [0, 3, 4, 7, 8, 11, 12, 15, 16, 18],
}


class MockCMSFetcher:
    def fetch_plans(self, zip_code: str) -> list[dict]:
        if zip_code in ZIP_CODE_PLAN_INDICES:
            indices = ZIP_CODE_PLAN_INDICES[zip_code]
            return [ALL_PLANS[i].copy() for i in indices]

        rng = random.Random(int(zip_code))
        indices = rng.sample(range(len(ALL_PLANS)), k=min(8, len(ALL_PLANS)))
        return [ALL_PLANS[i].copy() for i in indices]


class RealCMSFetcher:
    """CMSFetcher that uses the SQLite database with fallback to mock data."""

    def __init__(self, db_path: str | None = None):
        from healthflow.data.plan_database import PlanDatabase

        kwargs = {"db_path": db_path} if db_path else {}
        self.db = PlanDatabase(**kwargs)
        self._mock_fallback = MockCMSFetcher()

    def fetch_plans(self, zip_code: str) -> list[dict]:
        if self.db.is_available():
            plans = self.db.search_plans(zip_code)
            if plans:
                return plans
        # Fallback to mock data if DB not available or no results for this zip
        return self._mock_fallback.fetch_plans(zip_code)
