from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.api.routes.authoritative_ingestion import router as authoritative_ingestion_router
from app.config import get_settings
from app.db.base import Base
from app.db.session import engine
from app.models import AnalysisReport, Company, IngestionRun, RiskEvent  # noqa: F401


settings = get_settings()
allow_origins = (
    ["*"]
    if settings.cors_origins == "*"
    else [item.strip() for item in settings.cors_origins.split(",") if item.strip()]
)

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=settings.cors_origins != "*",
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def create_tables() -> None:
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(api_router, prefix=settings.api_v1_prefix)
app.include_router(authoritative_ingestion_router, prefix=settings.api_v1_prefix)
