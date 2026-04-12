# HealthFlow Phase 7: RLHF Feedback and Learning System — Design Spec

## Overview

Add a feedback loop where brokers rate every AI agent output (accuracy, clarity, helpfulness on a 1-5 scale). A reward model scores outputs weekly, flags low-quality patterns, and identifies top-rated examples. A prompt updater uses the best examples to generate improved few-shot prompts. Simple flag-based A/B testing routes a percentage of requests to updated prompts to measure improvement.

## The Loop (Simple Explanation)

1. AI gives answer → broker rates it → stored in database
2. Weekly: reward model scores all ratings → finds best and worst outputs
3. Prompt updater takes best-rated outputs → creates improved few-shot prompts
4. New prompts tested on 20% of requests (A/B split)
5. If updated prompts score higher → roll out to all → repeat

## Database Models

### `feedback` table

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | Primary key |
| broker_id | UUID | FK → brokers.id, indexed |
| output_id | VARCHAR(255) | Links to action_history.id or session_id |
| agent_type | VARCHAR(50) | compare/calculate/translate/appeal/verify |
| accuracy | INTEGER | 1-5 scale, required |
| clarity | INTEGER | 1-5 scale, required |
| helpfulness | INTEGER | 1-5 scale, required |
| comment | TEXT | Optional free text, max 2000 chars |
| created_at | TIMESTAMP | Server default now() |

### `prompt_variants` table

| Column | Type | Notes |
|--------|------|-------|
| id | UUID | Primary key |
| agent_type | VARCHAR(50) | Which agent this variant applies to |
| variant_name | VARCHAR(100) | "control" or "updated_v1" etc. |
| prompt_template | TEXT | The few-shot prompt text |
| is_active | BOOLEAN | Default true |
| traffic_pct | INTEGER | 0-100, percentage of requests using this variant |
| created_at | TIMESTAMP | Server default now() |

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /feedback | Yes | Submit feedback on an agent output |
| GET | /feedback | Yes | List feedback for current broker (filterable) |
| GET | /feedback/analytics | Yes | Aggregated feedback stats per agent type |
| POST | /feedback/reward-score | Yes | Trigger reward model scoring manually |
| GET | /feedback/weekly-report | Yes | Weekly summary report |

## New/Modified Files

### New: `healthflow/feedback/__init__.py`

Empty package marker.

### New: `healthflow/feedback/collector.py`

`FeedbackCollector` class handles feedback CRUD.

**Interface:**
- `submit(db, broker_id, output_id, agent_type, accuracy, clarity, helpfulness, comment) -> Feedback`
- `list_feedback(db, broker_id, agent_type=None, limit=50) -> list[Feedback]`
- `get_analytics(db, days=30) -> dict` — returns per-agent averages

### New: `healthflow/feedback/reward_model.py`

`RewardModel` class scores outputs based on collected feedback.

**Interface:**
- `score_outputs(db, agent_type=None, days=7) -> RewardReport`

**Logic:**
1. Query all feedback from the last N days
2. Group by agent_type
3. Calculate average accuracy, clarity, helpfulness per agent
4. Flag outputs with combined avg < 3.0 as "needs improvement"
5. Identify top outputs (combined avg > 4.5) as few-shot candidates
6. Return report with: per-agent scores, low-score count, top outputs, bottom outputs

**RewardReport structure:**
```python
{
    "period_days": 7,
    "agents": {
        "compare": {
            "total_feedback": 42,
            "avg_accuracy": 4.2,
            "avg_clarity": 3.8,
            "avg_helpfulness": 4.0,
            "combined_avg": 4.0,
            "low_score_count": 3,
            "top_outputs": ["output_id_1", "output_id_2"],
            "bottom_outputs": ["output_id_5"]
        },
        ...
    },
    "overall_avg": 3.9,
    "worst_agent": "translate",
    "best_agent": "compare"
}
```

### New: `healthflow/feedback/prompt_updater.py`

