"""Seed script — creates a test broker and sample clients for demo purposes."""
import httpx
import sys

BASE_URL = "http://localhost:8000"

BROKER = {
    "email": "demo@healthflow.com",
    "password": "healthflow123",
    "full_name": "Dr. Sarah Vance",
}

CLIENTS = [
    {
        "full_name": "Eleanor Rigby",
        "zip_code": "90210",
        "age": 67,
        "income_level": "low",
        "doctors": [{"name": "Dr. Sarah Chen", "npi": "1234567890"}],
        "prescriptions": ["Metformin", "Lisinopril", "Atorvastatin"],
        "procedures": ["Annual physical", "Blood work"],
    },
    {
        "full_name": "Julian Miller",
        "zip_code": "10001",
        "age": 42,
        "income_level": "medium",
        "doctors": [{"name": "Dr. James Wilson", "npi": "9876543210"}],
        "prescriptions": ["Ozempic", "Sertraline"],
        "procedures": ["MRI", "Mental health visit"],
    },
    {
        "full_name": "Sarah Hudson",
        "zip_code": "30301",
        "age": 55,
        "income_level": "high",
        "doctors": [
            {"name": "Dr. Maria Lopez", "npi": "5551234567"},
            {"name": "Dr. Robert Kim"},
        ],
        "prescriptions": ["Eliquis", "Omeprazole", "Gabapentin"],
        "procedures": ["CT scan", "Specialist office visit", "EKG"],
    },
    {
        "full_name": "Benjamin Thorne",
        "zip_code": "60601",
        "age": 71,
        "income_level": "low",
        "doctors": [{"name": "Dr. Patricia Davis", "npi": "1112223334"}],
        "prescriptions": ["Insulin Glargine", "Metformin", "Losartan", "Warfarin"],
        "procedures": ["Blood work", "Vision exam", "Annual physical"],
    },
]


def main():
    print("Seeding HealthFlow database...")
    print(f"API: {BASE_URL}")
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

    # Create clients
    for client in CLIENTS:
        resp = httpx.post(f"{BASE_URL}/clients", json=client, headers=headers)
        if resp.status_code == 201:
            print(f"  Created client: {client['full_name']}")
        else:
            print(f"  Failed to create {client['full_name']}: {resp.status_code} {resp.text}")

    print()
    print("=" * 50)
    print("  SEED COMPLETE")
    print("=" * 50)
    print()
    print("  Login credentials:")
    print(f"    Email:    {BROKER['email']}")
    print(f"    Password: {BROKER['password']}")
    print()
    print(f"  {len(CLIENTS)} sample clients created")
    print()


if __name__ == "__main__":
    main()
