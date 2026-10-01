"""
SQLAlchemy ORM - clean schema (no compatibility with the PoC database).

    attack_jobs    - one row per submission (aggregate root)
    model_runs     - one row per (job, target model)
    turns          - one row per turn per model run (the auditable trace)
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from crescendo.domain.models import now_utc


class Base(DeclarativeBase):
    pass


class AttackJobRow(Base):
    __tablename__ = "attack_jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    strategy_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    max_turns: Mapped[int] = mapped_column(Integer, nullable=False)
    temperature: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)
    seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    runs: Mapped[list["ModelRunRow"]] = relationship(
        back_populates="job", cascade="all, delete-orphan", lazy="selectin"
    )


class ModelRunRow(Base):
    __tablename__ = "model_runs"
    __table_args__ = (UniqueConstraint("job_id", "model", name="uq_run_job_model"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("attack_jobs.id", ondelete="CASCADE"), index=True
    )
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    final_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_verdict: Mapped[str | None] = mapped_column(String(32), nullable=True)

    job: Mapped[AttackJobRow] = relationship(back_populates="runs")
    turns: Mapped[list["TurnRow"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", lazy="selectin"
    )


class TurnRow(Base):
    __tablename__ = "turns"
    __table_args__ = (UniqueConstraint("model_run_id", "idx", name="uq_turn_run_idx"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("model_runs.id", ondelete="CASCADE"), index=True
    )
    idx: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    response: Mapped[str | None] = mapped_column(Text, nullable=True)
    verdict: Mapped[str] = mapped_column(String(32), nullable=False)
    reasons: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)

    run: Mapped[ModelRunRow] = relationship(back_populates="turns")
