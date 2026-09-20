from fastapi import APIRouter

from app.api.routes import (
    agent_analysis,
    analysis_reports,
    companies,
    company_profile,
    ingestion,
    knowledge_base,
    risk_events,
)


api_router = APIRouter()
api_router.include_router(companies.router)
api_router.include_router(company_profile.router)
api_router.include_router(risk_events.router)
api_router.include_router(analysis_reports.router)
api_router.include_router(knowledge_base.router)
api_router.include_router(agent_analysis.router)
api_router.include_router(ingestion.router)
