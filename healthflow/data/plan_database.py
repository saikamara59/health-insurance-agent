import os
import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "healthflow_data.db"


class PlanDatabase:
    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)

    def is_available(self) -> bool:
        return self.db_path.exists()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _row_to_plan_dict(self, row: sqlite3.Row) -> dict:
        return {
            "plan_name": row["plan_name"],
            "plan_id": row["plan_id"],
            "monthly_premium": row["monthly_premium"],
            "annual_deductible": row["annual_deductible"],
            "out_of_pocket_max": row["out_of_pocket_max"],
            "star_rating": row["star_rating"],
            "plan_type": row["plan_type"],
            "drug_coverage": bool(row["drug_coverage"]),
        }

    def search_plans(self, zip_code: str) -> list[dict]:
        if not self.is_available():
            return []
        conn = self._connect()
        try:
            cursor = conn.execute(
                """
                SELECT p.plan_id, p.plan_name, p.plan_type, p.monthly_premium,
                       p.annual_deductible, p.out_of_pocket_max, p.star_rating,
                       p.drug_coverage
                FROM plans p
                JOIN plan_zips pz ON p.plan_id = pz.plan_id
                WHERE pz.zip_code = ?
                ORDER BY p.star_rating DESC, p.monthly_premium ASC
                """,
                (zip_code,),
            )
            return [self._row_to_plan_dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def search_plans_by_state(self, state: str) -> list[dict]:
        if not self.is_available():
            return []
        conn = self._connect()
        try:
            cursor = conn.execute(
                """
                SELECT plan_id, plan_name, plan_type, monthly_premium,
                       annual_deductible, out_of_pocket_max, star_rating,
                       drug_coverage
                FROM plans
                WHERE state = ?
                ORDER BY star_rating DESC, monthly_premium ASC
                """,
                (state.upper(),),
            )
            return [self._row_to_plan_dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_plan(self, plan_id: str) -> dict | None:
        if not self.is_available():
            return None
        conn = self._connect()
        try:
            cursor = conn.execute(
                """
                SELECT plan_id, plan_name, plan_type, monthly_premium,
                       annual_deductible, out_of_pocket_max, star_rating,
                       drug_coverage
                FROM plans
                WHERE plan_id = ?
                """,
                (plan_id,),
            )
            row = cursor.fetchone()
            return self._row_to_plan_dict(row) if row else None
        finally:
            conn.close()
