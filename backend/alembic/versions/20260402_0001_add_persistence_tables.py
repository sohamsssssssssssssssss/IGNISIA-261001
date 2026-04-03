"""initial persistence tables for msmE scoring"""

from alembic import op
import sqlalchemy as sa


revision = "20260402_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "score_assessments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("gstin", sa.String(length=32), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=True),
        sa.Column("credit_score", sa.Integer(), nullable=False),
        sa.Column("risk_band", sa.String(length=64), nullable=False),
        sa.Column("fraud_risk", sa.String(length=32), nullable=False),
        sa.Column("model_version", sa.String(length=128), nullable=False),
        sa.Column("scenario", sa.String(length=32), nullable=False),
        sa.Column("data_sparse", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("freshness_timestamp", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="api"),
        sa.Column("top_reasons_json", sa.Text(), nullable=False),
        sa.Column("recommendation_json", sa.Text(), nullable=False),
    )
    op.create_index(
        "ix_score_assessments_gstin",
        "score_assessments",
        ["gstin"],
        unique=False,
    )
    op.create_index(
        "ix_score_assessments_created_at",
        "score_assessments",
        ["created_at"],
        unique=False,
    )

    op.create_table(
        "fraud_alerts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("gstin", sa.String(length=32), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=True),
        sa.Column("circular_risk", sa.String(length=32), nullable=False),
        sa.Column("risk_score", sa.Integer(), nullable=False),
        sa.Column("cycle_count", sa.Integer(), nullable=False),
        sa.Column("linked_msme_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_volume", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.String(length=64), nullable=False),
        sa.Column("alert_payload_json", sa.Text(), nullable=False),
    )
    op.create_index("ix_fraud_alerts_gstin", "fraud_alerts", ["gstin"], unique=False)
    op.create_index("ix_fraud_alerts_created_at", "fraud_alerts", ["created_at"], unique=False)

    op.create_table(
        "analyst_reviews",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(length=128), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("analyst_action", sa.String(length=32), nullable=False),
        sa.Column("original_score", sa.Float(), nullable=False),
        sa.Column("adjusted_score", sa.Float(), nullable=False),
        sa.Column("total_adjustment", sa.Float(), nullable=False),
        sa.Column("original_verdict", sa.String(length=32), nullable=False),
        sa.Column("adjusted_verdict", sa.String(length=32), nullable=False),
        sa.Column("management_quality", sa.Integer(), nullable=True),
        sa.Column("factory_utilization", sa.Float(), nullable=True),
        sa.Column("field_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
    )
    op.create_index("ix_analyst_reviews_session_id", "analyst_reviews", ["session_id"], unique=False)
    op.create_index("ix_analyst_reviews_created_at", "analyst_reviews", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_analyst_reviews_created_at", table_name="analyst_reviews")
    op.drop_index("ix_analyst_reviews_session_id", table_name="analyst_reviews")
    op.drop_table("analyst_reviews")

    op.drop_index("ix_fraud_alerts_created_at", table_name="fraud_alerts")
    op.drop_index("ix_fraud_alerts_gstin", table_name="fraud_alerts")
    op.drop_table("fraud_alerts")

    op.drop_index("ix_score_assessments_created_at", table_name="score_assessments")
    op.drop_index("ix_score_assessments_gstin", table_name="score_assessments")
    op.drop_table("score_assessments")
