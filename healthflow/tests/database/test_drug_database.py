import sqlite3
from pathlib import Path

import pytest

from healthflow.data.drug_database import DrugDatabase


@pytest.fixture
def drug_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "test_healthflow_data.db"
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

        CREATE INDEX idx_drugs_name ON drugs(name);

        INSERT INTO drugs (name, generic_name, brand_name, ndc, dosage_form,
                           tier_generic, copay_hmo, copay_ppo, prior_auth, quantity_limit)
        VALUES
            ('Metformin', 'metformin hydrochloride', 'Glucophage', '00087-6060-05',
             'Tablet', 'Tier 1 - Generic', 5.0, 10.0, 0, '90-day supply'),
            ('Eliquis', 'apixaban', 'Eliquis', '00003-0893-21',
             'Tablet', 'Tier 3 - Non-Preferred', 47.0, 95.0, 1, '30-day supply'),
            ('Ozempic', 'semaglutide', 'Ozempic', '00169-4130-12',
             'Injection', 'Tier 4 - Specialty', 100.0, 150.0, 1, '30-day supply'),
            ('Lisinopril', 'lisinopril', 'Prinivil', '00006-0019-54',
             'Tablet', 'Tier 1 - Generic', 3.0, 8.0, 0, '90-day supply');
        """
    )
    conn.close()
    return db_path


def test_is_available_true(drug_db: Path):
    db = DrugDatabase(db_path=drug_db)
    assert db.is_available() is True


def test_is_available_false(tmp_path: Path):
    db = DrugDatabase(db_path=tmp_path / "nonexistent.db")
    assert db.is_available() is False


def test_search_drug_exact_match(drug_db: Path):
    db = DrugDatabase(db_path=drug_db)
    result = db.search_drug("Metformin")
    assert result is not None
    assert result["name"] == "Metformin"
    assert result["tier"] == "Tier 1 - Generic"
    assert result["copay_hmo"] == 5.0
    assert result["copay_ppo"] == 10.0
    assert result["prior_auth"] is False
    assert result["quantity_limit"] == "90-day supply"


def test_search_drug_case_insensitive(drug_db: Path):
    db = DrugDatabase(db_path=drug_db)
    result = db.search_drug("metformin")
    assert result is not None
    assert result["name"] == "Metformin"


def test_search_drug_by_generic_name(drug_db: Path):
    db = DrugDatabase(db_path=drug_db)
    result = db.search_drug("apixaban")
    assert result is not None
    assert result["name"] == "Eliquis"


def test_search_drug_by_brand_name(drug_db: Path):
    db = DrugDatabase(db_path=drug_db)
    result = db.search_drug("Glucophage")
    assert result is not None
    assert result["name"] == "Metformin"


def test_search_drug_fuzzy_match(drug_db: Path):
    db = DrugDatabase(db_path=drug_db)
    result = db.search_drug("semaglut")
    assert result is not None
    assert result["name"] == "Ozempic"


def test_search_drug_not_found(drug_db: Path):
    db = DrugDatabase(db_path=drug_db)
    assert db.search_drug("NonexistentDrug") is None


def test_search_drug_db_not_available(tmp_path: Path):
    db = DrugDatabase(db_path=tmp_path / "nonexistent.db")
    assert db.search_drug("Metformin") is None


def test_get_copay_hmo(drug_db: Path):
    db = DrugDatabase(db_path=drug_db)
    copay = db.get_copay("Metformin", "HMO")
    assert copay == 5.0


def test_get_copay_ppo(drug_db: Path):
    db = DrugDatabase(db_path=drug_db)
    copay = db.get_copay("Eliquis", "PPO")
    assert copay == 95.0


def test_get_copay_unknown_drug(drug_db: Path):
    db = DrugDatabase(db_path=drug_db)
    assert db.get_copay("FakeDrug", "HMO") is None


def test_get_tier(drug_db: Path):
    db = DrugDatabase(db_path=drug_db)
    assert db.get_tier("Ozempic") == "Tier 4 - Specialty"
    assert db.get_tier("Lisinopril") == "Tier 1 - Generic"


def test_list_drugs(drug_db: Path):
    db = DrugDatabase(db_path=drug_db)
    drugs = db.list_drugs()
    assert len(drugs) == 4
    # Ordered alphabetically by name
    assert drugs[0]["name"] == "Eliquis"


def test_drug_dict_format(drug_db: Path):
    db = DrugDatabase(db_path=drug_db)
    result = db.search_drug("Eliquis")
    assert result is not None
    # Verify all expected keys present
    expected_keys = {"name", "generic_name", "brand_name", "ndc", "dosage_form",
                     "tier", "copay_hmo", "copay_ppo", "prior_auth", "quantity_limit"}
    assert set(result.keys()) == expected_keys
    assert isinstance(result["prior_auth"], bool)
    assert result["prior_auth"] is True
