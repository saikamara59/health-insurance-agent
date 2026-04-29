"""Seed script — creates a test broker and sample clients with real doctor data."""
import json
import os
import httpx
import sys

BASE_URL = "http://localhost:8000"

BROKER = {
    "email": "demo@healthflow.com",
    "password": "healthflow123",
    "full_name": "Dr. Sarah Vance",
}

# Load real doctors if available
REAL_DOCTORS_PATH = os.path.join(os.path.dirname(__file__), "scripts", "real_doctors.json")
real_doctors = []
if os.path.exists(REAL_DOCTORS_PATH):
    with open(REAL_DOCTORS_PATH) as f:
        real_doctors = json.load(f)

def get_doctors(city, count=2):
    """Get real doctors for a city, fallback to generic."""
    matches = [d for d in real_doctors if d.get("city", "").lower() == city.lower()]
    if matches:
        return [{"name": d["name"], "npi": d["npi"]} for d in matches[:count]]
    return [{"name": f"Dr. Smith ({city})"}]

CLIENTS = [
    # NYC clients
    {
        "full_name": "Eleanor Rigby",
        "zip_code": "10001",
        "age": 67,
        "income_level": "low",
        "doctors": get_doctors("New York", 3),
        "prescriptions": ["Metformin", "Lisinopril", "Atorvastatin"],
        "procedures": ["Annual physical", "Blood work", "EKG"],
    },
    {
        "full_name": "Julian Miller",
        "zip_code": "10001",
        "age": 42,
        "income_level": "medium",
        "doctors": get_doctors("New York", 2),
        "prescriptions": ["Ozempic", "Sertraline"],
        "procedures": ["MRI", "Mental health visit"],
    },
    {
        "full_name": "Marcus Chen",
        "zip_code": "10001",
        "age": 58,
        "income_level": "high",
        "doctors": get_doctors("New York", 2),
        "prescriptions": ["Eliquis", "Entresto", "Metoprolol"],
        "procedures": ["Specialist office visit", "CT scan", "Blood work"],
    },
    # Staten Island clients (zip 10304)
    {
        "full_name": "Anthony Russo",
        "zip_code": "10304",
        "age": 71,
        "income_level": "low",
        "doctors": get_doctors("Staten Island", 2),
        "prescriptions": ["Metformin", "Lisinopril", "Atorvastatin", "Aspirin"],
        "procedures": ["Annual physical", "Blood work", "EKG"],
    },
    {
        "full_name": "Maria DeLuca",
        "zip_code": "10304",
        "age": 64,
        "income_level": "medium",
        "doctors": get_doctors("Staten Island", 2),
        "prescriptions": ["Eliquis", "Metoprolol Succinate", "Rosuvastatin"],
        "procedures": ["Echocardiogram", "Specialist office visit", "Blood work"],
    },
    {
        "full_name": "Kevin O'Sullivan",
        "zip_code": "10304",
        "age": 49,
        "income_level": "medium",
        "doctors": get_doctors("Staten Island", 1),
        "prescriptions": ["Sertraline", "Omeprazole"],
        "procedures": ["Mental health visit", "Annual physical"],
    },
    # LA clients
    {
        "full_name": "Sofia Rodriguez",
        "zip_code": "90210",
        "age": 34,
        "income_level": "medium",
        "doctors": get_doctors("Los Angeles", 2),
        "prescriptions": ["Sertraline", "Montelukast"],
        "procedures": ["Annual physical", "Mammogram"],
    },
    {
        "full_name": "David Park",
        "zip_code": "90210",
        "age": 72,
        "income_level": "low",
        "doctors": get_doctors("Los Angeles", 3),
        "prescriptions": ["Insulin Glargine", "Metformin", "Losartan", "Warfarin"],
        "procedures": ["Blood work", "Vision exam", "Annual physical", "EKG"],
    },
    # Chicago clients
    {
        "full_name": "Sarah Hudson",
        "zip_code": "60601",
        "age": 55,
        "income_level": "high",
        "doctors": get_doctors("Chicago", 2),
        "prescriptions": ["Eliquis", "Omeprazole", "Gabapentin"],
        "procedures": ["CT scan", "Specialist office visit", "EKG"],
    },
    {
        "full_name": "Benjamin Thorne",
        "zip_code": "60601",
        "age": 71,
        "income_level": "low",
        "doctors": get_doctors("Chicago", 1),
        "prescriptions": ["Insulin Glargine", "Metformin", "Losartan", "Warfarin"],
        "procedures": ["Blood work", "Vision exam", "Annual physical"],
    },
    # Miami clients
    {
        "full_name": "Isabella Fernandez",
        "zip_code": "33101",
        "age": 63,
        "income_level": "medium",
        "doctors": get_doctors("Miami", 2),
        "prescriptions": ["Jardiance", "Lisinopril", "Rosuvastatin"],
        "procedures": ["Annual physical", "Blood work", "Hearing test"],
    },
    {
        "full_name": "Carlos Gutierrez",
        "zip_code": "33101",
        "age": 48,
        "income_level": "low",
        "doctors": get_doctors("Miami", 1),
        "prescriptions": ["Albuterol", "Montelukast", "Pantoprazole"],
        "procedures": ["X-ray", "Urgent care"],
    },
    # Houston clients
    {
        "full_name": "James Washington",
        "zip_code": "77001",
        "age": 69,
        "income_level": "medium",
        "doctors": get_doctors("Houston", 2),
        "prescriptions": ["Metformin", "Amlodipine", "Omeprazole", "Levothyroxine"],
        "procedures": ["Annual physical", "Blood work", "Colonoscopy"],
    },
    # Seattle client
    {
        "full_name": "Emily Nakamura",
        "zip_code": "98101",
        "age": 38,
        "income_level": "high",
        "doctors": get_doctors("Seattle", 2),
        "prescriptions": ["Escitalopram", "Gabapentin"],
        "procedures": ["Mental health visit", "MRI"],
    },
    # Atlanta client
    {
        "full_name": "Robert Johnson",
        "zip_code": "30301",
        "age": 74,
        "income_level": "low",
        "doctors": get_doctors("Atlanta", 2),
        "prescriptions": ["Xarelto", "Tamsulosin", "Atorvastatin", "Metformin"],
        "procedures": ["Blood work", "Ultrasound", "Annual physical"],
    },
    # Boston client
    {
        "full_name": "Patricia O'Brien",
        "zip_code": "02101",
        "age": 61,
        "income_level": "high",
        "doctors": get_doctors("Boston", 2),
        "prescriptions": ["Humira", "Meloxicam", "Omeprazole"],
        "procedures": ["Specialist office visit", "Blood work", "X-ray"],
    },
    # Dallas client
    {
        "full_name": "Miguel Torres",
        "zip_code": "75201",
        "age": 52,
        "income_level": "medium",
        "doctors": get_doctors("Dallas", 2),
        "prescriptions": ["Pantoprazole", "Glipizide", "Losartan"],
        "procedures": ["Colonoscopy", "Blood work"],
    },
    # Phoenix client
    {
        "full_name": "Linda Yamamoto",
        "zip_code": "85001",
        "age": 66,
        "income_level": "low",
        "doctors": get_doctors("Phoenix", 2),
        "prescriptions": ["Lisinopril", "Hydrochlorothiazide", "Atorvastatin"],
        "procedures": ["Annual physical", "EKG", "Lab panel"],
    },
]


