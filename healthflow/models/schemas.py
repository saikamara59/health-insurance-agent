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
