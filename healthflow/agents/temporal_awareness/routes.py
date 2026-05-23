"""FastAPI route for the Temporal Awareness Agent.

Single endpoint: POST /temporal/plan.

Accepts either a structured `event` payload OR a natural-language
`description`. Auth-gated like the rest of HealthFlow's authenticated
endpoints.
"""
from fastapi import APIRouter, Depends

from healthflow.agents.temporal_awareness.agent import TemporalAwarenessAgent
from healthflow.agents.temporal_awareness.schemas import ActionPlan, TemporalRequest
from healthflow.auth.dependencies import get_current_broker
from healthflow.database.models import Broker

temporal_router = APIRouter(prefix="/temporal", tags=["temporal"])


@temporal_router.post("/plan", response_model=ActionPlan)
def generate_plan(
    request: TemporalRequest,
    broker: Broker = Depends(get_current_broker),
) -> ActionPlan:
    """Generate a deadline-aware action plan for a health-insurance event.

    Provide exactly one of:
      - `event`: a structured ClassifiedEvent (event_type + trigger_date + optional plan_type)
      - `description`: free-text natural language; the classifier infers the event

    Optional `today` field overrides date.today() for deterministic demos.
    """
    agent = TemporalAwarenessAgent()
    return agent.generate_plan(request)
