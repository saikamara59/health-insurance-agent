import uuid

from fastapi import APIRouter, HTTPException, Path

from healthflow.agents.appeal_agent import AppealAgent
from healthflow.agents.comparison_agent import ComparisonAgent
from healthflow.agents.cost_calculator_agent import CostCalculatorAgent
from healthflow.agents.harness import Harness
from healthflow.agents.network_agent import NetworkAgent
from healthflow.agents.translation_agent import TranslationAgent
from healthflow.memory.session import InMemoryStore
from healthflow.models.schemas import (
    AppealRequest,
    AppealResponse,
    CalculateRequest,
    CalculateResponse,
    CompareRequest,
    CompareResponse,
    CostDetails,
    EstimateRequest,
    EstimateResponse,
    PlanSummary,
    TranslateRequest,
    TranslateResponse,
    VerifyRequest,
    VerifyResponse,
)
from healthflow.tools.cms_fetcher import MockCMSFetcher
from healthflow.tools.cost_estimator import CostEstimator
from healthflow.tools.document_parser import DocumentParser
from healthflow.tools.plan_parser import PlanParser

router = APIRouter()

fetcher = MockCMSFetcher()
parser = PlanParser()
estimator = CostEstimator()
harness = Harness()
session_store = InMemoryStore()
document_parser = DocumentParser()

DISCLAIMER = (
    "This is a plan comparison tool, not medical advice. "
    "Consult a licensed healthcare professional for medical decisions."
)

ESTIMATE_DISCLAIMER = (
    "These are estimates based on typical plan costs and your expected usage. "
    "Actual costs may vary based on provider network, specific services, and plan terms. "
    "This is not medical advice."
)

APPEAL_DISCLAIMER = (
    "This appeal letter template is for educational and informational purposes only. "
    "It does not constitute legal advice and does not guarantee appeal success. "
    "Consult a healthcare advocate or attorney for formal appeals. "
    "This is not medical advice."
)

VERIFY_DISCLAIMER = (
    "Network status and formulary coverage are based on publicly available data "
    "and may not reflect current plan contracts. Provider networks and drug "
    "formularies can change. Verify directly with your plan before making "
    "decisions. This is not medical advice."
)


@router.get("/health")
def health_check():
    return {"status": "healthy"}


@router.get("/plans/{zip_code}")
def get_plans(zip_code: str = Path(..., pattern=r"^\d{5}$")):
    raw_plans = fetcher.fetch_plans(zip_code)
    plans = [
        PlanSummary(
            plan_name=p["plan_name"],
            plan_id=p["plan_id"],
            monthly_premium=p["monthly_premium"],
            annual_deductible=p["annual_deductible"],
            out_of_pocket_max=p["out_of_pocket_max"],
            star_rating=p["star_rating"],
            plan_type=p["plan_type"],
            drug_coverage=p["drug_coverage"],
        )
        for p in raw_plans
    ]
    return {"zip_code": zip_code, "plans": plans}


@router.post("/compare", response_model=CompareResponse)
def compare_plans(request: CompareRequest):
    harness.audit.log("tool_called", {"tool": "cms_fetcher", "zip_code": request.zip_code})
    raw_plans = fetcher.fetch_plans(request.zip_code)
    harness.audit.log("plans_fetched", {"count": len(raw_plans)})

    ranked_plans = parser.parse_and_rank(raw_plans, request.income_level)

    for plan in ranked_plans:
        if request.medications:
            med_costs = estimator.estimate_multiple(
                request.medications, "medication", plan.plan_type
            )
            plan.estimated_medication_costs = {
                name: result["estimated_cost"]
                for name, result in med_costs.items()
                if result is not None
            }
        if request.procedures:
            proc_costs = estimator.estimate_multiple(
                request.procedures, "procedure", plan.plan_type
            )
            plan.estimated_procedure_costs = {
                name: result["estimated_cost"]
                for name, result in proc_costs.items()
                if result is not None
            }
            harness.audit.log("costs_estimated", {
                "medications": len(request.medications),
                "procedures": len(request.procedures),
            })

    agent = ComparisonAgent()
    raw_recommendation = agent.recommend(
        plans=ranked_plans,
        age=request.age,
        income_level=request.income_level,
        medications=request.medications or None,
        procedures=request.procedures or None,
    )

    recommendation = harness.filter_output(raw_recommendation)

    session_id = str(uuid.uuid4())
    session_store.save(session_id, {
        "zip_code": request.zip_code,
        "age": request.age,
        "income_level": request.income_level,
        "plan_ids": [p.plan_id for p in ranked_plans],
    })

    return CompareResponse(
        session_id=session_id,
        zip_code=request.zip_code,
        plans=ranked_plans,
        recommendation=recommendation,
        disclaimer=DISCLAIMER,
    )


@router.post("/estimate", response_model=EstimateResponse)
def estimate_cost(request: EstimateRequest):
    plan_type = "HMO"
    for zip_plans in [fetcher.fetch_plans(z) for z in ["10001"]]:
        for p in zip_plans:
            if p["plan_id"] == request.plan_id:
                plan_type = p["plan_type"]
                break

    result = estimator.estimate(request.item_name, request.item_type, plan_type)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"No cost data found for '{request.item_name}' ({request.item_type})",
        )

    return EstimateResponse(
        plan_name=request.plan_id,
        item_name=result["item_name"],
        item_type=result["item_type"],
        estimated_cost=result["estimated_cost"],
        cost_details=CostDetails(**result["cost_details"]),
        disclaimer=DISCLAIMER,
    )


