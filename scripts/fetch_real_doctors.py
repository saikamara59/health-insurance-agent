"""Fetch real doctor data from NPPES API and build an expanded client seed."""
import json
import httpx
import time

NPPES_URL = "https://npiregistry.cms.hhs.gov/api/"

SEARCHES = [
    {"city": "New York", "state": "NY", "taxonomy_description": "Internal Medicine", "limit": 5},
    {"city": "New York", "state": "NY", "taxonomy_description": "Cardiology", "limit": 3},
    {"city": "Staten Island", "state": "NY", "taxonomy_description": "Internal Medicine", "limit": 4},
    {"city": "Staten Island", "state": "NY", "taxonomy_description": "Cardiology", "limit": 2},
    {"city": "Staten Island", "state": "NY", "taxonomy_description": "Endocrinology", "limit": 2},
    {"city": "Los Angeles", "state": "CA", "taxonomy_description": "Family Medicine", "limit": 5},
    {"city": "Los Angeles", "state": "CA", "taxonomy_description": "Dermatology", "limit": 3},
    {"city": "Chicago", "state": "IL", "taxonomy_description": "Orthopedic Surgery", "limit": 3},
    {"city": "Chicago", "state": "IL", "taxonomy_description": "Psychiatry", "limit": 3},
    {"city": "Miami", "state": "FL", "taxonomy_description": "Endocrinology", "limit": 3},
    {"city": "Houston", "state": "TX", "taxonomy_description": "Pulmonary Disease", "limit": 3},
    {"city": "Seattle", "state": "WA", "taxonomy_description": "Neurology", "limit": 3},
    {"city": "Atlanta", "state": "GA", "taxonomy_description": "Oncology", "limit": 3},
    {"city": "Boston", "state": "MA", "taxonomy_description": "Rheumatology", "limit": 3},
    {"city": "Dallas", "state": "TX", "taxonomy_description": "Gastroenterology", "limit": 3},
    {"city": "Phoenix", "state": "AZ", "taxonomy_description": "Nephrology", "limit": 3},
]

def fetch_doctors():
    all_doctors = []
    for search in SEARCHES:
        params = {"version": "2.1", "enumeration_type": "NPI-1", **search}
        try:
            resp = httpx.get(NPPES_URL, params=params, timeout=15)
            data = resp.json()
            for p in data.get("results", []):
                b = p.get("basic", {})
                name = f'{b.get("first_name", "")} {b.get("last_name", "")}'.strip().title()
                cred = b.get("credential", "")
                spec = p.get("taxonomies", [{}])[0].get("desc", "")
                npi = p["number"]
                city = search["city"]
                state = search["state"]
                if name and len(name) > 3:
                    all_doctors.append({
                        "name": f"Dr. {name}" + (f", {cred}" if cred else ""),
                        "npi": npi,
                        "specialty": spec,
                        "city": city,
                        "state": state,
                    })
            print(f"  {search['city']}, {search['state']} — {search['taxonomy_description']}: {len(data.get('results', []))} doctors")
        except Exception as e:
            print(f"  {search['city']} — {search['taxonomy_description']}: ERROR {e}")
        time.sleep(0.3)  # Be nice to the API

    return all_doctors


if __name__ == "__main__":
    print("Fetching real doctors from NPPES...")
    doctors = fetch_doctors()
    print(f"\nTotal: {len(doctors)} real doctors fetched")

    # Save to JSON for seed.py to use
    with open("scripts/real_doctors.json", "w") as f:
        json.dump(doctors, f, indent=2)
    print(f"Saved to scripts/real_doctors.json")
