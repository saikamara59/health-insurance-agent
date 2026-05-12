---
name: healthcare-glossary
description: Use when explaining healthflow code that touches plan benefits, formularies, provider networks, or appeals — or when the user (who is learning healthtech) asks what a healthcare term means. Reference for the specific healthcare concepts this codebase models, with pointers to where each one lives in code.
---

# Healthcare Glossary (HealthFlow-specific)

Definitions framed by how *this codebase* uses each term. For broader textbook definitions, search the web; this skill exists so explanations stay anchored to the actual fields, files, and workflows in HealthFlow.

## The two markets HealthFlow touches

| Market | Who it's for | Where in code |
|---|---|---|
| **Medicare Advantage (MA)** | People 65+ or with certain disabilities; private-insurer alternative to Original Medicare. | `SEED_PLANS` in `scripts/refresh_data.py`, plans table in `healthflow_data.db` |
| **ACA Marketplace** | Under-65 individuals/families buying on Healthcare.gov. | In flight — `MARKETPLACE_API_KEY` fetcher per [[cms-aca-pivot]] |

A broker using HealthFlow needs to compare options *within* one market for a given client — never mix MA plans against ACA plans for the same person.

## Plan structure (DB fields → meaning)

These map 1:1 to the `plans` table schema in `scripts/refresh_data.py:93-105`.

| Field | Plain English | Broker context |
|---|---|---|
| `plan_type` | HMO / PPO / HMO-POS / HMO-SNP | HMO = must use in-network + referrals. PPO = out-of-network OK at higher cost. HMO-POS = HMO with limited out-of-network. SNP = Special Needs Plan (e.g. dual Medicare+Medicaid). |
| `monthly_premium` | What the client pays every month *just to have the plan*. | Many MA plans are $0 premium — the broker still has to point out the deductible/OOP. |
| `annual_deductible` | What client pays out-of-pocket before insurance starts paying. | $0 deductible is a common MA selling point. |
| `out_of_pocket_max` (OOP max) | Annual ceiling on what client can pay in cost-sharing. After this, plan covers 100%. | The single most important number for a client with chronic conditions. |
| `star_rating` | CMS quality score, 1–5. | 4+ stars = "good plan" in broker shorthand. CMS pays bonuses for 4+. |
| `drug_coverage` | Whether the plan includes Part D (prescription drugs). | An MA plan with `drug_coverage=1` is called an MA-PD. Without it, client needs a separate Part D plan. |

## Formulary (drug coverage)

A **formulary** is the plan's list of covered drugs, organized into **tiers**. HealthFlow's `drugs` table has tiers 1–4 (`scripts/refresh_data.py:272+`):

| Tier | Examples in seed data | What it means for the client |
|---|---|---|
| **Tier 1 — Generic** | Metformin, Lisinopril, Atorvastatin | Cheapest. ~$3–$10 copay. Mostly old, off-patent drugs. |
| **Tier 2 — Preferred Brand** | Lantus, Symbicort, Januvia | Brand-name but plan negotiated good price. ~$25–$45. |
| **Tier 3 — Non-Preferred** | Eliquis, Jardiance, Xarelto | Brand drugs the plan would rather you not use. ~$47–$95. |
| **Tier 4 — Specialty** | Ozempic, Humira, Keytruda | High-cost specialty drugs (often biologics, oncology). $100+. Almost always require prior auth. |

**`prior_auth`** (`prior_auth=1` in the schema): client's doctor must justify the prescription to the insurer before it's covered. Common on Tier 3/4. A frequent source of denials → see appeals below.

**`quantity_limit`**: max amount per fill (e.g. "30-day supply"). Going over requires PA.

## Provider network (NPPES / NPI)

| Term | Meaning | Where in code |
|---|---|---|
| **NPI** | National Provider Identifier — unique 10-digit ID for every US healthcare provider. | `healthflow/tools/npi_client.py` |
| **NPPES** | National Plan & Provider Enumeration System — the federal registry of NPIs. HealthFlow queries this live to verify a doctor exists. | API client in `npi_client.py` |
| **In-network** | Provider has a contract with the plan; client pays in-network rates. | The `network_agent` checks this for a client's listed doctors. |
| **Out-of-network** | No contract; client pays much more (or not covered at all on HMO). | |

The `network_agent` answering "is my doctor covered?" is one of the most-asked broker questions per the README.

## Appeals (denials process)

The `appeal_agent` orchestrates appeals against insurer denials. The codebase encodes the federal Medicare appeals framework — see `healthflow/agents/appeal_agent.py:19-33`:

| Stage | What happens |
|---|---|
| **Denial / EOB** | Insurer issues an Explanation of Benefits saying a claim won't be paid (or only partly paid). |
| **Redetermination** | First appeal level — back to the same insurer asking them to look again. |
| **Reconsideration** | Second level — independent reviewer (Qualified Independent Contractor). |
| **ALJ hearing, Council, federal court** | Higher levels, rarely reached. |

Federal cite the agent uses: **42 CFR §405.904** (Medicare appeals rights). Appeals never *guarantee* an outcome — the agent's system prompt is explicit about that.

## Geo / data joins

| Term | Meaning | Where |
|---|---|---|
| **ZIP** | USPS code. What clients give brokers. | `plan_zips` table |
| **County FIPS** | 5-digit federal county code. CMS publishes plan availability *by county*, not ZIP. | `plan_counties` table |
| **HUD ZIP↔County crosswalk** | HUD publishes the mapping (ZIPs cross county lines). HealthFlow uses this to convert a client's ZIP into the counties served. | `download_hud_zip_county` in `scripts/refresh_data.py` |

A ZIP can map to multiple counties → a client might have access to plans they'd miss with a naive single-county lookup. This is why `build_zip_mappings` does the join properly.

## Drug identifiers

| Term | Meaning |
|---|---|
| **Generic name** | The chemical/scientific name (e.g. `metformin hydrochloride`). |
| **Brand name** | The marketed name (e.g. `Glucophage`). |
| **NDC** | National Drug Code — 10–11 digit identifier, FDA-issued, uniquely identifies a specific drug *and packaging*. The same drug at two strengths or two pack sizes has two NDCs. |
| **Dosage form** | Tablet, Capsule, Injection, Inhaler, etc. — affects how it's administered and sometimes which tier. |

## Things the system prompts forbid (and why)

The agents are constrained — knowing why helps when reviewing prompt changes:

- **No medical advice** (`comparison_agent.py:20`, `appeal_agent.py:14`): brokers aren't doctors; the LLM definitely isn't. Saying "you should switch from drug X to drug Y" is practicing medicine.
- **No appeal-outcome guarantees** (`appeal_agent.py:14`): outcomes are insurer/judge discretion; promises create legal exposure.
- **Never diagnose** (`comparison_agent.py:20`): same reason as medical advice.

If a prompt change weakens these, push back.
