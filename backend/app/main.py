from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.projects import router as projects_router
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


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "environment": settings.environment}
