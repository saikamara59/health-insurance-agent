"""Pydantic schemas for the forensics replay tool.

Vocabulary mapping vs. the codebase:
  * member_id (spec)  → client_id (codebase) — the patient
  * tenant_id (spec)  → broker_id (codebase) — the user/owner
"""
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class AgentInvocation(BaseModel):
    agent: str
    invocation_id: uuid.UUID
    timestamp: datetime
    case_id: uuid.UUID | None = None
    endpoint: str
    event_type: str
    model_used: str | None = None
    duration_ms: int | None = None
    details_summary: str
    error: str | None = None
    phi_tables_touched: list[str] = Field(default_factory=list)
    phi_row_count: int = 0


class IntegrityCheck(BaseModel):
    entries_found: int
    gaps_detected: list[str] = Field(default_factory=list)
    tamper_evidence: Literal["clean", "suspect", "unknown"] = "unknown"
    notes: list[str] = Field(default_factory=list)


class CaseTimeline(BaseModel):
    case_id: uuid.UUID | None = None
    member_id_hash: str | None = None
    time_range: tuple[datetime, datetime] | None = None
    tenant_id: uuid.UUID
    invocations: list[AgentInvocation] = Field(default_factory=list)
    decision_chain: list[str] = Field(default_factory=list)
    integrity: IntegrityCheck


# Route request models — discriminated by `mode`.

class ReplayCaseRequest(BaseModel):
    mode: Literal["case"] = "case"
    case_id: uuid.UUID


class ReplayMemberRequest(BaseModel):
    mode: Literal["member"] = "member"
    client_id: uuid.UUID
    from_ts: datetime
    to_ts: datetime


class ReplayAgentRequest(BaseModel):
    mode: Literal["agent"] = "agent"
    agent: str
    from_ts: datetime
    to_ts: datetime
