from healthflow.tools.plan_parser import PlanParser


SAMPLE_PLANS = [
    {
        "plan_name": "Plan A",
        "plan_id": "H0001-001",
        "monthly_premium": 0.00,
        "annual_deductible": 0.00,
        "out_of_pocket_max": 3000.00,
        "star_rating": 5.0,
        "plan_type": "HMO",
        "drug_coverage": True,
    },
    {
        "plan_name": "Plan B",
        "plan_id": "H0001-002",
        "monthly_premium": 100.00,
        "annual_deductible": 500.00,
        "out_of_pocket_max": 8000.00,
        "star_rating": 3.0,
        "plan_type": "PPO",
        "drug_coverage": False,
    },
    {
        "plan_name": "Plan C",
        "plan_id": "H0001-003",
        "monthly_premium": 50.00,
        "annual_deductible": 200.00,
        "out_of_pocket_max": 5000.00,
        "star_rating": 4.0,
        "plan_type": "HMO",
        "drug_coverage": True,
    },
    {
        "plan_name": "Plan D",
        "plan_id": "H0001-004",
        "monthly_premium": 25.00,
        "annual_deductible": 100.00,
        "out_of_pocket_max": 4000.00,
        "star_rating": 4.5,
        "plan_type": "PPO",
        "drug_coverage": True,
    },
    {
        "plan_name": "Plan E",
        "plan_id": "H0001-005",
        "monthly_premium": 150.00,
        "annual_deductible": 400.00,
        "out_of_pocket_max": 7000.00,
        "star_rating": 2.5,
        "plan_type": "HMO",
        "drug_coverage": True,
    },
    {
        "plan_name": "Plan F",
        "plan_id": "H0001-006",
        "monthly_premium": 75.00,
        "annual_deductible": 300.00,
        "out_of_pocket_max": 6000.00,
        "star_rating": 3.5,
        "plan_type": "PPO",
        "drug_coverage": True,
    },
]


def test_parse_returns_plan_summaries():
    parser = PlanParser()
    plans = parser.parse_and_rank(SAMPLE_PLANS, "medium")
    assert len(plans) == 5
    for plan in plans:
        assert hasattr(plan, "plan_name")
        assert hasattr(plan, "monthly_premium")
        assert hasattr(plan, "star_rating")


def test_parse_returns_max_5():
    parser = PlanParser()
    plans = parser.parse_and_rank(SAMPLE_PLANS, "low")
    assert len(plans) <= 5


def test_low_income_prefers_low_premium():
    parser = PlanParser()
    plans = parser.parse_and_rank(SAMPLE_PLANS, "low")
    assert plans[0].plan_id == "H0001-001"


def test_high_income_prefers_high_star():
    parser = PlanParser()
    plans = parser.parse_and_rank(SAMPLE_PLANS, "high")
    assert plans[0].plan_id == "H0001-001"


def test_parse_fewer_than_5_plans():
    parser = PlanParser()
    plans = parser.parse_and_rank(SAMPLE_PLANS[:3], "medium")
    assert len(plans) == 3
