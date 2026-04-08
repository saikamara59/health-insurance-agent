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


@cli.command()
@click.option("--session-id", default="", help="Session ID from a prior /compare call")
@click.option("--zip-code", default="", help="5-digit US zip code")
@click.option(
    "--income",
    default="",
    type=click.Choice(["low", "medium", "high", ""], case_sensitive=False),
    help="Income level",
)
@click.option("--doctor-visits", prompt="Doctor visits per year", type=int, help="Expected doctor visits per year")
@click.option("--prescriptions", default="", help="Comma-separated name:fills pairs (e.g., Metformin:12,Ozempic:12)")
@click.option("--procedures", default="", help="Comma-separated name:count pairs (e.g., MRI:2,Blood work:4)")
def calculate(session_id: str, zip_code: str, income: str, doctor_visits: int, prescriptions: str, procedures: str):
    """Calculate estimated annual out-of-pocket costs."""
    payload: dict = {
        "usage": {
            "doctor_visits_per_year": doctor_visits,
            "prescriptions": [],
            "procedures": [],
        }
    }

    if session_id:
        payload["session_id"] = session_id
    elif zip_code:
        payload["zip_code"] = zip_code
        payload["income_level"] = income or "medium"
    else:
        click.echo("Error: Provide --session-id or --zip-code")
        sys.exit(1)

    for item in prescriptions.split(","):
        item = item.strip()
        if not item:
            continue
        parts = item.rsplit(":", 1)
        if len(parts) == 2:
            payload["usage"]["prescriptions"].append(
                {"name": parts[0].strip(), "fills_per_year": int(parts[1])}
            )
        else:
            payload["usage"]["prescriptions"].append(
                {"name": parts[0].strip(), "fills_per_year": 12}
            )

    for item in procedures.split(","):
        item = item.strip()
        if not item:
            continue
        parts = item.rsplit(":", 1)
        if len(parts) == 2:
            payload["usage"]["procedures"].append(
                {"name": parts[0].strip(), "count": int(parts[1])}
            )
        else:
            payload["usage"]["procedures"].append(
                {"name": parts[0].strip(), "count": 1}
            )

    try:
        response = httpx.post(f"{BASE_URL}/calculate", json=payload, timeout=30.0)
        response.raise_for_status()
    except httpx.ConnectError:
        click.echo("Error: Cannot connect to HealthFlow API. Is the server running?")
        sys.exit(1)
    except httpx.HTTPStatusError as e:
        click.echo(f"Error: {e.response.json().get('detail', str(e))}")
        sys.exit(1)

    data = response.json()

    click.echo("\n" + "=" * 60)
    click.echo("  HEALTHFLOW — Annual Cost Calculator")
    click.echo("=" * 60)

    for i, plan in enumerate(data["plans"], 1):
        b = plan["breakdown"]
        click.echo(f"\n--- #{i}: {plan['plan_name']} ---")
        click.echo(f"  Annual Premium:    ${plan['annual_premium']:>10,.2f}")
        click.echo(f"  Annual Care Cost:  ${plan['annual_care_cost']:>10,.2f}")
        click.echo(f"  TOTAL ANNUAL COST: ${plan['total_annual_cost']:>10,.2f}")
        click.echo(f"  ---")
        click.echo(f"  Doctor Visits:     ${b['doctor_visit_costs']:>10,.2f}")
        click.echo(f"  Prescriptions:     ${b['prescription_costs']:>10,.2f}")
        click.echo(f"  Procedures:        ${b['procedure_costs']:>10,.2f}")
        if b["oop_cap_applied"]:
            click.echo(f"  ** OOP Max cap applied — saved ${b['total_before_oop_cap'] - b['final_care_cost']:,.2f}")

        if plan["prescription_details"]:
            click.echo("  Rx Breakdown:")
            for rx in plan["prescription_details"]:
                click.echo(f"    - {rx['name']}: ${rx['cost_per_fill']:.2f}/fill x {int(rx['annual_cost'] / rx['cost_per_fill'])} = ${rx['annual_cost']:.2f}/yr")

        if plan["procedure_details"]:
            click.echo("  Procedure Breakdown:")
            for proc in plan["procedure_details"]:
                click.echo(f"    - {proc['name']}: ${proc['cost_per_visit']:.2f} x {int(proc['annual_cost'] / proc['cost_per_visit'])} = ${proc['annual_cost']:.2f}/yr")

    click.echo("\n" + "-" * 60)
    click.echo("\nRECOMMENDATION:\n")
    click.echo(data["recommendation"])
    click.echo(f"\n{data['disclaimer']}")
    click.echo(f"\nSession ID: {data['session_id']}")
    click.echo()


@cli.command()
@click.option(
    "--denial-text",
    default="",
    help="Pasted denial letter text (prompted if not provided)",
)
@click.option("--context", default="", help="Optional additional context")
def appeal(denial_text: str, context: str):
    """Generate an appeal letter from a denial letter."""
    if not denial_text:
        denial_text = click.prompt(
            "Paste your denial letter text (end with Enter on an empty line)",
            default="",
            prompt_suffix="\n> ",
        )
        if not denial_text.strip():
            click.echo("Error: Denial text cannot be empty.")
            sys.exit(1)

    payload: dict = {
        "denial_text": denial_text,
        "additional_context": context,
    }

    try:
        response = httpx.post(f"{BASE_URL}/appeal", json=payload, timeout=60.0)
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
    click.echo("  HEALTHFLOW — Claims Denial Appeal")
    click.echo("=" * 60)

    analysis = data["denial_analysis"]
    click.echo("\n--- Denial Analysis ---")
    click.echo(f"  Denial Code:     {analysis.get('denial_reason_code', 'N/A') or 'N/A'}")
    click.echo(f"  Denial Reason:   {analysis.get('denial_reason', 'N/A')}")
    click.echo(f"  Treatment:       {analysis.get('treatment_denied', 'N/A')}")
    click.echo(f"  Policy Section:  {analysis.get('policy_section_cited', 'N/A') or 'N/A'}")
    click.echo(f"  Appeal Deadline: {analysis.get('appeal_deadline', 'N/A') or 'N/A'}")
    click.echo(f"  Denial Date:     {analysis.get('denial_date', 'N/A') or 'N/A'}")

    argument = data["coverage_argument"]
    click.echo("\n--- Coverage Argument ---")
    click.echo(f"  CMS Rule: {argument.get('cms_rule', 'N/A')}")
    click.echo("  Appeal Grounds:")
    for ground in argument.get("common_appeal_grounds", []):
        click.echo(f"    - {ground}")
    click.echo("  Precedents:")
    for precedent in argument.get("success_precedents", []):
        click.echo(f"    - {precedent}")

    click.echo("\n" + "-" * 60)
    click.echo("\nAPPEAL LETTER:\n")
    click.echo(data["appeal_letter"])

    click.echo("\n" + "-" * 60)
    click.echo(f"\n{data['disclaimer']}")
    click.echo(f"\nSession ID: {data['session_id']}")
    click.echo()


if __name__ == "__main__":
    cli()
