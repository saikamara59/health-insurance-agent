from pydantic import BaseModel, Field, field_validator


class CompareRequest(BaseModel):
    zip_code: str = Field(..., description="5-digit US zip code")
    age: int = Field(..., ge=18, le=120, description="Age between 18 and 120")
    income_level: str = Field(..., description="Income level: low, medium, or high")
    medications: list[str] = Field(
        default_factory=list, max_length=10, description="Optional list of medications"
    )
    procedures: list[str] = Field(
        default_factory=list, max_length=10, description="Optional list of procedures"
    )

    @field_validator("zip_code")
    @classmethod
    def validate_zip_code(cls, v: str) -> str:
        if len(v) != 5 or not v.isdigit():
            raise ValueError("Zip code must be exactly 5 digits")
        return v

    @field_validator("income_level")
    @classmethod
    def validate_income_level(cls, v: str) -> str:
        allowed = {"low", "medium", "high"}
        if v not in allowed:
            raise ValueError(f"Income level must be one of: {', '.join(sorted(allowed))}")
        return v


class EstimateRequest(BaseModel):
    plan_id: str = Field(..., description="Plan ID to estimate costs for")
    item_name: str = Field(..., description="Medication or procedure name")
    item_type: str = Field(..., description="Type: medication or procedure")

    @field_validator("item_type")
    @classmethod
    def validate_item_type(cls, v: str) -> str:
        allowed = {"medication", "procedure"}
        if v not in allowed:
            raise ValueError(f"Item type must be one of: {', '.join(sorted(allowed))}")
        return v


class PlanSummary(BaseModel):
    plan_name: str
    plan_id: str
    monthly_premium: float
    annual_deductible: float
    out_of_pocket_max: float
    star_rating: float = Field(..., ge=1.0, le=5.0)
    plan_type: str
    drug_coverage: bool
    estimated_medication_costs: dict[str, float] | None = None
    estimated_procedure_costs: dict[str, float] | None = None


class CompareResponse(BaseModel):
    session_id: str
    zip_code: str
    plans: list[PlanSummary]
    recommendation: str
    disclaimer: str


class CostDetails(BaseModel):
    formulary_tier: str | None = None
    copay: float | None = None
    coinsurance_pct: float | None = None
    prior_auth_required: bool = False
    quantity_limit: str | None = None


class EstimateResponse(BaseModel):
    plan_name: str
    item_name: str
    item_type: str
    estimated_cost: float
    cost_details: CostDetails
    disclaimer: str


class DocumentSection(BaseModel):
    title: str
    content: str


