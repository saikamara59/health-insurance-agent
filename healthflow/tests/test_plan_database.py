import sqlite3
from pathlib import Path

import pytest

from healthflow.data.plan_database import PlanDatabase


@pytest.fixture
def test_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "test_healthflow_data.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """
        CREATE TABLE plans (
            plan_id TEXT PRIMARY KEY,
            plan_name TEXT NOT NULL,
            organization TEXT,
            plan_type TEXT NOT NULL,
            monthly_premium REAL NOT NULL,
            annual_deductible REAL NOT NULL,
            out_of_pocket_max REAL NOT NULL,
            star_rating REAL NOT NULL,
            drug_coverage INTEGER NOT NULL,
            state TEXT
        );

        CREATE TABLE plan_zips (
            plan_id TEXT NOT NULL,
            zip_code TEXT NOT NULL,
            FOREIGN KEY (plan_id) REFERENCES plans(plan_id)
        );

        CREATE INDEX idx_plan_zips_zip ON plan_zips(zip_code);

        INSERT INTO plans VALUES
            ('H3312-034', 'Aetna Medicare Eagle Plus (HMO)', 'Aetna', 'HMO',
             0.00, 250.00, 4500.00, 4.5, 1, 'NY'),
            ('H5521-017', 'Aetna Medicare Value (PPO)', 'Aetna', 'PPO',
             45.00, 0.00, 5900.00, 4.0, 1, 'NY'),
            ('H1036-200', 'Humana Gold Plus (HMO-POS)', 'Humana', 'HMO',
             0.00, 0.00, 3400.00, 4.5, 1, 'FL');

        INSERT INTO plan_zips VALUES
            ('H3312-034', '10001'),
            ('H5521-017', '10001'),
            ('H1036-200', '33101'),
            ('H3312-034', '33101');
        """
    )
    conn.close()
    return db_path


def test_is_available_true(test_db: Path):
    db = PlanDatabase(db_path=test_db)
    assert db.is_available() is True


def test_is_available_false(tmp_path: Path):
    db = PlanDatabase(db_path=tmp_path / "nonexistent.db")
    assert db.is_available() is False


def test_search_plans_known_zip(test_db: Path):
    db = PlanDatabase(db_path=test_db)
    plans = db.search_plans("10001")
    assert len(plans) == 2
    plan_ids = {p["plan_id"] for p in plans}
    assert "H3312-034" in plan_ids
    assert "H5521-017" in plan_ids
    # Verify output format matches CMSFetcher protocol
    plan = plans[0]
    assert "plan_name" in plan
    assert "plan_id" in plan
    assert "monthly_premium" in plan
    assert "annual_deductible" in plan
    assert "out_of_pocket_max" in plan
    assert "star_rating" in plan
    assert "plan_type" in plan
    assert "drug_coverage" in plan
    assert isinstance(plan["drug_coverage"], bool)


def test_search_plans_unknown_zip(test_db: Path):
    db = PlanDatabase(db_path=test_db)
    plans = db.search_plans("99999")
    assert plans == []


def test_search_plans_db_not_available(tmp_path: Path):
    db = PlanDatabase(db_path=tmp_path / "nonexistent.db")
    plans = db.search_plans("10001")
    assert plans == []


def test_get_plan_found(test_db: Path):
    db = PlanDatabase(db_path=test_db)
    plan = db.get_plan("H3312-034")
    assert plan is not None
    assert plan["plan_name"] == "Aetna Medicare Eagle Plus (HMO)"
    assert plan["plan_type"] == "HMO"
    assert plan["monthly_premium"] == 0.00
    assert plan["drug_coverage"] is True


def test_get_plan_not_found(test_db: Path):
    db = PlanDatabase(db_path=test_db)
    assert db.get_plan("XXXXX-999") is None


def test_search_plans_by_state(test_db: Path):
    db = PlanDatabase(db_path=test_db)
    plans = db.search_plans_by_state("NY")
    assert len(plans) == 2
    plans_fl = db.search_plans_by_state("FL")
    assert len(plans_fl) == 1
    assert plans_fl[0]["plan_id"] == "H1036-200"


def test_search_plans_ordered_by_rating_then_premium(test_db: Path):
    db = PlanDatabase(db_path=test_db)
    plans = db.search_plans("10001")
    # H3312-034 (4.5 stars, $0) should come before H5521-017 (4.0 stars, $45)
    assert plans[0]["plan_id"] == "H3312-034"
    assert plans[1]["plan_id"] == "H5521-017"
