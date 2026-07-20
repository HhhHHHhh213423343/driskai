from __future__ import annotations

import uuid

from sqlalchemy import JSON, Column, Index, String, Text, Uuid
from sqlalchemy.orm import relationship

from app.db.base import Base, TimestampMixin


class Company(TimestampMixin, Base):
    __tablename__ = "companies"
    __table_args__ = (
        Index("ix_companies_name_unique", "name", unique=True),
        Index("ix_companies_credit_code_unique", "credit_code", unique=True),
    )

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    credit_code = Column(String(64), nullable=True)
    industry = Column(String(128), nullable=True, index=True)
    region = Column(String(128), nullable=True, index=True)
    description = Column(Text, nullable=False, server_default="")
    official_website = Column(String(255), nullable=False, server_default="")
    company_profile = Column(
        JSON,
        nullable=False,
        default=dict,
    )

    risk_events = relationship(
        "RiskEvent",
        back_populates="company",
        cascade="all, delete-orphan",
    )
    analysis_reports = relationship(
        "AnalysisReport",
        back_populates="company",
        cascade="all, delete-orphan",
    )
