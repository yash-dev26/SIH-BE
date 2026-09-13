"""Phase 2: add data_quality_log and feature_snapshots tables.

Revision ID: 0002_phase2_ingestion_features
Revises: 0001_init_schema
Create Date: 2026-09-13

NOTE: `down_revision` assumes Phase 1's initial migration file is named
`0001_init_schema` (per the Phase 1 file tree: alembic/versions/0001_init_schema.py).
Update it to match the actual revision id if Alembic auto-generated a
different hash-based id.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_phase2_ingestion_features"
down_revision = "0001_init_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "data_quality_log",
        sa.Column("log_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("connector_name", sa.String(80), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("resolved_provenance", sa.String(20), nullable=True),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column("rows_written", sa.Integer(), nullable=True),
        sa.Column("context", postgresql.JSONB(), nullable=True),
    )
    op.create_index("ix_data_quality_log_connector_name", "data_quality_log", ["connector_name"])
    op.create_index("ix_data_quality_log_occurred_at", "data_quality_log", ["occurred_at"])

    op.create_table(
        "feature_snapshots",
        sa.Column("snapshot_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("trade_lane_id", sa.Integer(), sa.ForeignKey("trade_lanes.trade_lane_id"), nullable=False),
        sa.Column("vessel_class_id", sa.Integer(), sa.ForeignKey("vessel_classes.vessel_class_id"), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("feature_group", sa.String(30), nullable=False),
        sa.Column("features", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "trade_lane_id", "vessel_class_id", "as_of", "feature_group",
            name="uq_feature_snapshot_entity_asof_group",
        ),
    )
    op.create_index(
        "ix_feature_snapshots_lane_class_asof",
        "feature_snapshots",
        ["trade_lane_id", "vessel_class_id", "as_of"],
    )


def downgrade() -> None:
    op.drop_index("ix_feature_snapshots_lane_class_asof", table_name="feature_snapshots")
    op.drop_table("feature_snapshots")
    op.drop_index("ix_data_quality_log_occurred_at", table_name="data_quality_log")
    op.drop_index("ix_data_quality_log_connector_name", table_name="data_quality_log")
    op.drop_table("data_quality_log")
