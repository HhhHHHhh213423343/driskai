from __future__ import annotations

import uuid

from sqlalchemy import JSON, Column, DateTime, Integer, String, Uuid, func

from app.db.base import Base, TimestampMixin


class IngestionRun(TimestampMixin, Base):
    __tablename__ = "ingestion_runs"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    status = Column(String(24), nullable=False, index=True, server_default="running")
    started_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    finished_at = Column(DateTime(timezone=True), nullable=True)
    requested_company_count = Column(Integer, nullable=False, server_default="0")
    scanned_company_count = Column(Integer, nullable=False, server_default="0")
    total_raw_count = Column(Integer, nullable=False, server_default="0")
    inserted_count = Column(Integer, nullable=False, server_default="0")
    skipped_count = Column(Integer, nullable=False, server_default="0")
    source_breakdown = Column(JSON, nullable=False, default=dict)
    failures = Column(JSON, nullable=False, default=list)
    summary = Column(JSON, nullable=False, default=dict)
