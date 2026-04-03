"""add pipeline run event history"""

from alembic import op
import sqlalchemy as sa


revision = "20260403_0008"
down_revision = "20260403_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pipeline_run_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(length=64), sa.ForeignKey("pipeline_runs.run_id"), nullable=False),
        sa.Column("session_id", sa.String(length=64), sa.ForeignKey("document_sessions.session_id"), nullable=False),
        sa.Column("stage", sa.String(length=32), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.String(length=64), nullable=False),
    )
    op.create_index("ix_pipeline_run_events_run_id", "pipeline_run_events", ["run_id"], unique=False)
    op.create_index("ix_pipeline_run_events_session_id", "pipeline_run_events", ["session_id"], unique=False)
    op.create_index("ix_pipeline_run_events_stage", "pipeline_run_events", ["stage"], unique=False)
    op.create_index("ix_pipeline_run_events_event_type", "pipeline_run_events", ["event_type"], unique=False)
    op.create_index("ix_pipeline_run_events_created_at", "pipeline_run_events", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_pipeline_run_events_created_at", table_name="pipeline_run_events")
    op.drop_index("ix_pipeline_run_events_event_type", table_name="pipeline_run_events")
    op.drop_index("ix_pipeline_run_events_stage", table_name="pipeline_run_events")
    op.drop_index("ix_pipeline_run_events_session_id", table_name="pipeline_run_events")
    op.drop_index("ix_pipeline_run_events_run_id", table_name="pipeline_run_events")
    op.drop_table("pipeline_run_events")
