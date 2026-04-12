from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from healthflow.api.routes import router
from healthflow.auth.router import auth_router
from healthflow.api.client_router import client_router
from healthflow.api.history_router import history_router
from healthflow.feedback.router import feedback_router


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

app.include_router(router)
app.include_router(auth_router)
app.include_router(client_router)
app.include_router(history_router)
app.include_router(feedback_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("healthflow.main:app", host="0.0.0.0", port=8000, reload=True)
