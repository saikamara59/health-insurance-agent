"""
Integration tests for real health data: seed script, plan/drug databases,
RealCMSFetcher, and CostEstimator.

These tests use the existing healthflow_data.db at the project root.
If the file does not exist they run the seed script to create it.
"""

import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = PROJECT_ROOT / "healthflow_data.db"


# ---------------------------------------------------------------------------
# 1. Seed script creates the database
# ---------------------------------------------------------------------------


def test_seed_script_creates_database():
    """Running refresh_data.py --seed-only must produce healthflow_data.db."""
    seed_script = PROJECT_ROOT / "scripts" / "refresh_data.py"
    result = subprocess.run(
        [sys.executable, str(seed_script), "--seed-only"],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
    )
    assert result.returncode == 0, (
        f"seed script failed (rc={result.returncode}):\n{result.stderr}"
    )
    assert DB_PATH.exists(), "healthflow_data.db was not created by the seed script"


# ---------------------------------------------------------------------------
# 2. PlanDatabase queries
# ---------------------------------------------------------------------------


def test_plan_database_search_zip_10001():
    """PlanDatabase.search_plans for zip 10001 must return at least one plan
    with the expected fields."""
    from healthflow.data.plan_database import PlanDatabase

    db = PlanDatabase(db_path=DB_PATH)
    assert db.is_available(), "healthflow_data.db must exist for this test"

    plans = db.search_plans("10001")
    assert len(plans) > 0, "Expected at least one plan for zip 10001"

    required_fields = {
        "plan_name",
        "plan_id",
        "monthly_premium",
        "annual_deductible",
        "out_of_pocket_max",
        "star_rating",
        "plan_type",
        "drug_coverage",
    }
    for plan in plans:
        missing = required_fields - set(plan.keys())
        assert not missing, f"Plan missing fields: {missing}"


# ---------------------------------------------------------------------------
# 3. DrugDatabase queries
# ---------------------------------------------------------------------------


def test_drug_database_search_metformin():
    """DrugDatabase.search_drug('Metformin') must return a non-None result."""
    from healthflow.data.drug_database import DrugDatabase

    db = DrugDatabase(db_path=DB_PATH)
    assert db.is_available(), "healthflow_data.db must exist for this test"

    result = db.search_drug("Metformin")
    assert result is not None, "Expected a result for 'Metformin'"

    required_fields = {"name", "tier", "copay_hmo", "copay_ppo"}
    missing = required_fields - set(result.keys())
    assert not missing, f"Drug result missing fields: {missing}"


# ---------------------------------------------------------------------------
# 4. RealCMSFetcher returns real data
# ---------------------------------------------------------------------------


def test_real_cms_fetcher_returns_plans_for_zip_10001():
    """RealCMSFetcher.fetch_plans('10001') must return plans with required fields."""
    from healthflow.tools.cms_fetcher import RealCMSFetcher

    fetcher = RealCMSFetcher(db_path=str(DB_PATH))
    plans = fetcher.fetch_plans("10001")
    assert len(plans) > 0, "Expected at least one plan from RealCMSFetcher for 10001"

    required_fields = {"plan_name", "plan_id", "monthly_premium"}
    for plan in plans:
        missing = required_fields - set(plan.keys())
        assert not missing, f"Plan missing required fields: {missing}"


# ---------------------------------------------------------------------------
# 5. CostEstimator uses real drug data
# ---------------------------------------------------------------------------


def test_cost_estimator_metformin_returns_result():
    """CostEstimator.estimate for 'Metformin' must return a non-None result."""
    from healthflow.tools.cost_estimator import CostEstimator

    estimator = CostEstimator(db_path=str(DB_PATH))
    result = estimator.estimate("Metformin", "medication", "HMO")
    assert result is not None, "CostEstimator.estimate returned None for 'Metformin'"
    assert "item_name" in result, "Result missing 'item_name'"
    assert "estimated_cost" in result, "Result missing 'estimated_cost'"
