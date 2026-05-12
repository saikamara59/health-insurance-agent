import sqlite3
from pathlib import Path

import pytest

from healthflow.tools.cost_estimator import CostEstimator


@pytest.fixture
def drug_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "healthflow_data.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """
        CREATE TABLE drugs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            generic_name TEXT,
            brand_name TEXT,
            ndc TEXT,
            dosage_form TEXT,
            tier_generic TEXT NOT NULL,
            copay_hmo REAL NOT NULL,
            copay_ppo REAL NOT NULL,
            prior_auth INTEGER NOT NULL DEFAULT 0,
            quantity_limit TEXT
        );

        INSERT INTO drugs (name, generic_name, brand_name, ndc, dosage_form,
                           tier_generic, copay_hmo, copay_ppo, prior_auth, quantity_limit)
        VALUES
            ('Metformin', 'metformin hydrochloride', 'Glucophage', '00087-6060-05',
             'Tablet', 'Tier 1 - Generic', 5.0, 10.0, 0, '90-day supply'),
            ('Ozempic', 'semaglutide', 'Ozempic', '00169-4130-12',
             'Injection', 'Tier 4 - Specialty', 100.0, 150.0, 1, '30-day supply');
        """
    )
    conn.close()
    return db_path


def test_estimate_medication_from_db(drug_db: Path):
    estimator = CostEstimator(db_path=str(drug_db))
    result = estimator.estimate("Metformin", "medication", "HMO")
    assert result is not None
    assert result["item_name"] == "Metformin"
    assert result["item_type"] == "medication"
    assert result["estimated_cost"] == 5.0
    assert result["cost_details"]["formulary_tier"] == "Tier 1 - Generic"
    assert result["cost_details"]["copay"] == 5.0
    assert result["cost_details"]["prior_auth_required"] is False
    assert result["cost_details"]["quantity_limit"] == "90-day supply"


def test_estimate_medication_ppo_from_db(drug_db: Path):
    estimator = CostEstimator(db_path=str(drug_db))
    result = estimator.estimate("Ozempic", "medication", "PPO")
    assert result is not None
    assert result["estimated_cost"] == 150.0
    assert result["cost_details"]["prior_auth_required"] is True


def test_estimate_falls_back_to_hardcoded(drug_db: Path):
    estimator = CostEstimator(db_path=str(drug_db))
    # Albuterol is in MEDICATIONS but not in our test DB
    result = estimator.estimate("Albuterol", "medication", "HMO")
    assert result is not None
    assert result["item_name"] == "Albuterol"
    assert result["estimated_cost"] == 25.0


def test_estimate_no_db_uses_hardcoded(tmp_path: Path):
    estimator = CostEstimator(db_path=str(tmp_path / "nonexistent.db"))
    result = estimator.estimate("Metformin", "medication", "HMO")
    assert result is not None
    assert result["item_name"] == "Metformin"
    assert result["estimated_cost"] == 5.0


def test_estimate_procedure_unchanged(drug_db: Path):
    estimator = CostEstimator(db_path=str(drug_db))
    result = estimator.estimate("MRI", "procedure", "HMO")
    assert result is not None
    assert result["item_name"] == "MRI"
    assert result["estimated_cost"] == 150.0


def test_estimate_unknown_returns_none(drug_db: Path):
    estimator = CostEstimator(db_path=str(drug_db))
    assert estimator.estimate("FakeDrug123", "medication", "HMO") is None


def test_estimate_multiple_with_db(drug_db: Path):
    estimator = CostEstimator(db_path=str(drug_db))
    results = estimator.estimate_multiple(
        ["Metformin", "Ozempic", "MRI"], "medication", "HMO"
    )
    assert results["Metformin"] is not None
    assert results["Ozempic"] is not None
    assert results["MRI"] is None  # "MRI" is not a medication


def test_backward_compatible_no_args():
    """CostEstimator() with no args still works using hardcoded data."""
    estimator = CostEstimator()
    result = estimator.estimate("Lisinopril", "medication", "PPO")
    assert result is not None
    assert result["item_name"] == "Lisinopril"
    assert result["estimated_cost"] == 8.0