class TranslateRequest(BaseModel):
    document_text: str = Field(..., description="Pasted Summary of Benefits text")
    question: str = Field(..., description="Specific question about the document")

    @field_validator("document_text")
    @classmethod
    def validate_document_text(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Document text cannot be empty")
        if len(v) > 50_000:
            raise ValueError("Document text must be at most 50,000 characters")
        return v

    @field_validator("question")
    @classmethod
    def validate_question(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Question cannot be empty")
        if len(v) > 500:
            raise ValueError("Question must be at most 500 characters")
        return v


class TranslateResponse(BaseModel):
    session_id: str
    question: str
    answer: str
    relevant_sections: list[str]
    disclaimer: str


class PrescriptionInput(BaseModel):
    name: str
    fills_per_year: int = Field(..., ge=1, le=365)


class ProcedureInput(BaseModel):
    name: str
    count: int = Field(..., ge=1, le=365)


class UsageInput(BaseModel):
    doctor_visits_per_year: int = Field(..., ge=0, le=365)
    prescriptions: list[PrescriptionInput] = Field(
        default_factory=list, max_length=20
    )
    procedures: list[ProcedureInput] = Field(
        default_factory=list, max_length=20
    )


class CalculateRequest(BaseModel):
    session_id: str | None = None
    zip_code: str | None = None
    income_level: str | None = None
    usage: UsageInput

    @field_validator("zip_code")
    @classmethod
    def validate_zip_code(cls, v: str | None) -> str | None:
        if v is not None and (len(v) != 5 or not v.isdigit()):
            raise ValueError("Zip code must be exactly 5 digits")
        return v

    @field_validator("income_level")
    @classmethod
    def validate_income_level(cls, v: str | None) -> str | None:
        if v is not None and v not in {"low", "medium", "high"}:
            raise ValueError("Income level must be one of: high, low, medium")
        return v

    def model_post_init(self, __context: object) -> None:
        if self.session_id is None and self.zip_code is None:
            raise ValueError(
                "Either session_id or zip_code must be provided"
            )
        if self.session_id is None and self.income_level is None:
            raise ValueError(
                "income_level is required when using zip_code instead of session_id"
            )


class PrescriptionDetail(BaseModel):
    name: str
    cost_per_fill: float
    annual_cost: float


class ProcedureDetail(BaseModel):
    name: str
    cost_per_visit: float
    annual_cost: float


class CostBreakdown(BaseModel):
    premium_total: float
    deductible_spent: float
    doctor_visit_costs: float
    prescription_costs: float
    procedure_costs: float
    total_before_oop_cap: float
    oop_cap_applied: bool
    final_care_cost: float


class PlanCostResult(BaseModel):
    plan_name: str
    plan_id: str
    annual_premium: float
    annual_care_cost: float
    total_annual_cost: float
    breakdown: CostBreakdown
    prescription_details: list[PrescriptionDetail]
    procedure_details: list[ProcedureDetail]


class CalculateResponse(BaseModel):
    session_id: str
    plans: list[PlanCostResult]
    recommendation: str
    disclaimer: str


class AppealRequest(BaseModel):
    denial_text: str = Field(..., description="Pasted denial letter text")
    additional_context: str = Field(
        default="", description="Optional additional context from the user"
    )

    @field_validator("denial_text")
    @classmethod
    def validate_denial_text(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Denial text cannot be empty")
        if len(v) > 50_000:
            raise ValueError("Denial text must be at most 50,000 characters")
        return v

    @field_validator("additional_context")
    @classmethod
    def validate_additional_context(cls, v: str) -> str:
        if len(v) > 1_000:
            raise ValueError("Additional context must be at most 1,000 characters")
        return v


class DenialAnalysis(BaseModel):
    denial_reason_code: str | None
    denial_reason: str
    treatment_denied: str
    policy_section_cited: str | None
    appeal_deadline: str | None
    denial_date: str | None


class CoverageArgument(BaseModel):
    cms_rule: str
    common_appeal_grounds: list[str]
    success_precedents: list[str]


class AppealResponse(BaseModel):
    session_id: str
    denial_analysis: DenialAnalysis
    coverage_argument: CoverageArgument
    appeal_letter: str
    disclaimer: str


class ProviderInput(BaseModel):
    name: str
    npi: str | None = None


class VerifyRequest(BaseModel):
    session_id: str | None = None
    zip_code: str | None = None
    income_level: str | None = None
    providers: list[ProviderInput] = Field(default_factory=list, max_length=10)
    prescriptions: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("zip_code")
    @classmethod
    def validate_zip_code(cls, v: str | None) -> str | None:
        if v is not None and (len(v) != 5 or not v.isdigit()):
            raise ValueError("Zip code must be exactly 5 digits")
        return v

    @field_validator("income_level")
    @classmethod
    def validate_income_level(cls, v: str | None) -> str | None:
        if v is not None and v not in {"low", "medium", "high"}:
            raise ValueError("Income level must be one of: high, low, medium")
        return v

    def model_post_init(self, __context: object) -> None:
        if self.session_id is None and self.zip_code is None:
            raise ValueError(
                "Either session_id or zip_code must be provided"
            )
        if self.session_id is None and self.income_level is None:
            raise ValueError(
                "income_level is required when using zip_code instead of session_id"
            )


class ProviderResult(BaseModel):
    name: str
    npi: str | None
    npi_verified: bool
    specialty: str | None
    in_network: bool
    warning: str | None


class FormularyResult(BaseModel):
    drug_name: str
    on_formulary: bool
    tier: str | None
    copay: float | None
    prior_auth_required: bool
    warning: str | None


class PlanNetworkResult(BaseModel):
    plan_name: str
    plan_id: str
    provider_results: list[ProviderResult]
    formulary_results: list[FormularyResult]


class VerifyResponse(BaseModel):
    session_id: str
    plans: list[PlanNetworkResult]
    recommendation: str
    disclaimer: str


# ── Phase 6A: Auth & Client Schemas ──────────────────────────────────────────


class BrokerCreate(BaseModel):
    email: str = Field(..., description="Broker email address")
    password: str = Field(..., min_length=8, description="Password (min 8 chars)")
    full_name: str = Field(..., description="Broker full name")

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        import re
        pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
        if not re.match(pattern, v):
            raise ValueError("Invalid email address")
        return v


class BrokerResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: str

    model_config = {"from_attributes": True}


class LoginRequest(BaseModel):
    email: str = Field(..., description="Broker email")
    password: str = Field(..., description="Broker password")


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class ClientCreate(BaseModel):
    full_name: str = Field(..., description="Client full name")
    zip_code: str = Field(..., description="5-digit US zip code")
    age: int = Field(..., ge=18, le=120, description="Age between 18 and 120")
    income_level: str = Field(..., description="Income level: low, medium, or high")
    doctors: list[dict] = Field(
        default_factory=list, description="List of doctor objects with name and npi"
    )
    prescriptions: list[str] = Field(
        default_factory=list, description="List of prescription names"
    )
    procedures: list[str] = Field(
        default_factory=list, description="List of procedure names"
    )

    @field_validator("zip_code")
    @classmethod
    def validate_zip_code(cls, v: str) -> str:
        if len(v) != 5 or not v.isdigit():
            raise ValueError("Zip code must be exactly 5 digits")
        return v

    @field_validator("income_level")
    @classmethod
    def validate_income_level(cls, v: str) -> str:
        allowed = {"low", "medium", "high"}
        if v not in allowed:
            raise ValueError(f"Income level must be one of: {', '.join(sorted(allowed))}")
        return v


class ClientResponse(BaseModel):
    id: str
    broker_id: str
    full_name: str
    zip_code: str
    age: int
    income_level: str
    doctors: list[dict]
    prescriptions: list[str]
    procedures: list[str]
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class ClientUpdate(BaseModel):
    full_name: str | None = None
    zip_code: str | None = None
    age: int | None = Field(default=None, ge=18, le=120)
    income_level: str | None = None
    doctors: list[dict] | None = None
    prescriptions: list[str] | None = None
    procedures: list[str] | None = None

    @field_validator("zip_code")
    @classmethod
    def validate_zip_code(cls, v: str | None) -> str | None:
        if v is not None and (len(v) != 5 or not v.isdigit()):
            raise ValueError("Zip code must be exactly 5 digits")
        return v

    @field_validator("income_level")
    @classmethod
    def validate_income_level(cls, v: str | None) -> str | None:
        if v is not None and v not in {"low", "medium", "high"}:
            raise ValueError(f"Income level must be one of: high, low, medium")
        return v


# Phase 6: Action History & Profile Schemas

class ActionHistoryCreate(BaseModel):
    client_id: str
    action_type: str
    request_data: dict = {}
    response_summary: dict = {}


class ActionHistoryResponse(BaseModel):
    id: str
    broker_id: str
    client_id: str
    action_type: str
    request_data: dict
    response_summary: dict
    created_at: str
    client_name: str | None = None

    model_config = {"from_attributes": True}


class BrokerProfileUpdate(BaseModel):
    full_name: str | None = None
    email: str | None = None


# ── Phase 7: RLHF Feedback Schemas ─────────────────────────────────────────


VALID_AGENT_TYPES = {"compare", "calculate", "translate", "appeal", "verify"}


class FeedbackCreate(BaseModel):
    output_id: str = Field(..., description="ID of the agent output being rated")
    agent_type: str = Field(..., description="Agent type: compare/calculate/translate/appeal/verify")
    accuracy: int = Field(..., ge=1, le=5, description="Accuracy rating 1-5")
    clarity: int = Field(..., ge=1, le=5, description="Clarity rating 1-5")
    helpfulness: int = Field(..., ge=1, le=5, description="Helpfulness rating 1-5")
    comment: str = Field(default="", max_length=2000, description="Optional comment")

    @field_validator("agent_type")
    @classmethod
    def validate_agent_type(cls, v: str) -> str:
        if v not in VALID_AGENT_TYPES:
            raise ValueError(
                f"agent_type must be one of: {', '.join(sorted(VALID_AGENT_TYPES))}"
            )
        return v


class FeedbackResponse(BaseModel):
    id: str
    broker_id: str
    output_id: str
    agent_type: str
    accuracy: int
    clarity: int
    helpfulness: int
    comment: str
    created_at: str

    model_config = {"from_attributes": True}


class AgentFeedbackStats(BaseModel):
    agent_type: str
    total_feedback: int
    avg_accuracy: float
    avg_clarity: float
    avg_helpfulness: float
    combined_avg: float


class FeedbackAnalytics(BaseModel):
    period_days: int
    agents: list[AgentFeedbackStats]
    overall_avg: float
    total_feedback: int


class WeeklyReport(BaseModel):
    period_days: int
    agents: list[AgentFeedbackStats]
    overall_avg: float
    worst_agent: str | None
    best_agent: str | None
    low_score_count: int
    top_output_ids: list[str]
    bottom_output_ids: list[str]
