MEDICATIONS = [
    {"name": "Metformin", "tier": "Tier 1 - Generic", "copay_hmo": 5.0, "copay_ppo": 10.0, "prior_auth": False, "quantity_limit": "90-day supply"},
    {"name": "Lisinopril", "tier": "Tier 1 - Generic", "copay_hmo": 3.0, "copay_ppo": 8.0, "prior_auth": False, "quantity_limit": "90-day supply"},
    {"name": "Atorvastatin", "tier": "Tier 1 - Generic", "copay_hmo": 5.0, "copay_ppo": 10.0, "prior_auth": False, "quantity_limit": "90-day supply"},
    {"name": "Amlodipine", "tier": "Tier 1 - Generic", "copay_hmo": 3.0, "copay_ppo": 7.0, "prior_auth": False, "quantity_limit": "90-day supply"},
    {"name": "Omeprazole", "tier": "Tier 1 - Generic", "copay_hmo": 5.0, "copay_ppo": 10.0, "prior_auth": False, "quantity_limit": "90-day supply"},
    {"name": "Levothyroxine", "tier": "Tier 1 - Generic", "copay_hmo": 5.0, "copay_ppo": 10.0, "prior_auth": False, "quantity_limit": "90-day supply"},
    {"name": "Albuterol", "tier": "Tier 2 - Preferred Brand", "copay_hmo": 25.0, "copay_ppo": 35.0, "prior_auth": False, "quantity_limit": "30-day supply"},
    {"name": "Gabapentin", "tier": "Tier 1 - Generic", "copay_hmo": 5.0, "copay_ppo": 10.0, "prior_auth": False, "quantity_limit": "90-day supply"},
    {"name": "Losartan", "tier": "Tier 1 - Generic", "copay_hmo": 3.0, "copay_ppo": 8.0, "prior_auth": False, "quantity_limit": "90-day supply"},
    {"name": "Hydrochlorothiazide", "tier": "Tier 1 - Generic", "copay_hmo": 3.0, "copay_ppo": 7.0, "prior_auth": False, "quantity_limit": "90-day supply"},
    {"name": "Sertraline", "tier": "Tier 1 - Generic", "copay_hmo": 5.0, "copay_ppo": 10.0, "prior_auth": False, "quantity_limit": "90-day supply"},
    {"name": "Montelukast", "tier": "Tier 1 - Generic", "copay_hmo": 5.0, "copay_ppo": 12.0, "prior_auth": False, "quantity_limit": "30-day supply"},
    {"name": "Pantoprazole", "tier": "Tier 1 - Generic", "copay_hmo": 5.0, "copay_ppo": 10.0, "prior_auth": False, "quantity_limit": "90-day supply"},
    {"name": "Escitalopram", "tier": "Tier 1 - Generic", "copay_hmo": 5.0, "copay_ppo": 10.0, "prior_auth": False, "quantity_limit": "90-day supply"},
    {"name": "Rosuvastatin", "tier": "Tier 1 - Generic", "copay_hmo": 5.0, "copay_ppo": 12.0, "prior_auth": False, "quantity_limit": "90-day supply"},
    {"name": "Tamsulosin", "tier": "Tier 1 - Generic", "copay_hmo": 5.0, "copay_ppo": 10.0, "prior_auth": False, "quantity_limit": "90-day supply"},
    {"name": "Meloxicam", "tier": "Tier 1 - Generic", "copay_hmo": 3.0, "copay_ppo": 8.0, "prior_auth": False, "quantity_limit": "30-day supply"},
    {"name": "Glipizide", "tier": "Tier 1 - Generic", "copay_hmo": 5.0, "copay_ppo": 10.0, "prior_auth": False, "quantity_limit": "90-day supply"},
    {"name": "Insulin Glargine", "tier": "Tier 3 - Non-Preferred", "copay_hmo": 47.0, "copay_ppo": 75.0, "prior_auth": False, "quantity_limit": "30-day supply"},
    {"name": "Eliquis", "tier": "Tier 3 - Non-Preferred", "copay_hmo": 47.0, "copay_ppo": 95.0, "prior_auth": True, "quantity_limit": "30-day supply"},
    {"name": "Jardiance", "tier": "Tier 3 - Non-Preferred", "copay_hmo": 47.0, "copay_ppo": 90.0, "prior_auth": True, "quantity_limit": "30-day supply"},
    {"name": "Ozempic", "tier": "Tier 4 - Specialty", "copay_hmo": 100.0, "copay_ppo": 150.0, "prior_auth": True, "quantity_limit": "30-day supply"},
    {"name": "Xarelto", "tier": "Tier 3 - Non-Preferred", "copay_hmo": 47.0, "copay_ppo": 95.0, "prior_auth": True, "quantity_limit": "30-day supply"},
    {"name": "Humira", "tier": "Tier 4 - Specialty", "copay_hmo": 150.0, "copay_ppo": 250.0, "prior_auth": True, "quantity_limit": "30-day supply"},
    {"name": "Dupixent", "tier": "Tier 4 - Specialty", "copay_hmo": 150.0, "copay_ppo": 275.0, "prior_auth": True, "quantity_limit": "30-day supply"},
    {"name": "Entresto", "tier": "Tier 3 - Non-Preferred", "copay_hmo": 47.0, "copay_ppo": 90.0, "prior_auth": True, "quantity_limit": "30-day supply"},
    {"name": "Tresiba", "tier": "Tier 3 - Non-Preferred", "copay_hmo": 47.0, "copay_ppo": 80.0, "prior_auth": False, "quantity_limit": "30-day supply"},
    {"name": "Farxiga", "tier": "Tier 3 - Non-Preferred", "copay_hmo": 47.0, "copay_ppo": 85.0, "prior_auth": True, "quantity_limit": "30-day supply"},
    {"name": "Trulicity", "tier": "Tier 3 - Non-Preferred", "copay_hmo": 47.0, "copay_ppo": 95.0, "prior_auth": True, "quantity_limit": "30-day supply"},
    {"name": "Warfarin", "tier": "Tier 1 - Generic", "copay_hmo": 3.0, "copay_ppo": 7.0, "prior_auth": False, "quantity_limit": "90-day supply"},
]