def main():
    print("Seeding HealthFlow database...")
    print(f"API: {BASE_URL}")
    print(f"Real doctors loaded: {len(real_doctors)}")
    print()

    # Register broker
    resp = httpx.post(f"{BASE_URL}/auth/register", json=BROKER)
    if resp.status_code == 201:
        print(f"  Broker registered: {BROKER['email']}")
    elif resp.status_code == 409:
        print(f"  Broker already exists: {BROKER['email']}")
    else:
        print(f"  Failed to register broker: {resp.status_code} {resp.text}")
        sys.exit(1)

    # Login
    resp = httpx.post(
        f"{BASE_URL}/auth/login",
        json={"email": BROKER["email"], "password": BROKER["password"]},
    )
    if resp.status_code != 200:
        print(f"  Login failed: {resp.status_code} {resp.text}")
        sys.exit(1)
    token = resp.json()["access_token"]
    print(f"  Logged in, got token")
    print()

    headers = {"Authorization": f"Bearer {token}"}

    # Check existing clients to avoid duplicates
    existing = httpx.get(f"{BASE_URL}/clients", headers=headers)
    existing_names = set()
    if existing.status_code == 200:
        existing_names = {c["full_name"] for c in existing.json()}

    # Create clients (skip duplicates)
    created = 0
    skipped = 0
    for client in CLIENTS:
        if client["full_name"] in existing_names:
            skipped += 1
            continue
        resp = httpx.post(f"{BASE_URL}/clients", json=client, headers=headers)
        if resp.status_code == 201:
            doc_count = len(client.get("doctors", []))
            rx_count = len(client.get("prescriptions", []))
            print(f"  ✓ {client['full_name']} ({client['zip_code']}) — {doc_count} docs, {rx_count} Rx")
            created += 1
        else:
            print(f"  ✗ {client['full_name']}: {resp.status_code}")

    print()
    print("=" * 50)
    print("  SEED COMPLETE")
    print("=" * 50)
    print()
    print(f"  Created: {created} new clients")
    if skipped:
        print(f"  Skipped: {skipped} (already exist)")
    print(f"  Total clients: {len(CLIENTS)}")
    print()
    print("  Login credentials:")
    print(f"    Email:    {BROKER['email']}")
    print(f"    Password: {BROKER['password']}")
    print()


if __name__ == "__main__":
    main()
