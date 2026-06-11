"""add glucose schema and source values

Revision ID: bb8879b5ac53
Revises: 8d55e89b65e0
Create Date: 2026-06-11 18:03:14.703112

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'bb8879b5ac53'
down_revision: Union[str, Sequence[str], None] = '8d55e89b65e0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new enum values to data_source
    op.execute("ALTER TYPE data_source ADD VALUE IF NOT EXISTS 'LINX_CGM'")
    op.execute("ALTER TYPE data_source ADD VALUE IF NOT EXISTS 'DEXCOM'")
    op.execute("ALTER TYPE data_source ADD VALUE IF NOT EXISTS 'LIBRE'")

    # Add denormalized glucose summary columns to runs
    op.add_column("runs", sa.Column("glucose_pre_run_60min_avg_mg_dl", sa.Float(), nullable=True))
    op.add_column("runs", sa.Column("glucose_at_start_mg_dl", sa.Float(), nullable=True))
    op.add_column("runs", sa.Column("glucose_at_end_mg_dl", sa.Float(), nullable=True))
    op.add_column("runs", sa.Column("glucose_avg_during_run_mg_dl", sa.Float(), nullable=True))
    op.add_column("runs", sa.Column("glucose_min_during_run_mg_dl", sa.Float(), nullable=True))
    op.add_column("runs", sa.Column("glucose_max_during_run_mg_dl", sa.Float(), nullable=True))
    op.add_column("runs", sa.Column("glucose_post_run_60min_avg_mg_dl", sa.Float(), nullable=True))
    op.add_column("runs", sa.Column("glucose_time_in_range_pct_during_run", sa.Float(), nullable=True))

    # Create glucose_daily_records
    op.create_table(
        "glucose_daily_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column(
            "source",
            postgresql.ENUM(name="data_source", create_type=False),
            nullable=False,
        ),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("avg_glucose_mg_dl", sa.Float(), nullable=True),
        sa.Column("min_glucose_mg_dl", sa.Float(), nullable=True),
        sa.Column("max_glucose_mg_dl", sa.Float(), nullable=True),
        sa.Column("std_glucose_mg_dl", sa.Float(), nullable=True),
        sa.Column("time_in_range_pct", sa.Float(), nullable=True),
        sa.Column("glucose_variability_cv", sa.Float(), nullable=True),
        sa.Column("gmi", sa.Float(), nullable=True),
        sa.Column("overnight_avg_glucose_mg_dl", sa.Float(), nullable=True),
        sa.Column("overnight_min_glucose_mg_dl", sa.Float(), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("user_id", "source", "date", name="uq_glucose_user_source_date"),
    )
    op.create_index("ix_glucose_user_date", "glucose_daily_records", ["user_id", "date"])

    # Create run_glucose_samples
    op.create_table(
        "run_glucose_samples",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("elapsed_seconds", sa.Integer(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("glucose_mg_dl", sa.Float(), nullable=False),
        sa.Column("trend", sa.String(length=20), nullable=True),
        sa.Column(
            "source",
            postgresql.ENUM(name="data_source", create_type=False),
            nullable=False,
        ),
        sa.Column("raw_payload", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("run_id", "elapsed_seconds", "source", name="uq_run_glucose_sample"),
    )
    op.create_index("ix_run_glucose_run_elapsed", "run_glucose_samples", ["run_id", "elapsed_seconds"])


def downgrade() -> None:
    op.drop_index("ix_run_glucose_run_elapsed", table_name="run_glucose_samples")
    op.drop_table("run_glucose_samples")
    op.drop_index("ix_glucose_user_date", table_name="glucose_daily_records")
    op.drop_table("glucose_daily_records")

    op.drop_column("runs", "glucose_time_in_range_pct_during_run")
    op.drop_column("runs", "glucose_post_run_60min_avg_mg_dl")
    op.drop_column("runs", "glucose_max_during_run_mg_dl")
    op.drop_column("runs", "glucose_min_during_run_mg_dl")
    op.drop_column("runs", "glucose_avg_during_run_mg_dl")
    op.drop_column("runs", "glucose_at_end_mg_dl")
    op.drop_column("runs", "glucose_at_start_mg_dl")
    op.drop_column("runs", "glucose_pre_run_60min_avg_mg_dl")
