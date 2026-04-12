import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "healthflow_data.db"


class DrugDatabase:
    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)

    def is_available(self) -> bool:
        return self.db_path.exists()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _row_to_drug_dict(self, row: sqlite3.Row) -> dict:
        return {
            "name": row["name"],
            "generic_name": row["generic_name"],
            "brand_name": row["brand_name"],
            "ndc": row["ndc"],
            "dosage_form": row["dosage_form"],
            "tier": row["tier_generic"],
            "copay_hmo": row["copay_hmo"],
            "copay_ppo": row["copay_ppo"],
            "prior_auth": bool(row["prior_auth"]),
            "quantity_limit": row["quantity_limit"],
        }

    def search_drug(self, name: str) -> dict | None:
        if not self.is_available():
            return None
        conn = self._connect()
        try:
            # Exact match first (case-insensitive)
            cursor = conn.execute(
                "SELECT * FROM drugs WHERE LOWER(name) = LOWER(?)", (name,)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_drug_dict(row)

            # Try generic_name exact match
            cursor = conn.execute(
                "SELECT * FROM drugs WHERE LOWER(generic_name) = LOWER(?)", (name,)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_drug_dict(row)

            # Try brand_name exact match
            cursor = conn.execute(
                "SELECT * FROM drugs WHERE LOWER(brand_name) = LOWER(?)", (name,)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_drug_dict(row)

            # Fuzzy match with LIKE
            cursor = conn.execute(
                "SELECT * FROM drugs WHERE name LIKE ? OR generic_name LIKE ? OR brand_name LIKE ?",
                (f"%{name}%", f"%{name}%", f"%{name}%"),
            )
            row = cursor.fetchone()
            return self._row_to_drug_dict(row) if row else None
        finally:
            conn.close()

    def get_tier(self, drug_name: str) -> str | None:
        drug = self.search_drug(drug_name)
        return drug["tier"] if drug else None

    def get_copay(self, drug_name: str, plan_type: str) -> float | None:
        drug = self.search_drug(drug_name)
        if drug is None:
            return None
        key = "copay_hmo" if plan_type.upper() == "HMO" else "copay_ppo"
        return drug[key]

    def list_drugs(self, limit: int = 100) -> list[dict]:
        if not self.is_available():
            return []
        conn = self._connect()
        try:
            cursor = conn.execute(
                "SELECT * FROM drugs ORDER BY name LIMIT ?", (limit,)
            )
            return [self._row_to_drug_dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
