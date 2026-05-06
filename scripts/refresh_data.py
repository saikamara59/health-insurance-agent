#!/usr/bin/env python3
"""
Refresh healthflow_data.db with CMS Medicare Advantage plan data and FDA drug data.

Usage:
    python scripts/refresh_data.py              # Download real data (with seed fallback)
    python scripts/refresh_data.py --seed-only  # Use curated seed data only (for CI/testing)

Output:
    healthflow_data.db in the project root directory.
"""

import argparse
import json
import logging
import os
import sqlite3
import sys
import time
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv

# Load .env so HUD_API_TOKEN (and any other vars) are visible. Existing process
# env wins — useful when CI passes secrets explicitly.
load_dotenv(override=False)

try:
    import httpx
except ImportError:
    httpx = None  # downloaders return None gracefully when httpx isn't installed

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

CACHE_DIR = Path.home() / ".cache" / "healthflow"


def _serialize_for_cache(obj):
    """Convert sets to sorted lists, recursively, so the result is JSON-safe."""
    if isinstance(obj, set):
        return sorted(obj)
    if isinstance(obj, dict):
        return {k: _serialize_for_cache(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialize_for_cache(v) for v in obj]
    return obj


def _load_or_fetch(key: str, ttl_days: int, fetch_fn, *, force: bool = False):
    """Read ~/.cache/healthflow/<key>.json if present and within TTL; else call fetch_fn().

    On a fetcher hit, the result is JSON-serialized (sets → sorted lists) and written through.
    Returns whatever fetch_fn returned, or — on a cache hit — the JSON-rehydrated equivalent.
    Sets in the original return value come back as lists; consumers must accept iterables.
    Returns None (and does not cache) if fetch_fn returns None.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = CACHE_DIR / f"{key}.json"

    if not force and cache_path.exists():
        age_seconds = time.time() - cache_path.stat().st_mtime
        if age_seconds < ttl_days * 86400:
            try:
                with cache_path.open() as fh:
                    return json.load(fh)
            except (json.JSONDecodeError, OSError) as e:
                logger.debug(f"Cache file {cache_path} unreadable ({e}); refetching.")
                cache_path.unlink(missing_ok=True)

    result = fetch_fn()
    if result is not None:
        try:
            with cache_path.open("w") as fh:
                json.dump(_serialize_for_cache(result), fh)
        except OSError as e:
            logger.warning(f"Failed to write cache {cache_path}: {e}")
    return result

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "healthflow_data.db"

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS plans (
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

CREATE TABLE IF NOT EXISTS plan_counties (
    plan_id TEXT NOT NULL,
    state TEXT NOT NULL,
    county TEXT NOT NULL,
    fips_code TEXT,
    FOREIGN KEY (plan_id) REFERENCES plans(plan_id)
);

CREATE TABLE IF NOT EXISTS plan_zips (
    plan_id TEXT NOT NULL,
    zip_code TEXT NOT NULL,
    FOREIGN KEY (plan_id) REFERENCES plans(plan_id)
);

CREATE INDEX IF NOT EXISTS idx_plan_zips_zip ON plan_zips(zip_code);
CREATE INDEX IF NOT EXISTS idx_plan_zips_plan ON plan_zips(plan_id);
CREATE INDEX IF NOT EXISTS idx_plan_counties_plan ON plan_counties(plan_id);
CREATE INDEX IF NOT EXISTS idx_plans_state ON plans(state);

CREATE TABLE IF NOT EXISTS drugs (
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

CREATE INDEX IF NOT EXISTS idx_drugs_name ON drugs(name);
CREATE INDEX IF NOT EXISTS idx_drugs_generic ON drugs(generic_name);
"""

# ---------------------------------------------------------------------------
# Seed Data — curated real plans and drugs for --seed-only / download fallback
# ---------------------------------------------------------------------------

SEED_PLANS = [
    # Aetna plans
    ("H3312-034", "Aetna Medicare Eagle Plus (HMO)", "Aetna", "HMO", 0.00, 250.00, 4500.00, 4.5, 1, "NY"),
    ("H5521-017", "Aetna Medicare Value (PPO)", "Aetna", "PPO", 45.00, 0.00, 5900.00, 4.0, 1, "NY"),
    ("H3312-041", "Aetna Medicare Premier (HMO)", "Aetna", "HMO", 65.00, 0.00, 3900.00, 4.5, 1, "NY"),
    ("H5521-022", "Aetna Medicare Select (PPO)", "Aetna", "PPO", 28.00, 150.00, 5200.00, 4.0, 1, "CA"),
    # Humana plans
    ("H1036-200", "Humana Gold Plus (HMO-POS)", "Humana", "HMO", 0.00, 0.00, 3400.00, 4.5, 1, "FL"),
    ("H1036-180", "Humana Choice (PPO)", "Humana", "PPO", 75.50, 200.00, 6700.00, 3.5, 1, "FL"),
    ("H1036-210", "Humana Honor (HMO)", "Humana", "HMO", 0.00, 0.00, 3200.00, 4.0, 1, "TX"),
    ("H1036-215", "Humana Value (PPO)", "Humana", "PPO", 32.00, 100.00, 5800.00, 3.5, 1, "TX"),
    # UnitedHealthcare plans
    ("H2228-050", "UHC Medicare Advantage Choice (PPO)", "UnitedHealthcare", "PPO", 25.00, 150.00, 5500.00, 4.0, 1, "NY"),
    ("H2228-063", "UHC Medicare Advantage Star (HMO)", "UnitedHealthcare", "HMO", 0.00, 0.00, 3900.00, 5.0, 1, "NY"),
    ("H2228-071", "UHC Dual Complete (HMO-SNP)", "UnitedHealthcare", "HMO", 0.00, 0.00, 3000.00, 4.0, 1, "IL"),
    ("H2228-080", "UHC Medicare Advantage Plus (HMO)", "UnitedHealthcare", "HMO", 15.00, 0.00, 4200.00, 4.5, 1, "CA"),
    ("H2228-085", "UHC Medicare Advantage Flex (PPO)", "UnitedHealthcare", "PPO", 55.00, 0.00, 5000.00, 4.0, 1, "FL"),
    # Cigna plans
    ("H5410-022", "Cigna Preferred Medicare (HMO)", "Cigna", "HMO", 35.00, 100.00, 4200.00, 4.0, 1, "IL"),
    ("H5410-038", "Cigna True Choice Medicare (PPO)", "Cigna", "PPO", 110.00, 0.00, 5000.00, 3.5, 1, "IL"),
    ("H5410-045", "Cigna Secure Medicare (HMO)", "Cigna", "HMO", 0.00, 200.00, 4800.00, 3.5, 1, "TX"),
    # BCBS plans
    ("H7917-010", "BCBS Medicare Blue Choice (PPO)", "Blue Cross Blue Shield", "PPO", 55.00, 175.00, 6200.00, 4.5, 1, "GA"),
    ("H7917-025", "BCBS Medicare Essentials (HMO)", "Blue Cross Blue Shield", "HMO", 0.00, 300.00, 4800.00, 4.0, 1, "GA"),
    ("H7917-030", "BCBS Medicare Advantage Plus (PPO)", "Blue Cross Blue Shield", "PPO", 42.00, 0.00, 5500.00, 4.0, 1, "MA"),
    # Wellcare plans
    ("H1032-064", "Wellcare Value Script (HMO)", "Wellcare", "HMO", 0.00, 0.00, 4000.00, 3.5, 1, "FL"),
    ("H1032-070", "Wellcare No Premium (HMO)", "Wellcare", "HMO", 0.00, 500.00, 5500.00, 3.0, 0, "FL"),
    ("H1032-075", "Wellcare Giveback (HMO)", "Wellcare", "HMO", 0.00, 0.00, 3800.00, 3.5, 1, "TX"),
    # Kaiser Permanente
    ("H0524-001", "Kaiser Permanente Senior Advantage (HMO)", "Kaiser Permanente", "HMO", 15.00, 0.00, 3200.00, 5.0, 1, "CA"),
    ("H0524-005", "Kaiser Permanente Medicare Cost (HMO)", "Kaiser Permanente", "HMO", 0.00, 0.00, 3000.00, 4.5, 1, "CA"),
    # Molina
    ("H9622-005", "Molina Medicare Complete Care (HMO)", "Molina Healthcare", "HMO", 0.00, 0.00, 3800.00, 3.5, 1, "CA"),
    ("H9622-010", "Molina Medicare Choice (HMO)", "Molina Healthcare", "HMO", 0.00, 150.00, 4200.00, 3.0, 1, "TX"),
    # Anthem/Elevance
    ("H3952-018", "Anthem MediBlue Plus (PPO)", "Anthem", "PPO", 89.00, 0.00, 5200.00, 4.0, 1, "IN"),
    ("H3952-025", "Anthem MediBlue Access (HMO)", "Anthem", "HMO", 0.00, 0.00, 4000.00, 4.0, 1, "CA"),
    # Centene
    ("H6105-012", "Centene Ambetter Medicare (HMO)", "Centene", "HMO", 20.00, 200.00, 4600.00, 3.0, 1, "AZ"),
    ("H6105-018", "Centene WellCare Flex (PPO)", "Centene", "PPO", 38.00, 0.00, 5000.00, 3.5, 1, "AZ"),
    # Devoted Health
    ("H8230-003", "Devoted Health Medicare (HMO)", "Devoted Health", "HMO", 0.00, 0.00, 3500.00, 4.5, 1, "FL"),
    ("H8230-008", "Devoted Health Premium (HMO)", "Devoted Health", "HMO", 25.00, 0.00, 3000.00, 4.5, 1, "TX"),
    # Clover Health
    ("H7322-008", "Clover Health Preferred (PPO)", "Clover Health", "PPO", 30.00, 100.00, 4900.00, 3.5, 1, "NJ"),
    ("H7322-012", "Clover Health Choice (PPO)", "Clover Health", "PPO", 0.00, 200.00, 5500.00, 3.0, 1, "NJ"),
    # Oscar Health
    ("H8245-002", "Oscar Medicare Advantage (HMO)", "Oscar Health", "HMO", 175.00, 0.00, 3000.00, 4.0, 1, "NY"),
    ("H8245-005", "Oscar Medicare Edge (HMO)", "Oscar Health", "HMO", 95.00, 0.00, 3500.00, 4.0, 1, "CA"),
    # Alignment Healthcare
    ("H0562-001", "Alignment Health Plan Access (HMO)", "Alignment Healthcare", "HMO", 0.00, 0.00, 3900.00, 4.0, 1, "CA"),
    # Scan Health Plan
    ("H5425-010", "SCAN Classic (HMO)", "SCAN Health Plan", "HMO", 0.00, 0.00, 3400.00, 4.5, 1, "CA"),
    ("H5425-015", "SCAN Connections (HMO-POS)", "SCAN Health Plan", "HMO", 19.00, 0.00, 3800.00, 4.0, 1, "CA"),
    # Mutual of Omaha
    ("H6806-001", "Mutual of Omaha Medicare Advantage (PPO)", "Mutual of Omaha", "PPO", 0.00, 250.00, 5900.00, 3.5, 1, "NE"),
    # Bright Health
    ("H6299-003", "Bright Medicare Essential (HMO)", "Bright Health", "HMO", 0.00, 0.00, 4500.00, 3.0, 1, "FL"),
    # Zing Health
    ("H4624-002", "Zing Choice (HMO)", "Zing Health", "HMO", 0.00, 0.00, 3500.00, 3.5, 1, "IL"),
    # CareSource
    ("H8452-004", "CareSource Advantage (HMO)", "CareSource", "HMO", 0.00, 0.00, 4000.00, 3.5, 1, "OH"),
    # Priority Health
    ("H5945-003", "Priority Health Medicare (HMO)", "Priority Health", "HMO", 0.00, 100.00, 4200.00, 4.0, 1, "MI"),
    # Regence
    ("H3817-001", "Regence MedAdvantage (PPO)", "Regence", "PPO", 48.00, 0.00, 5000.00, 4.0, 1, "WA"),
    # Additional coverage plans
    ("H3312-050", "Aetna Medicare Premier Plan (PPO)", "Aetna", "PPO", 120.00, 0.00, 4500.00, 4.5, 1, "FL"),
    ("H1036-220", "Humana Medicare Saver (HMO)", "Humana", "HMO", 0.00, 350.00, 5000.00, 3.5, 1, "GA"),
    ("H2228-090", "UHC AARP Medicare Complete (HMO)", "UnitedHealthcare", "HMO", 0.00, 0.00, 3500.00, 4.5, 1, "AZ"),
    ("H5410-050", "Cigna Medicare Saver (HMO)", "Cigna", "HMO", 0.00, 275.00, 5200.00, 3.5, 1, "WA"),
    ("H0524-010", "Kaiser Permanente Senior Advantage Medi-Medi (HMO-SNP)", "Kaiser Permanente", "HMO", 0.00, 0.00, 2800.00, 5.0, 1, "CA"),
    ("H1032-080", "Wellcare Patriot (PPO)", "Wellcare", "PPO", 42.00, 0.00, 5200.00, 3.5, 1, "MA"),
]

# Map zip codes to plan_ids for seed data
SEED_ZIP_MAPPINGS: dict[str, list[str]] = {
    # New York City
    "10001": ["H3312-034", "H5521-017", "H3312-041", "H2228-050", "H2228-063", "H8245-002", "H7322-008", "H7322-012"],
    "10002": ["H3312-034", "H5521-017", "H2228-050", "H2228-063", "H8245-002"],
    "10003": ["H3312-034", "H5521-017", "H3312-041", "H2228-050", "H2228-063", "H8245-002"],
    # Staten Island — same NY plan footprint as Manhattan
    "10304": ["H3312-034", "H5521-017", "H3312-041", "H2228-050", "H2228-063", "H8245-002", "H7322-008", "H7322-012"],
    # Los Angeles / Beverly Hills
    "90210": ["H5521-022", "H2228-080", "H0524-001", "H0524-005", "H9622-005", "H3952-025", "H8245-005", "H0562-001", "H5425-010", "H5425-015", "H0524-010"],
    "90001": ["H5521-022", "H2228-080", "H0524-001", "H9622-005", "H3952-025", "H0562-001", "H5425-010"],
    # Chicago
    "60601": ["H2228-071", "H5410-022", "H5410-038", "H4624-002"],
    "60602": ["H2228-071", "H5410-022", "H5410-038", "H4624-002"],
    # Miami
    "33101": ["H1036-200", "H1036-180", "H2228-085", "H1032-064", "H1032-070", "H8230-003", "H6299-003", "H3312-050"],
    "33102": ["H1036-200", "H1036-180", "H2228-085", "H1032-064", "H8230-003"],
    # Houston
    "77001": ["H1036-210", "H1036-215", "H5410-045", "H1032-075", "H9622-010", "H8230-008"],
    "77002": ["H1036-210", "H1036-215", "H5410-045", "H1032-075", "H9622-010"],
    # Phoenix
    "85001": ["H6105-012", "H6105-018", "H2228-090"],
    "85002": ["H6105-012", "H6105-018", "H2228-090"],
    # Seattle
    "98101": ["H3817-001", "H5410-050"],
    "98102": ["H3817-001", "H5410-050"],
    # Atlanta
    "30301": ["H7917-010", "H7917-025", "H1036-220"],
    "30302": ["H7917-010", "H7917-025", "H1036-220"],
    # Boston
    "02101": ["H7917-030", "H1032-080"],
    "02102": ["H7917-030", "H1032-080"],
    # Dallas
    "75201": ["H1036-210", "H1036-215", "H5410-045", "H1032-075"],
    # Indianapolis
    "46201": ["H3952-018"],
    # Newark / NJ
    "07101": ["H7322-008", "H7322-012"],
    # Omaha
    "68101": ["H6806-001"],
    # Columbus OH
    "43201": ["H8452-004"],
    # Detroit MI
    "48201": ["H5945-003"],
    # Jacksonville FL
    "32099": ["H1036-200", "H1036-180", "H1032-064", "H8230-003"],
}

SEED_DRUGS = [
    # Tier 1 - Generic (common generics)
    ("Metformin", "metformin hydrochloride", "Glucophage", "00087-6060-05", "Tablet", "Tier 1 - Generic", 5.0, 10.0, 0, "90-day supply"),
    ("Lisinopril", "lisinopril", "Prinivil", "00006-0019-54", "Tablet", "Tier 1 - Generic", 3.0, 8.0, 0, "90-day supply"),
    ("Atorvastatin", "atorvastatin calcium", "Lipitor", "00071-0155-23", "Tablet", "Tier 1 - Generic", 5.0, 10.0, 0, "90-day supply"),
    ("Amlodipine", "amlodipine besylate", "Norvasc", "00069-1530-30", "Tablet", "Tier 1 - Generic", 3.0, 7.0, 0, "90-day supply"),
    ("Omeprazole", "omeprazole", "Prilosec", "00186-5020-31", "Capsule", "Tier 1 - Generic", 5.0, 10.0, 0, "90-day supply"),
    ("Levothyroxine", "levothyroxine sodium", "Synthroid", "00074-5182-90", "Tablet", "Tier 1 - Generic", 5.0, 10.0, 0, "90-day supply"),
    ("Gabapentin", "gabapentin", "Neurontin", "00071-0802-24", "Capsule", "Tier 1 - Generic", 5.0, 10.0, 0, "90-day supply"),
    ("Losartan", "losartan potassium", "Cozaar", "00006-0951-54", "Tablet", "Tier 1 - Generic", 3.0, 8.0, 0, "90-day supply"),
    ("Hydrochlorothiazide", "hydrochlorothiazide", "Microzide", "00378-0232-01", "Tablet", "Tier 1 - Generic", 3.0, 7.0, 0, "90-day supply"),
    ("Sertraline", "sertraline hydrochloride", "Zoloft", "00049-4960-50", "Tablet", "Tier 1 - Generic", 5.0, 10.0, 0, "90-day supply"),
    ("Montelukast", "montelukast sodium", "Singulair", "00006-0275-31", "Tablet", "Tier 1 - Generic", 5.0, 12.0, 0, "30-day supply"),
    ("Pantoprazole", "pantoprazole sodium", "Protonix", "00008-0841-81", "Tablet", "Tier 1 - Generic", 5.0, 10.0, 0, "90-day supply"),
    ("Escitalopram", "escitalopram oxalate", "Lexapro", "00456-2010-01", "Tablet", "Tier 1 - Generic", 5.0, 10.0, 0, "90-day supply"),
    ("Rosuvastatin", "rosuvastatin calcium", "Crestor", "00310-0755-90", "Tablet", "Tier 1 - Generic", 5.0, 12.0, 0, "90-day supply"),
    ("Tamsulosin", "tamsulosin hydrochloride", "Flomax", "00597-0058-01", "Capsule", "Tier 1 - Generic", 5.0, 10.0, 0, "90-day supply"),
    ("Meloxicam", "meloxicam", "Mobic", "00597-0057-01", "Tablet", "Tier 1 - Generic", 3.0, 8.0, 0, "30-day supply"),
    ("Glipizide", "glipizide", "Glucotrol", "00049-4110-66", "Tablet", "Tier 1 - Generic", 5.0, 10.0, 0, "90-day supply"),
    ("Warfarin", "warfarin sodium", "Coumadin", "00056-0169-75", "Tablet", "Tier 1 - Generic", 3.0, 7.0, 0, "90-day supply"),
    ("Metoprolol Succinate", "metoprolol succinate", "Toprol-XL", "00186-1092-05", "Tablet ER", "Tier 1 - Generic", 5.0, 10.0, 0, "90-day supply"),
    ("Furosemide", "furosemide", "Lasix", "00039-0060-13", "Tablet", "Tier 1 - Generic", 3.0, 7.0, 0, "90-day supply"),
    ("Prednisone", "prednisone", "Deltasone", "00054-4728-25", "Tablet", "Tier 1 - Generic", 3.0, 8.0, 0, "30-day supply"),
    ("Carvedilol", "carvedilol", "Coreg", "00007-4140-20", "Tablet", "Tier 1 - Generic", 5.0, 10.0, 0, "90-day supply"),
    ("Clopidogrel", "clopidogrel bisulfate", "Plavix", "00024-5847-04", "Tablet", "Tier 1 - Generic", 5.0, 10.0, 0, "90-day supply"),
    ("Duloxetine", "duloxetine hydrochloride", "Cymbalta", "00002-3240-30", "Capsule DR", "Tier 1 - Generic", 5.0, 12.0, 0, "90-day supply"),
    ("Bupropion", "bupropion hydrochloride", "Wellbutrin", "00173-0177-55", "Tablet", "Tier 1 - Generic", 5.0, 10.0, 0, "90-day supply"),
    ("Spironolactone", "spironolactone", "Aldactone", "00025-1001-51", "Tablet", "Tier 1 - Generic", 5.0, 10.0, 0, "90-day supply"),
    ("Fluoxetine", "fluoxetine hydrochloride", "Prozac", "00777-3105-02", "Capsule", "Tier 1 - Generic", 3.0, 8.0, 0, "90-day supply"),
    ("Tramadol", "tramadol hydrochloride", "Ultram", "00045-0659-60", "Tablet", "Tier 1 - Generic", 5.0, 10.0, 0, "30-day supply"),
    ("Trazodone", "trazodone hydrochloride", "Desyrel", "00555-0104-02", "Tablet", "Tier 1 - Generic", 3.0, 8.0, 0, "90-day supply"),
    ("Pravastatin", "pravastatin sodium", "Pravachol", "00003-5178-31", "Tablet", "Tier 1 - Generic", 3.0, 8.0, 0, "90-day supply"),
    ("Simvastatin", "simvastatin", "Zocor", "00006-0726-54", "Tablet", "Tier 1 - Generic", 3.0, 7.0, 0, "90-day supply"),
    ("Potassium Chloride", "potassium chloride", "Klor-Con", "00245-0040-01", "Tablet ER", "Tier 1 - Generic", 5.0, 10.0, 0, "90-day supply"),
    ("Cephalexin", "cephalexin", "Keflex", "00777-2613-01", "Capsule", "Tier 1 - Generic", 5.0, 10.0, 0, "30-day supply"),
    ("Amoxicillin", "amoxicillin", "Amoxil", "00029-6008-31", "Capsule", "Tier 1 - Generic", 3.0, 7.0, 0, "30-day supply"),
    ("Azithromycin", "azithromycin", "Zithromax", "00069-3060-75", "Tablet", "Tier 1 - Generic", 5.0, 10.0, 0, "30-day supply"),
    ("Ciprofloxacin", "ciprofloxacin hydrochloride", "Cipro", "00009-7520-01", "Tablet", "Tier 1 - Generic", 5.0, 10.0, 0, "30-day supply"),
    ("Cyclobenzaprine", "cyclobenzaprine hydrochloride", "Flexeril", "00006-0931-68", "Tablet", "Tier 1 - Generic", 3.0, 8.0, 0, "30-day supply"),
    ("Allopurinol", "allopurinol", "Zyloprim", "00054-3281-25", "Tablet", "Tier 1 - Generic", 3.0, 7.0, 0, "90-day supply"),
    ("Donepezil", "donepezil hydrochloride", "Aricept", "00062-1050-30", "Tablet", "Tier 1 - Generic", 5.0, 10.0, 0, "90-day supply"),
    ("Finasteride", "finasteride", "Proscar", "00006-0071-31", "Tablet", "Tier 1 - Generic", 5.0, 10.0, 0, "90-day supply"),
    # Tier 2 - Preferred Brand
    ("Albuterol", "albuterol sulfate", "ProAir HFA", "59310-0579-22", "Inhaler", "Tier 2 - Preferred Brand", 25.0, 35.0, 0, "30-day supply"),
    ("Lantus", "insulin glargine", "Lantus", "00088-2220-33", "Injection", "Tier 2 - Preferred Brand", 35.0, 45.0, 0, "30-day supply"),
    ("Humalog", "insulin lispro", "Humalog", "00002-7510-01", "Injection", "Tier 2 - Preferred Brand", 35.0, 45.0, 0, "30-day supply"),
    ("Symbicort", "budesonide/formoterol", "Symbicort", "00186-0372-20", "Inhaler", "Tier 2 - Preferred Brand", 30.0, 40.0, 0, "30-day supply"),
    ("Spiriva", "tiotropium bromide", "Spiriva", "00597-0075-41", "Inhaler", "Tier 2 - Preferred Brand", 30.0, 40.0, 0, "30-day supply"),
    ("Januvia", "sitagliptin phosphate", "Januvia", "00006-0277-31", "Tablet", "Tier 2 - Preferred Brand", 35.0, 45.0, 0, "30-day supply"),
    ("Venlafaxine ER", "venlafaxine hydrochloride", "Effexor XR", "00008-0833-01", "Capsule ER", "Tier 2 - Preferred Brand", 20.0, 30.0, 0, "90-day supply"),
    ("Pregabalin", "pregabalin", "Lyrica", "00071-1014-68", "Capsule", "Tier 2 - Preferred Brand", 25.0, 40.0, 0, "30-day supply"),
    ("Eliquis Low Dose", "apixaban 2.5mg", "Eliquis 2.5mg", "00003-0894-21", "Tablet", "Tier 2 - Preferred Brand", 30.0, 42.0, 0, "30-day supply"),
    ("Breo Ellipta", "fluticasone/vilanterol", "Breo Ellipta", "00173-0859-10", "Inhaler", "Tier 2 - Preferred Brand", 35.0, 45.0, 0, "30-day supply"),
    # Tier 3 - Non-Preferred
    ("Insulin Glargine", "insulin glargine", "Basaglar", "00002-7711-01", "Injection", "Tier 3 - Non-Preferred", 47.0, 75.0, 0, "30-day supply"),
    ("Eliquis", "apixaban", "Eliquis", "00003-0893-21", "Tablet", "Tier 3 - Non-Preferred", 47.0, 95.0, 1, "30-day supply"),
    ("Jardiance", "empagliflozin", "Jardiance", "00597-0152-30", "Tablet", "Tier 3 - Non-Preferred", 47.0, 90.0, 1, "30-day supply"),
    ("Xarelto", "rivaroxaban", "Xarelto", "50458-0580-30", "Tablet", "Tier 3 - Non-Preferred", 47.0, 95.0, 1, "30-day supply"),
    ("Entresto", "sacubitril/valsartan", "Entresto", "00078-0696-15", "Tablet", "Tier 3 - Non-Preferred", 47.0, 90.0, 1, "30-day supply"),
    ("Tresiba", "insulin degludec", "Tresiba", "00169-2660-13", "Injection", "Tier 3 - Non-Preferred", 47.0, 80.0, 0, "30-day supply"),
    ("Farxiga", "dapagliflozin", "Farxiga", "00310-6205-30", "Tablet", "Tier 3 - Non-Preferred", 47.0, 85.0, 1, "30-day supply"),
    ("Trulicity", "dulaglutide", "Trulicity", "00002-1474-01", "Injection", "Tier 3 - Non-Preferred", 47.0, 95.0, 1, "30-day supply"),
    ("Rybelsus", "semaglutide oral", "Rybelsus", "00169-4314-13", "Tablet", "Tier 3 - Non-Preferred", 47.0, 90.0, 1, "30-day supply"),
    ("Victoza", "liraglutide", "Victoza", "00169-4060-12", "Injection", "Tier 3 - Non-Preferred", 47.0, 85.0, 1, "30-day supply"),
    ("Brilinta", "ticagrelor", "Brilinta", "00186-0380-60", "Tablet", "Tier 3 - Non-Preferred", 47.0, 90.0, 1, "30-day supply"),
    ("Pradaxa", "dabigatran etexilate", "Pradaxa", "00597-0150-60", "Capsule", "Tier 3 - Non-Preferred", 47.0, 85.0, 1, "30-day supply"),
    ("Invokana", "canagliflozin", "Invokana", "50458-0140-30", "Tablet", "Tier 3 - Non-Preferred", 47.0, 85.0, 1, "30-day supply"),
    ("Repatha", "evolocumab", "Repatha", "55513-0730-01", "Injection", "Tier 3 - Non-Preferred", 60.0, 95.0, 1, "30-day supply"),
    ("Toujeo", "insulin glargine U-300", "Toujeo", "00088-5020-03", "Injection", "Tier 3 - Non-Preferred", 47.0, 80.0, 0, "30-day supply"),
    ("Levemir", "insulin detemir", "Levemir", "00169-1833-12", "Injection", "Tier 3 - Non-Preferred", 47.0, 75.0, 0, "30-day supply"),
    ("Novolog", "insulin aspart", "Novolog", "00169-7501-11", "Injection", "Tier 3 - Non-Preferred", 47.0, 75.0, 0, "30-day supply"),
    ("Admelog", "insulin lispro biosimilar", "Admelog", "00024-5801-05", "Injection", "Tier 3 - Non-Preferred", 47.0, 70.0, 0, "30-day supply"),
    ("Ozempic Low Dose", "semaglutide 0.25mg", "Ozempic 0.25mg", "00169-4131-12", "Injection", "Tier 3 - Non-Preferred", 55.0, 90.0, 1, "30-day supply"),
    ("Wegovy", "semaglutide 2.4mg", "Wegovy", "00169-4501-01", "Injection", "Tier 3 - Non-Preferred", 60.0, 95.0, 1, "30-day supply"),
    # Tier 4 - Specialty
    ("Ozempic", "semaglutide", "Ozempic", "00169-4130-12", "Injection", "Tier 4 - Specialty", 100.0, 150.0, 1, "30-day supply"),
    ("Humira", "adalimumab", "Humira", "00074-4339-02", "Injection", "Tier 4 - Specialty", 150.0, 250.0, 1, "30-day supply"),
    ("Dupixent", "dupilumab", "Dupixent", "00024-5918-02", "Injection", "Tier 4 - Specialty", 150.0, 275.0, 1, "30-day supply"),
    ("Keytruda", "pembrolizumab", "Keytruda", "00006-3026-02", "Injection", "Tier 4 - Specialty", 250.0, 300.0, 1, "30-day supply"),
    ("Enbrel", "etanercept", "Enbrel", "58406-0435-04", "Injection", "Tier 4 - Specialty", 150.0, 250.0, 1, "30-day supply"),
    ("Stelara", "ustekinumab", "Stelara", "57894-0060-03", "Injection", "Tier 4 - Specialty", 150.0, 275.0, 1, "30-day supply"),
    ("Skyrizi", "risankizumab", "Skyrizi", "00074-2100-01", "Injection", "Tier 4 - Specialty", 150.0, 275.0, 1, "30-day supply"),
    ("Rinvoq", "upadacitinib", "Rinvoq", "00074-2306-30", "Tablet", "Tier 4 - Specialty", 150.0, 250.0, 1, "30-day supply"),
    ("Tremfya", "guselkumab", "Tremfya", "57894-0150-01", "Injection", "Tier 4 - Specialty", 150.0, 275.0, 1, "30-day supply"),
    ("Xeljanz", "tofacitinib", "Xeljanz", "00069-0501-30", "Tablet", "Tier 4 - Specialty", 125.0, 200.0, 1, "30-day supply"),
    ("Mounjaro", "tirzepatide", "Mounjaro", "00002-1506-01", "Injection", "Tier 4 - Specialty", 125.0, 200.0, 1, "30-day supply"),
    ("Cosentyx", "secukinumab", "Cosentyx", "00078-0639-98", "Injection", "Tier 4 - Specialty", 150.0, 250.0, 1, "30-day supply"),
    ("Otezla", "apremilast", "Otezla", "59572-0410-00", "Tablet", "Tier 4 - Specialty", 100.0, 175.0, 1, "30-day supply"),
    ("Taltz", "ixekizumab", "Taltz", "00002-7865-01", "Injection", "Tier 4 - Specialty", 150.0, 275.0, 1, "30-day supply"),
    ("Kevzara", "sarilumab", "Kevzara", "00024-5950-02", "Injection", "Tier 4 - Specialty", 150.0, 250.0, 1, "30-day supply"),
    ("Actemra", "tocilizumab", "Actemra", "50242-0135-01", "Injection", "Tier 4 - Specialty", 150.0, 250.0, 1, "30-day supply"),
    ("Orencia", "abatacept", "Orencia", "00003-2187-11", "Injection", "Tier 4 - Specialty", 150.0, 250.0, 1, "30-day supply"),
    ("Praluent", "alirocumab", "Praluent", "00024-5920-01", "Injection", "Tier 4 - Specialty", 125.0, 200.0, 1, "30-day supply"),
    ("Eylea", "aflibercept", "Eylea", "61755-0005-02", "Injection", "Tier 4 - Specialty", 200.0, 300.0, 1, "30-day supply"),
    ("Lucentis", "ranibizumab", "Lucentis", "50242-0080-01", "Injection", "Tier 4 - Specialty", 200.0, 300.0, 1, "30-day supply"),
]

# ---------------------------------------------------------------------------
# CMS Data Downloader
# ---------------------------------------------------------------------------

def download_cms_data() -> tuple[list[tuple], dict[str, set[str]]] | None:
    """Download CMS Medicare Advantage Plan Landscape, paged.

    Returns (plans, plan_county_map) where plans is a list of tuples in the
    column order build_database expects, and plan_county_map maps plan_id to
    the set of county FIPS codes that plan serves. Returns None on first-page
    failure; on later-page failure, returns what was collected.
    """
    if httpx is None:
        logger.warning("httpx not installed — skipping CMS download. Using seed data.")
        return None

    logger.info("Downloading CMS Medicare Advantage plan landscape (paged)...")
    url = "https://data.cms.gov/resource/jfhb-kvhx.json"
    select = (
        "contract_id,plan_id,plan_name,organization_name,plan_type,"
        "monthly_consolidated_premium,annual_drug_deductible,out_of_pocket_maximum,"
        "overall_star_rating,drug_coverage,state,county_code"
    )

    plans_by_id: dict[str, tuple] = {}
    plan_county_map: dict[str, set[str]] = defaultdict(set)
    page_size = 5000
    offset = 0

    while True:
        params = {"$limit": page_size, "$offset": offset, "$select": select}
        try:
            with httpx.Client(timeout=60.0) as client:
                resp = client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            sunset_hint = ""
            if "410" in str(e) or "Gone" in str(e):
                sunset_hint = (
                    " — CMS retired the legacy Socrata SODA API in 2026; "
                    "see README 'Data refresh' section."
                )
            if not plans_by_id:
                logger.warning(f"CMS download failed on first page ({e}). Using seed data.{sunset_hint}")
                return None
            logger.warning(
                f"CMS download failed at offset {offset} ({e}). "
                f"Using {len(plans_by_id)} plans collected so far.{sunset_hint}"
            )
            break

        if not data:
            break

        for row in data:
            try:
                plan_id = f"{row.get('contract_id', '')}-{row.get('plan_id', '')}"
                if plan_id == "-":
                    continue
                county_code = (row.get("county_code") or "").strip()
                if county_code:
                    plan_county_map[plan_id].add(county_code)
                if plan_id in plans_by_id:
                    continue  # plan already captured; only county is new
                premium = float(row.get("monthly_consolidated_premium", 0) or 0)
                deductible = float(row.get("annual_drug_deductible", 0) or 0)
                oop = float(row.get("out_of_pocket_maximum", 6700) or 6700)
                star_str = (row.get("overall_star_rating") or "").strip()
                star = float(star_str) if star_str and star_str != "Not enough data" else 3.0
                drug = 1 if str(row.get("drug_coverage", "")).lower() in ("yes", "true", "1") else 0
                plans_by_id[plan_id] = (
                    plan_id,
                    row.get("plan_name", "Unknown Plan"),
                    row.get("organization_name", "Unknown"),
                    row.get("plan_type", "HMO"),
                    premium,
                    deductible,
                    oop,
                    star,
                    drug,
                    row.get("state", ""),
                )
            except (ValueError, TypeError) as e:
                logger.debug(f"Skipping malformed row: {e}")
                continue

        if len(data) < page_size:
            break
        offset += page_size

    logger.info(
        f"CMS: {len(plans_by_id)} plans across "
        f"{sum(len(v) for v in plan_county_map.values())} plan-county pairs."
    )
    return list(plans_by_id.values()), dict(plan_county_map)


# ---------------------------------------------------------------------------
# FDA Drug Data Downloader
# ---------------------------------------------------------------------------

def download_fda_drugs() -> list[tuple] | None:
    """Attempt to download FDA drug data. Returns list of drug tuples or None on failure."""
    try:
        import httpx
    except ImportError:
        logger.warning("httpx not installed — skipping FDA download. Using seed data.")
        return None

    logger.info("Downloading FDA drug data for top prescribed drugs...")
    # We query OpenFDA for common drug names and build our records
    # Start with the names from seed data to look up NDCs and verify names
    drug_names_to_lookup = [d[0] for d in SEED_DRUGS[:50]]  # Top 50

    drugs_found: list[tuple] = []
    try:
        with httpx.Client(timeout=30.0) as client:
            for name in drug_names_to_lookup:
                try:
                    resp = client.get(
                        "https://api.fda.gov/drug/label.json",
                        params={"search": f'openfda.brand_name:"{name}"', "limit": 1},
                    )
                    if resp.status_code != 200:
                        continue
                    results = resp.json().get("results", [])
                    if not results:
                        continue

                    result = results[0]
                    openfda = result.get("openfda", {})
                    brand = openfda.get("brand_name", [name])[0] if openfda.get("brand_name") else name
                    generic = openfda.get("generic_name", [""])[0] if openfda.get("generic_name") else ""
                    ndc = openfda.get("product_ndc", [""])[0] if openfda.get("product_ndc") else ""
                    dosage = openfda.get("dosage_form", ["Tablet"])[0] if openfda.get("dosage_form") else "Tablet"

                    # Find matching seed drug for tier/copay info (we keep curated pricing)
                    seed_match = next((d for d in SEED_DRUGS if d[0].lower() == name.lower()), None)
                    if seed_match:
                        drugs_found.append((
                            seed_match[0], generic.lower() or seed_match[1],
                            brand, ndc or seed_match[3], dosage or seed_match[4],
                            seed_match[5], seed_match[6], seed_match[7],
                            seed_match[8], seed_match[9],
                        ))

                    # Rate limit: FDA API allows ~40 req/min without key
                    time.sleep(0.1)
                except Exception:
                    continue

        if len(drugs_found) < 20:
            logger.warning(f"Only found {len(drugs_found)} drugs from FDA. Using seed data.")
            return None

        logger.info(f"Verified {len(drugs_found)} drugs from FDA.")
        return drugs_found

    except Exception as e:
        logger.warning(f"FDA download failed: {e}. Using seed data.")
        return None


# ---------------------------------------------------------------------------
# HUD ZIP ↔ County Crosswalk Downloader
# ---------------------------------------------------------------------------

HUD_API_URL = "https://www.huduser.gov/hudapi/public/usps"


def download_hud_zip_county() -> dict[str, set[str]] | None:
    """Download the HUD USPS ZIP↔county crosswalk for all US ZIPs.

    Returns dict[zip_code, set[county_fips]] or None on failure.
    Falls back silently (returns None) if HUD_API_TOKEN is not set or if
    httpx isn't available — the orchestrator then uses SEED_ZIP_MAPPINGS.
    """
    token = os.environ.get("HUD_API_TOKEN")
    if not token:
        logger.warning(
            "HUD_API_TOKEN not set; using seed ZIP mappings (~25 ZIPs covered). "
            "Set the token in .env to enable nationwide ZIPs."
        )
        return None
    if httpx is None:
        logger.warning("httpx not installed — skipping HUD download. Using seed ZIP mappings.")
        return None

    logger.info("Downloading HUD ZIP↔county crosswalk (national)...")
    try:
        with httpx.Client(timeout=120.0) as client:
            resp = client.get(
                HUD_API_URL,
                params={"type": 2, "query": "All"},
                headers={"Authorization": f"Bearer {token}"},
            )
            resp.raise_for_status()
            payload = resp.json()
    except Exception as e:
        logger.warning(f"HUD download failed: {e}. Falling back to seed ZIP mappings.")
        return None

    results = (payload or {}).get("data", {}).get("results", []) or []
    zip_county_map: dict[str, set[str]] = defaultdict(set)
    for row in results:
        zip_code = (row.get("zip") or "").strip()
        county = (row.get("geoid") or "").strip()
        if zip_code and county:
            zip_county_map[zip_code].add(county)

    logger.info(f"HUD: {len(zip_county_map)} ZIPs mapped across {sum(len(v) for v in zip_county_map.values())} ZIP-county pairs.")
    return dict(zip_county_map)


# ---------------------------------------------------------------------------
# ZIP ↔ Plan Mapping Join
# ---------------------------------------------------------------------------

def build_zip_mappings(
    plan_county_map: dict,
    zip_county_map: dict,
) -> dict[str, list[str]]:
    """Join plan→counties and zip→counties into zip→plans.

    Accepts any iterable (set or list) as the inner collection — the cache
    layer may rehydrate sets as lists after a JSON round-trip.

    A ZIP that maps to no served counties is omitted from the output rather
    than mapping to an empty list.
    """
    county_to_plans: dict[str, set[str]] = defaultdict(set)
    for plan_id, counties in plan_county_map.items():
        for county in counties:
            county_to_plans[county].add(plan_id)

    zip_to_plans: dict[str, list[str]] = {}
    for zip_code, counties in zip_county_map.items():
        plan_ids: set[str] = set()
        for county in counties:
            plan_ids.update(county_to_plans.get(county, ()))
        if plan_ids:
            zip_to_plans[zip_code] = sorted(plan_ids)
    return zip_to_plans


# ---------------------------------------------------------------------------
# Database Builder
# ---------------------------------------------------------------------------

def build_database(
    plans: list[tuple],
    zip_mappings: dict[str, list[str]],
    drugs: list[tuple],
    db_path: Path = DB_PATH,
    plan_county_map: dict[str, set[str]] | None = None,
) -> None:
    """Build the SQLite database atomically.

    Writes to <db_path>.tmp, then os.replace()s to db_path so a mid-run
    crash leaves any previous DB intact.
    """
    tmp_path = db_path.with_name(db_path.name + ".tmp")
    if tmp_path.exists():
        tmp_path.unlink()

    conn = sqlite3.connect(str(tmp_path))
    try:
        conn.executescript(SCHEMA_SQL)

        conn.executemany(
            """
            INSERT OR IGNORE INTO plans
                (plan_id, plan_name, organization, plan_type, monthly_premium,
                 annual_deductible, out_of_pocket_max, star_rating, drug_coverage, state)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            plans,
        )

        # plan_zips
        zip_rows = [
            (plan_id, zip_code)
            for zip_code, plan_ids in zip_mappings.items()
            for plan_id in plan_ids
        ]
        conn.executemany(
            "INSERT INTO plan_zips (plan_id, zip_code) VALUES (?, ?)",
            zip_rows,
        )

        # plan_counties
        if plan_county_map:
            plan_state = {p[0]: p[9] for p in plans}  # plan_id -> state
            county_rows = [
                (plan_id, plan_state.get(plan_id, ""), "", fips)
                for plan_id, counties in plan_county_map.items()
                for fips in counties
            ]
            conn.executemany(
                "INSERT INTO plan_counties (plan_id, state, county, fips_code) VALUES (?, ?, ?, ?)",
                county_rows,
            )

        # drugs
        conn.executemany(
            """
            INSERT INTO drugs
                (name, generic_name, brand_name, ndc, dosage_form,
                 tier_generic, copay_hmo, copay_ppo, prior_auth, quantity_limit)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            drugs,
        )

        conn.commit()

        plan_count = conn.execute("SELECT COUNT(*) FROM plans").fetchone()[0]
        drug_count = conn.execute("SELECT COUNT(*) FROM drugs").fetchone()[0]
        zip_count = conn.execute("SELECT COUNT(DISTINCT zip_code) FROM plan_zips").fetchone()[0]
        county_count = conn.execute("SELECT COUNT(*) FROM plan_counties").fetchone()[0]
    finally:
        conn.close()

    os.replace(str(tmp_path), str(db_path))

    print(
        f"Loaded {plan_count} plans, {drug_count} drugs, "
        f"{zip_count} zips, {county_count} plan-county rows"
    )
    logger.info(
        f"Database built: {plan_count} plans, {drug_count} drugs, "
        f"{zip_count} zips, {county_count} plan-county rows"
    )
    logger.info(f"Saved to: {db_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Refresh healthflow_data.db")
    parser.add_argument(
        "--seed-only",
        action="store_true",
        help="Use curated seed data only (no downloads). Good for CI/testing.",
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Bypass the local cache for both CMS and HUD downloads.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable DEBUG logging (pagination, cache hits, row counts).",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DB_PATH,
        help=f"Output database path (default: {DB_PATH})",
    )
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)

    if args.seed_only:
        logger.info("Using seed data only (--seed-only).")
        plans = SEED_PLANS
        drugs = SEED_DRUGS
        zip_mappings = SEED_ZIP_MAPPINGS
        plan_county_map: dict[str, set[str]] | None = None
        build_database(plans, zip_mappings, drugs, db_path=args.db_path, plan_county_map=plan_county_map)
        return

    logger.info("Attempting to download real data from CMS, HUD, and FDA...")

    cms_result = _load_or_fetch(
        "cms_landscape", ttl_days=7,
        fetch_fn=download_cms_data, force=args.force_refresh,
    )
    drugs = _load_or_fetch(
        "fda_drugs", ttl_days=30,
        fetch_fn=download_fda_drugs, force=args.force_refresh,
    )
    zip_county_map = _load_or_fetch(
        "hud_zip_county", ttl_days=30,
        fetch_fn=download_hud_zip_county, force=args.force_refresh,
    )

    if cms_result is None:
        logger.info("Falling back to seed plan data (CMS download failed).")
        plans = SEED_PLANS
        plan_county_map = None
        zip_mappings = SEED_ZIP_MAPPINGS
    else:
        plans, plan_county_map = cms_result
        # Cache may have rehydrated tuples as lists; coerce back.
        plans = [tuple(p) for p in plans]
        # Cache may have rehydrated set values as lists; build_zip_mappings accepts both.
        if zip_county_map:
            zip_mappings = build_zip_mappings(plan_county_map, zip_county_map)
            if not zip_mappings:
                logger.warning(
                    "build_zip_mappings produced empty result; "
                    "falling back to seed ZIP mappings."
                )
                zip_mappings = SEED_ZIP_MAPPINGS
        else:
            logger.info("Falling back to seed ZIP mappings (HUD unavailable).")
            zip_mappings = SEED_ZIP_MAPPINGS

    if drugs is None:
        logger.info("Falling back to seed drug data.")
        drugs = SEED_DRUGS
    else:
        drugs = [tuple(d) for d in drugs]  # cache JSON round-trip

    build_database(
        plans, zip_mappings, drugs,
        db_path=args.db_path,
        plan_county_map=plan_county_map,
    )


if __name__ == "__main__":
    main()
