import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv

# Load .env before any module reads os.getenv (e.g., DATABASE_URL, ANTHROPIC_API_KEY).
# Existing process env wins — useful in docker/CI where vars are passed explicitly.
load_dotenv(override=False)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from healthflow.api.middleware import EndpointContextMiddleware, HTTPLoggingMiddleware

from healthflow.api.routes import router
from healthflow.auth.router import auth_router
from healthflow.auth.admin_router import admin_router
from healthflow.api.drug_router import drug_router
from healthflow.api.client_router import client_router
from healthflow.api.history_router import history_router
from healthflow.feedback.router import feedback_router
from healthflow.agents.temporal_awareness.routes import temporal_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database tables on startup (for development/testing)."""
    from healthflow.database.config import engine
    from healthflow.database.models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title="HealthFlow",
    description="AI-powered Medicare Advantage plan comparison service",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(HTTPLoggingMiddleware)
app.add_middleware(EndpointContextMiddleware)

app.include_router(router)
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(drug_router)
app.include_router(client_router)
app.include_router(history_router)
app.include_router(feedback_router)
app.include_router(temporal_router)


if os.getenv("HEALTHFLOW_TEST_MODE") == "1":
    from healthflow.api.test_router import test_router
    app.include_router(test_router)
    logging.warning("⚠️ test reset endpoint enabled — never run in production")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("healthflow.main:app", host="0.0.0.0", port=8000, reload=True)