@router.post("/translate", response_model=TranslateResponse)
def translate_coverage(request: TranslateRequest):
    harness.audit.log("tool_called", {"tool": "document_parser", "doc_length": len(request.document_text)})

    sections = document_parser.parse(request.document_text)
    relevant = document_parser.find_relevant_sections(sections, request.question)

    agent = TranslationAgent()
    raw_answer, section_titles = agent.translate(
        sections=relevant,
        question=request.question,
    )

    answer = harness.filter_output(raw_answer)

    session_id = str(uuid.uuid4())
    session_store.save(session_id, {
        "question": request.question,
        "section_titles": section_titles,
    })

    return TranslateResponse(
        session_id=session_id,
        question=request.question,
        answer=answer,
        relevant_sections=section_titles,
        disclaimer=DISCLAIMER,
    )


@router.post("/calculate", response_model=CalculateResponse)
def calculate_costs(request: CalculateRequest):
    if request.session_id:
        session_data = session_store.load(request.session_id)
        if session_data is None:
            raise HTTPException(status_code=404, detail="Session not found")
        plan_ids = session_data.get("plan_ids", [])
        zip_code = session_data.get("zip_code", "10001")
        raw_plans = fetcher.fetch_plans(zip_code)
        raw_plans = [p for p in raw_plans if p["plan_id"] in plan_ids] or raw_plans
        income_level = session_data.get("income_level", "medium")
    else:
        raw_plans = fetcher.fetch_plans(request.zip_code)
        income_level = request.income_level

    ranked_plans = parser.parse_and_rank(raw_plans, income_level)

    harness.audit.log("tool_called", {"tool": "cost_calculator", "plans": len(ranked_plans)})

    agent = CostCalculatorAgent()
    results, raw_recommendation = agent.calculate(ranked_plans, request.usage)

    recommendation = harness.filter_output(raw_recommendation)

    session_id = request.session_id or str(uuid.uuid4())
    session_store.save(session_id, {
        "zip_code": request.zip_code or (session_data.get("zip_code") if request.session_id else None),
        "income_level": income_level,
        "plan_ids": [r.plan_id for r in results],
        "calculation": True,
    })

    return CalculateResponse.model_validate({
        "session_id": session_id,
        "plans": [r.model_dump() for r in results],
        "recommendation": recommendation,
        "disclaimer": ESTIMATE_DISCLAIMER,
    })


@router.post("/appeal", response_model=AppealResponse)
def generate_appeal(request: AppealRequest):
    harness.audit.log("tool_called", {
        "tool": "appeal_agent",
        "denial_length": len(request.denial_text),
    })

    agent = AppealAgent()
    analysis, argument, appeal_letter, raw_recommendation = agent.process_appeal(
        request.denial_text,
        request.additional_context,
    )

    # Filter Claude's recommendation through the harness
    filtered_recommendation = harness.filter_output(raw_recommendation)

    session_id = str(uuid.uuid4())
    session_store.save(session_id, {
        "type": "appeal",
        "denial_code": analysis.denial_reason_code,
        "treatment_denied": analysis.treatment_denied,
    })

    return AppealResponse(
        session_id=session_id,
        denial_analysis=analysis,
        coverage_argument=argument,
        appeal_letter=appeal_letter,
        disclaimer=APPEAL_DISCLAIMER,
    )


@router.post("/verify", response_model=VerifyResponse)
def verify_network(request: VerifyRequest):
    if request.session_id:
        session_data = session_store.load(request.session_id)
        if session_data is None:
            raise HTTPException(status_code=404, detail="Session not found")
        plan_ids = session_data.get("plan_ids", [])
        zip_code = session_data.get("zip_code", "10001")
        raw_plans = fetcher.fetch_plans(zip_code)
        raw_plans = [p for p in raw_plans if p["plan_id"] in plan_ids] or raw_plans
        income_level = session_data.get("income_level", "medium")
    else:
        raw_plans = fetcher.fetch_plans(request.zip_code)
        income_level = request.income_level

    ranked_plans = parser.parse_and_rank(raw_plans, income_level)

    harness.audit.log("tool_called", {
        "tool": "network_agent",
        "providers": len(request.providers),
        "prescriptions": len(request.prescriptions),
    })

    agent = NetworkAgent()
    results, raw_recommendation = agent.verify(
        ranked_plans, request.providers, request.prescriptions
    )

    recommendation = harness.filter_output(raw_recommendation)

    session_id = request.session_id or str(uuid.uuid4())
    session_store.save(session_id, {
        "zip_code": request.zip_code or (session_data.get("zip_code") if request.session_id else None),
        "income_level": income_level,
        "plan_ids": [r.plan_id for r in results],
        "verification": True,
    })

    return VerifyResponse(
        session_id=session_id,
        plans=results,
        recommendation=recommendation,
        disclaimer=VERIFY_DISCLAIMER,
    )