`PromptUpdater` class generates improved prompts from top-rated outputs.

**Interface:**
- `generate_few_shot(db, agent_type, top_n=3) -> str` — takes top-rated outputs from action_history, extracts input/output pairs, formats as few-shot examples appended to the system prompt
- `create_variant(db, agent_type, prompt_template, traffic_pct=20) -> PromptVariant` — inserts new prompt variant, reduces existing variants' traffic_pct proportionally
- `get_active_variant(db, agent_type) -> PromptVariant | None` — randomly selects a variant based on traffic_pct weights

### New: `healthflow/feedback/router.py`

FastAPI router with prefix `/feedback`.

**POST /feedback:**
- Body: `FeedbackCreate` (output_id, agent_type, accuracy 1-5, clarity 1-5, helpfulness 1-5, comment optional)
- Returns: `FeedbackResponse` (201)
- Requires auth

**GET /feedback:**
- Query params: `agent_type` (optional), `limit` (default 50)
- Returns: `list[FeedbackResponse]`
- Filtered to current broker

**GET /feedback/analytics:**
- Query params: `days` (default 30)
- Returns: `FeedbackAnalytics` — per-agent averages, total counts

**POST /feedback/reward-score:**
- Query params: `days` (default 7)
- Returns: reward model report
- Triggers the scoring pipeline

**GET /feedback/weekly-report:**
- Returns: full weekly summary (worst agent, best agent, recommendations)

## A/B Testing (Simple Flag-Based)

**How it works:**
1. Each agent has a "control" variant (100% traffic) created on first use
2. When prompt_updater creates a new variant, it sets traffic_pct=20 and reduces control to 80%
3. On each agent request, `get_active_variant()` does a weighted random selection
4. The chosen variant's prompt_template is used as the system prompt
5. Which variant was used is logged in `action_history.response_summary.variant_id`
6. After enough feedback on both variants, broker can compare scores and promote the winner

**No separate experiment UI** — managed via API calls. Future phase can add dashboard controls.

## Pydantic Schemas

```python
class FeedbackCreate(BaseModel):
    output_id: str
    agent_type: str  # compare/calculate/translate/appeal/verify
    accuracy: int = Field(..., ge=1, le=5)
    clarity: int = Field(..., ge=1, le=5)
    helpfulness: int = Field(..., ge=1, le=5)
    comment: str = Field(default="", max_length=2000)

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
```

## Modified Files

### `healthflow/database/models.py`
Add `Feedback` and `PromptVariant` ORM models.

### `healthflow/models/schemas.py`
Add `FeedbackCreate`, `FeedbackResponse`, `AgentFeedbackStats`, `FeedbackAnalytics`, `WeeklyReport`.

### `healthflow/main.py`
Include `feedback_router`.

## Testing

### `healthflow/tests/test_feedback_collector.py`
1. Submit feedback — 201, verify fields
2. Submit feedback with invalid rating (0 or 6) — 422
3. List feedback — returns only broker's feedback
4. List feedback filtered by agent_type

### `healthflow/tests/test_reward_model.py`
1. Score outputs with mixed feedback — correct averages
2. Flag low-scoring outputs (avg < 3.0)
3. Identify top outputs (avg > 4.5)
4. Empty feedback returns zero scores

### `healthflow/tests/test_prompt_updater.py`
1. Generate few-shot from top outputs — returns formatted prompt
2. Create variant — inserts with correct traffic_pct
3. Get active variant — returns weighted random selection

### `healthflow/tests/test_feedback_routes.py`
1. POST /feedback — valid submission
2. GET /feedback — list with filter
3. GET /feedback/analytics — returns per-agent stats
4. POST /feedback/reward-score — returns report
5. Auth required on all endpoints

## What This Does NOT Do

- No automatic prompt deployment (manual review required)
- No real-time model fine-tuning (uses few-shot prompt engineering)
- No client-facing feedback (broker only for Phase 7)
- No experiment management UI (API only)
- No statistical significance calculation (simple average comparison)
