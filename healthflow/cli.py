import sys

import click
import httpx

BASE_URL = "http://localhost:8000"


@click.group()
def cli():
    """HealthFlow — AI-powered Medicare plan comparison tool."""
    pass


@cli.command()
@click.option("--zip-code", prompt="Zip code", help="5-digit US zip code")
@click.option("--age", prompt="Age", type=int, help="Your age (18-120)")
@click.option(
    "--income",
    prompt="Income level",
    type=click.Choice(["low", "medium", "high"]),
    help="Income level",
)
@click.option("--medications", default="", help="Comma-separated medication list")
@click.option("--procedures", default="", help="Comma-separated procedure list")
def compare(zip_code: str, age: int, income: str, medications: str, procedures: str):
    """Compare Medicare Advantage plans."""
    payload = {
        "zip_code": zip_code,
        "age": age,
        "income_level": income,
        "medications": [m.strip() for m in medications.split(",") if m.strip()],
        "procedures": [p.strip() for p in procedures.split(",") if p.strip()],
    }

    try:
        response = httpx.post(f"{BASE_URL}/compare", json=payload, timeout=30.0)
        response.raise_for_status()
    except httpx.ConnectError:
        click.echo("Error: Cannot connect to HealthFlow API. Is the server running?")
        click.echo("Start it with: python -m healthflow.main")
        sys.exit(1)
    except httpx.HTTPStatusError as e:
        click.echo(f"Error: {e.response.json().get('detail', str(e))}")
        sys.exit(1)

    data = response.json()

    click.echo("\n" + "=" * 60)
    click.echo("  HEALTHFLOW — Medicare Plan Comparison")
    click.echo("=" * 60)

    for i, plan in enumerate(data["plans"], 1):
        click.echo(f"\n--- Plan {i}: {plan['plan_name']} ---")
        click.echo(f"  ID:             {plan['plan_id']}")
        click.echo(f"  Type:           {plan['plan_type']}")
        click.echo(f"  Premium:        ${plan['monthly_premium']:.2f}/mo")
        click.echo(f"  Deductible:     ${plan['annual_deductible']:.2f}/yr")
        click.echo(f"  OOP Max:        ${plan['out_of_pocket_max']:.2f}")
        click.echo(f"  Star Rating:    {'*' * int(plan['star_rating'])} ({plan['star_rating']})")
        click.echo(f"  Drug Coverage:  {'Yes' if plan['drug_coverage'] else 'No'}")

        if plan.get("estimated_medication_costs"):
            click.echo("  Medication Costs:")
            for med, cost in plan["estimated_medication_costs"].items():
                click.echo(f"    - {med}: ${cost:.2f}/mo")

        if plan.get("estimated_procedure_costs"):
            click.echo("  Procedure Costs:")
            for proc, cost in plan["estimated_procedure_costs"].items():
                click.echo(f"    - {proc}: ${cost:.2f}")

    click.echo("\n" + "-" * 60)
    click.echo("\nRECOMMENDATION:\n")
    click.echo(data["recommendation"])
    click.echo(f"\nSession ID: {data['session_id']}")
    click.echo()


@cli.command()
@click.option("--plan-id", prompt="Plan ID", help="Plan ID (e.g., H3312-034)")
@click.option("--item", prompt="Item name", help="Medication or procedure name")
@click.option(
    "--type",
    "item_type",
    prompt="Type",
    type=click.Choice(["medication", "procedure"]),
    help="medication or procedure",
)
def estimate(plan_id: str, item: str, item_type: str):
    """Estimate cost for a medication or procedure."""
    payload = {"plan_id": plan_id, "item_name": item, "item_type": item_type}

    try:
        response = httpx.post(f"{BASE_URL}/estimate", json=payload, timeout=10.0)
        response.raise_for_status()
    except httpx.ConnectError:
        click.echo("Error: Cannot connect to HealthFlow API. Is the server running?")
        sys.exit(1)
    except httpx.HTTPStatusError as e:
        click.echo(f"Error: {e.response.json().get('detail', str(e))}")
        sys.exit(1)

    data = response.json()
    click.echo(f"\nCost Estimate for {data['item_name']} ({data['item_type']})")
    click.echo(f"  Plan: {data['plan_name']}")
    click.echo(f"  Estimated Cost: ${data['estimated_cost']:.2f}")
    details = data["cost_details"]
    if details.get("formulary_tier"):
        click.echo(f"  Formulary Tier: {details['formulary_tier']}")
    if details.get("prior_auth_required"):
        click.echo("  Prior Authorization: Required")
    if details.get("quantity_limit"):
        click.echo(f"  Quantity Limit: {details['quantity_limit']}")
    click.echo(f"\n{data['disclaimer']}")


if __name__ == "__main__":
    cli()
