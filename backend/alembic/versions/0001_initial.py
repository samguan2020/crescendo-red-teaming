"""initial schema: attack_jobs, model_runs, turns

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-04
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "attack_jobs",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("strategy_kind", sa.String(length=32), nullable=False),
        sa.Column("max_turns", sa.Integer(), nullable=False),
        sa.Column("temperature", sa.Float(), nullable=False, server_default="0.7"),
        sa.Column("seed", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("total_duration_ms", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "model_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("job_id", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("final_output", sa.Text(), nullable=True),
        sa.Column("final_verdict", sa.String(length=32), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["attack_jobs.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("job_id", "model", name="uq_run_job_model"),
    )
    op.create_index("ix_model_runs_job_id", "model_runs", ["job_id"])
    op.create_table(
        "turns",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("model_run_id", sa.Integer(), nullable=False),
        sa.Column("idx", sa.Integer(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("response", sa.Text(), nullable=True),
        sa.Column("verdict", sa.String(length=32), nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["model_run_id"], ["model_runs.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("model_run_id", "idx", name="uq_turn_run_idx"),
    )
    op.create_index("ix_turns_model_run_id", "turns", ["model_run_id"])


def downgrade() -> None:
    op.drop_index("ix_turns_model_run_id", table_name="turns")
    op.drop_table("turns")
    op.drop_index("ix_model_runs_job_id", table_name="model_runs")
    op.drop_table("model_runs")
    op.drop_table("attack_jobs")
