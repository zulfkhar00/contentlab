from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.projects import router as projects_router
from app.api.v1.hypotheses import router as hypotheses_router
from app.api.v1.experiments import router as experiments_router
from app.api.v1.insights import router as insights_router
from app.api.v1.dev import router as dev_router
from app.config import settings

app = FastAPI(
    title="Content Lab API",
    version="0.1.0",
    docs_url="/api/docs" if settings.environment != "production" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects_router)
app.include_router(hypotheses_router)
app.include_router(experiments_router)
app.include_router(insights_router)
if settings.environment != "production":
    app.include_router(dev_router)


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "environment": settings.environment}
