from __future__ import annotations

import uuid

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.orm import relationship

from app.db.base import Base, TimestampMixin


class CompanyProfileRun(TimestampMixin, Base):
    __tablename__ = "company_profile_runs"
    __table_args__ = (
        Index("ix_company_profile_runs_company_created", "company_id", "created_at"),
        Index("ix_company_profile_runs_status_lease", "status", "lease_expires_at"),
        Index(
            "uq_company_profile_runs_one_active_company",
            "company_id",
            unique=True,
            postgresql_where=text(
                "status IN ('queued', 'running', 'waiting_for_login', 'waiting_for_captcha')"
            ),
            sqlite_where=text(
                "status IN ('queued', 'running', 'waiting_for_login', 'waiting_for_captcha')"
            ),
        ),
    )

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    company_id = Column(
        Uuid,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = Column(String(32), nullable=False, index=True, default="queued")
    mode = Column(String(16), nullable=False, default="full")
    force = Column(Boolean, nullable=False, default=False)
    worker_id = Column(String(128), nullable=False, default="")
    lease_expires_at = Column(DateTime(timezone=True), nullable=True)
    heartbeat_at = Column(DateTime(timezone=True), nullable=True)
    claimed_at = Column(DateTime(timezone=True), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    progress_current = Column(Integer, nullable=False, default=0)
    progress_total = Column(Integer, nullable=False, default=8)
    current_module = Column(String(64), nullable=False, default="")
    error_code = Column(String(64), nullable=False, default="")
    error_message = Column(Text, nullable=False, default="")
    module_statuses = Column(JSON, nullable=False, default=dict)

    company = relationship("Company", back_populates="company_profile_runs")
    snapshot = relationship(
        "CompanyProfileSnapshot",
        back_populates="run",
        uselist=False,
        cascade="all, delete-orphan",
    )


class CompanyProfileSnapshot(TimestampMixin, Base):
    __tablename__ = "company_profile_snapshots"
    __table_args__ = (
        Index(
            "ix_company_profile_snapshots_company_captured",
            "company_id",
            "captured_at",
        ),
    )

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    company_id = Column(
        Uuid,
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    run_id = Column(
        Uuid,
        ForeignKey("company_profile_runs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    captured_at = Column(DateTime(timezone=True), nullable=False, index=True)
    sop_version = Column(String(64), nullable=False)
    module_statuses = Column(JSON, nullable=False, default=dict)
    normalized_data = Column(JSON, nullable=False, default=dict)
    raw_data = Column(JSON, nullable=False, default=dict)
    excel_filename = Column(String(512), nullable=False)
    excel_sha256 = Column(String(64), nullable=False)
    excel_file = Column(LargeBinary, nullable=False)

    company = relationship("Company", back_populates="company_profile_snapshots")
    run = relationship("CompanyProfileRun", back_populates="snapshot")
