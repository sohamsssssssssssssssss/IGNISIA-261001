"""add durable document pipeline session tables"""

from alembic import op
import sqlalchemy as sa


revision = "20260403_0007"
down_revision = "20260403_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_sessions",
        sa.Column("session_id", sa.String(length=64), primary_key=True),
        sa.Column("created_at", sa.String(length=64), nullable=False),
        sa.Column("updated_at", sa.String(length=64), nullable=False),
        sa.Column("workflow_status", sa.String(length=32), nullable=False, server_default="uploaded"),
        sa.Column("company_name", sa.String(length=255), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("cam_filename", sa.String(length=255), nullable=True),
        sa.Column("cam_file_path", sa.Text(), nullable=True),
    )
    op.create_index("ix_document_sessions_created_at", "document_sessions", ["created_at"], unique=False)
    op.create_index("ix_document_sessions_updated_at", "document_sessions", ["updated_at"], unique=False)
    op.create_index("ix_document_sessions_workflow_status", "document_sessions", ["workflow_status"], unique=False)

    op.create_table(
        "uploaded_documents",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(length=64), sa.ForeignKey("document_sessions.session_id"), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("predicted_type", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=False),
        sa.Column("confirmed_type", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("uploaded_at", sa.String(length=64), nullable=False),
    )
    op.create_index("ix_uploaded_documents_session_id", "uploaded_documents", ["session_id"], unique=False)
    op.create_index("ix_uploaded_documents_filename", "uploaded_documents", ["filename"], unique=False)
    op.create_index("ix_uploaded_documents_status", "uploaded_documents", ["status"], unique=False)
    op.create_index("ix_uploaded_documents_uploaded_at", "uploaded_documents", ["uploaded_at"], unique=False)

    op.create_table(
        "pipeline_runs",
        sa.Column("run_id", sa.String(length=64), primary_key=True),
        sa.Column("session_id", sa.String(length=64), sa.ForeignKey("document_sessions.session_id"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("stage", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.String(length=64), nullable=False),
        sa.Column("completed_at", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("result_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("chunks_indexed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cam_filename", sa.String(length=255), nullable=True),
        sa.Column("cam_file_path", sa.Text(), nullable=True),
    )
    op.create_index("ix_pipeline_runs_session_id", "pipeline_runs", ["session_id"], unique=False)
    op.create_index("ix_pipeline_runs_status", "pipeline_runs", ["status"], unique=False)
    op.create_index("ix_pipeline_runs_stage", "pipeline_runs", ["stage"], unique=False)
    op.create_index("ix_pipeline_runs_started_at", "pipeline_runs", ["started_at"], unique=False)
    op.create_index("ix_pipeline_runs_completed_at", "pipeline_runs", ["completed_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_pipeline_runs_completed_at", table_name="pipeline_runs")
    op.drop_index("ix_pipeline_runs_started_at", table_name="pipeline_runs")
    op.drop_index("ix_pipeline_runs_stage", table_name="pipeline_runs")
    op.drop_index("ix_pipeline_runs_status", table_name="pipeline_runs")
    op.drop_index("ix_pipeline_runs_session_id", table_name="pipeline_runs")
    op.drop_table("pipeline_runs")

    op.drop_index("ix_uploaded_documents_uploaded_at", table_name="uploaded_documents")
    op.drop_index("ix_uploaded_documents_status", table_name="uploaded_documents")
    op.drop_index("ix_uploaded_documents_filename", table_name="uploaded_documents")
    op.drop_index("ix_uploaded_documents_session_id", table_name="uploaded_documents")
    op.drop_table("uploaded_documents")

    op.drop_index("ix_document_sessions_workflow_status", table_name="document_sessions")
    op.drop_index("ix_document_sessions_updated_at", table_name="document_sessions")
    op.drop_index("ix_document_sessions_created_at", table_name="document_sessions")
    op.drop_table("document_sessions")