PROCEDURES = [
    {"name": "Annual physical", "category": "preventive", "cost_hmo": 0.0, "cost_ppo": 0.0},
    {"name": "Blood work", "category": "diagnostic", "cost_hmo": 10.0, "cost_ppo": 20.0},
    {"name": "X-ray", "category": "diagnostic", "cost_hmo": 30.0, "cost_ppo": 50.0},
    {"name": "MRI", "category": "diagnostic", "cost_hmo": 150.0, "cost_ppo": 250.0},
    {"name": "CT scan", "category": "diagnostic", "cost_hmo": 125.0, "cost_ppo": 200.0},
    {"name": "ER visit", "category": "inpatient", "cost_hmo": 150.0, "cost_ppo": 200.0},
    {"name": "Urgent care", "category": "outpatient", "cost_hmo": 25.0, "cost_ppo": 50.0},
    {"name": "Physical therapy", "category": "outpatient", "cost_hmo": 20.0, "cost_ppo": 40.0},
    {"name": "Specialist office visit", "category": "specialist", "cost_hmo": 40.0, "cost_ppo": 50.0},
    {"name": "Colonoscopy", "category": "preventive", "cost_hmo": 0.0, "cost_ppo": 0.0},
    {"name": "Mammogram", "category": "preventive", "cost_hmo": 0.0, "cost_ppo": 0.0},
    {"name": "Dental cleaning", "category": "outpatient", "cost_hmo": 25.0, "cost_ppo": 35.0},
    {"name": "Vision exam", "category": "outpatient", "cost_hmo": 15.0, "cost_ppo": 25.0},
    {"name": "Hearing test", "category": "diagnostic", "cost_hmo": 20.0, "cost_ppo": 35.0},
    {"name": "Mental health visit", "category": "specialist", "cost_hmo": 25.0, "cost_ppo": 40.0},
    {"name": "Lab panel", "category": "diagnostic", "cost_hmo": 15.0, "cost_ppo": 25.0},
    {"name": "EKG", "category": "diagnostic", "cost_hmo": 20.0, "cost_ppo": 35.0},
    {"name": "Ultrasound", "category": "diagnostic", "cost_hmo": 50.0, "cost_ppo": 80.0},
    {"name": "Minor surgery", "category": "outpatient", "cost_hmo": 250.0, "cost_ppo": 400.0},
    {"name": "Inpatient day", "category": "inpatient", "cost_hmo": 300.0, "cost_ppo": 500.0},
]


def _fuzzy_match(query: str, candidates: list[dict]) -> dict | None:
    query_lower = query.lower().strip()
    for item in candidates:
        if item["name"].lower() == query_lower:
            return item
    for item in candidates:
        if query_lower in item["name"].lower() or item["name"].lower() in query_lower:
            return item
    return None


class CostEstimator:
    def __init__(self, db_path: str | None = None):
        self._drug_db = None
        self._db_path = db_path

    @property
    def drug_db(self):
        if self._drug_db is None:
            from healthflow.data.drug_database import DrugDatabase

            kwargs = {"db_path": self._db_path} if self._db_path else {}
            self._drug_db = DrugDatabase(**kwargs)
        return self._drug_db

    def estimate(
        self, item_name: str, item_type: str, plan_type: str
    ) -> dict | None:
        if item_type == "medication":
            # Try real database first
            if self.drug_db.is_available():
                db_result = self.drug_db.search_drug(item_name)
                if db_result is not None:
                    copay_key = "copay_hmo" if plan_type == "HMO" else "copay_ppo"
                    return {
                        "item_name": db_result["name"],
                        "item_type": "medication",
                        "estimated_cost": db_result[copay_key],
                        "cost_details": {
                            "formulary_tier": db_result["tier"],
                            "copay": db_result[copay_key],
                            "coinsurance_pct": None,
                            "prior_auth_required": db_result["prior_auth"],
                            "quantity_limit": db_result["quantity_limit"],
                        },
                    }
            # Fallback to hardcoded MEDICATIONS
            match = _fuzzy_match(item_name, MEDICATIONS)
            if match is None:
                return None
            copay_key = "copay_hmo" if plan_type == "HMO" else "copay_ppo"
            return {
                "item_name": match["name"],
                "item_type": "medication",
                "estimated_cost": match[copay_key],
                "cost_details": {
                    "formulary_tier": match["tier"],
                    "copay": match[copay_key],
                    "coinsurance_pct": None,
                    "prior_auth_required": match["prior_auth"],
                    "quantity_limit": match["quantity_limit"],
                },
            }
        elif item_type == "procedure":
            match = _fuzzy_match(item_name, PROCEDURES)
            if match is None:
                return None
            cost_key = "cost_hmo" if plan_type == "HMO" else "cost_ppo"
            return {
                "item_name": match["name"],
                "item_type": "procedure",
                "estimated_cost": match[cost_key],
                "cost_details": {
                    "formulary_tier": None,
                    "copay": match[cost_key],
                    "coinsurance_pct": None,
                    "prior_auth_required": False,
                    "quantity_limit": None,
                },
            }
        return None

    def estimate_multiple(
        self, items: list[str], item_type: str, plan_type: str
    ) -> dict[str, dict | None]:
        return {item: self.estimate(item, item_type, plan_type) for item in items}
