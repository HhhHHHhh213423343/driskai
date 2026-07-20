from __future__ import annotations

import uuid

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import relationship

from app.db.base import Base, TimestampMixin


class RiskEvent(TimestampMixin, Base):
    __tablename__ = "risk_events"
    __table_args__ = (
        Index(
            "ix_risk_events_company_category_severity",
            "company_id",
            "category",
            "severity",
        ),
    )

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    company_id = Column(
        Uuid,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category = Column(String(80), nullable=False, index=True)
    severity = Column(String(16), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    source_url = Column(String(512), nullable=False)
    source_name = Column(String(128), nullable=False, server_default="")
    occurred_at = Column(DateTime(timezone=True), nullable=True, index=True)
    sentiment = Column(String(16), nullable=False, server_default="neutral")
    extra_payload = Column(
        JSON,
        nullable=False,
        default=dict,
    )

    company = relationship("Company", back_populates="risk_events")
