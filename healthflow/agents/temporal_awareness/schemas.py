"""Pydantic schemas for the Temporal Awareness Agent.

Public types live here so the deadline engine, classifier, agent, and route
all import from one source.
"""
from datetime import date
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class EventType(str, Enum):
    OPEN_ENROLLMENT = "open_enrollment"
    MEDICARE_AEP = "medicare_aep"
    SEP_JOB_LOSS = "sep_job_loss"
    SEP_MARRIAGE = "sep_marriage"
    SEP_BIRTH = "sep_birth"
    SEP_MOVE = "sep_move"
    SEP_DIVORCE = "sep_divorce"
    PA_APPEAL = "pa_appeal"


_SEP_EVENTS = frozenset({
    EventType.SEP_JOB_LOSS,
    EventType.SEP_MARRIAGE,
    EventType.SEP_BIRTH,
    EventType.SEP_MOVE,
    EventType.SEP_DIVORCE,
})


def is_sep_event(event_type: EventType) -> bool:
    return event_type in _SEP_EVENTS


Urgency = Literal["critical", "high", "medium", "low"]
PlanType = Literal["HMO", "PPO", "EPO", "POS", "MA"]


class Action(BaseModel):
    step: int
    description: str
    target_date: date
    completed: bool = False


class ActionPlan(BaseModel):
    event_type: EventType
    trigger_date: date
    deadline: date
    days_remaining: int
    urgency: Urgency
    actions: list[Action]


class ClassifiedEvent(BaseModel):
    """Structured output from the Haiku classifier."""

    event_type: EventType
    trigger_date: date = Field(..., description="The qualifying event date, or today if not specified")
    plan_type: PlanType | None = Field(None, description="Required for PA appeal; ignored for other events")


class TemporalRequest(BaseModel):
    """One request shape supporting either structured input OR natural-language input.

    Provide one of:
      - `event` (a fully-specified ClassifiedEvent)
      - `description` (free-text; the classifier will infer event_type + trigger_date)
    """

    event: ClassifiedEvent | None = None
    description: str | None = Field(None, max_length=2000)
    today: date | None = Field(
        None,
        description="Override 'today' for deterministic testing/demos; defaults to date.today()",
    )

    @model_validator(mode="after")
    def _exactly_one_input(self) -> "TemporalRequest":
        if (self.event is None) == (self.description is None):
            raise ValueError("Provide exactly one of: 'event' (structured) or 'description' (natural language)")
        return self
