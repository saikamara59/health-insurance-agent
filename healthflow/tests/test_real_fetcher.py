import sqlite3
from pathlib import Path

import pytest

from healthflow.tools.cms_fetcher import RealCMSFetcher, MockCMSFetcher


@pytest.fixture
def seed_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "healthflow_data.db"
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
             45.00, 0.00, 5900.00, 4.0, 1, 'NY');

        INSERT INTO plan_zips VALUES
            ('H3312-034', '10001'),
            ('H5521-017', '10001');
        """
    )
    conn.close()
    return db_path


def test_real_fetcher_returns_plans_from_db(seed_db: Path):
    fetcher = RealCMSFetcher(db_path=str(seed_db))
    plans = fetcher.fetch_plans("10001")
    assert len(plans) == 2
    assert all("plan_name" in p for p in plans)
    assert all("plan_id" in p for p in plans)
    assert all("monthly_premium" in p for p in plans)
    assert all("annual_deductible" in p for p in plans)
    assert all("out_of_pocket_max" in p for p in plans)
    assert all("star_rating" in p for p in plans)
    assert all("plan_type" in p for p in plans)
    assert all("drug_coverage" in p for p in plans)


def test_real_fetcher_falls_back_to_mock_when_db_missing(tmp_path: Path):
    fetcher = RealCMSFetcher(db_path=str(tmp_path / "nonexistent.db"))
    plans = fetcher.fetch_plans("10001")
    # Should get mock data (MockCMSFetcher returns plans for 10001)
    assert len(plans) > 0
    assert all("plan_name" in p for p in plans)


def test_real_fetcher_falls_back_for_unknown_zip(seed_db: Path):
    fetcher = RealCMSFetcher(db_path=str(seed_db))
    plans = fetcher.fetch_plans("99999")
    # DB has no plans for 99999, should fall back to mock
    assert len(plans) > 0


def test_real_fetcher_matches_protocol_format(seed_db: Path):
    fetcher = RealCMSFetcher(db_path=str(seed_db))
    plans = fetcher.fetch_plans("10001")
    plan = plans[0]
    # Verify exact keys match MockCMSFetcher output format
    mock_fetcher = MockCMSFetcher()
    mock_plans = mock_fetcher.fetch_plans("10001")
    mock_keys = set(mock_plans[0].keys())
    real_keys = set(plan.keys())
    assert real_keys == mock_keys


def test_real_fetcher_drug_coverage_is_bool(seed_db: Path):
    fetcher = RealCMSFetcher(db_path=str(seed_db))
    plans = fetcher.fetch_plans("10001")
    for plan in plans:
        assert isinstance(plan["drug_coverage"], bool)
