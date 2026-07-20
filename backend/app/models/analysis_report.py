from __future__ import annotations

import uuid

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Index, String, Text, Uuid, func
from sqlalchemy.orm import relationship

from app.db.base import Base, TimestampMixin


class AnalysisReport(TimestampMixin, Base):
    __tablename__ = "analysis_reports"
    __table_args__ = (
        Index(
            "ix_analysis_reports_company_report_type_generated_at",
            "company_id",
            "report_type",
            "generated_at",
        ),
    )

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    company_id = Column(
        Uuid,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    report_type = Column(String(80), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    summary = Column(Text, nullable=False, server_default="")
    snapshot = Column(JSON, nullable=False, default=dict)
    model_name = Column(String(120), nullable=False, server_default="fastgpt")
    generated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    company = relationship("Company", back_populates="analysis_reports")
