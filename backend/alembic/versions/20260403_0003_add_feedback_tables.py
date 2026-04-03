"""add loan outcomes and model version governance tables"""

from alembic import op
import sqlalchemy as sa


revision = "20260403_0003"
down_revision = "20260403_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "loan_outcomes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("gstin", sa.String(length=32), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=True),
        sa.Column("repaid", sa.Boolean(), nullable=False),
        sa.Column("loan_amount", sa.Float(), nullable=False),
        sa.Column("tenure_months", sa.Integer(), nullable=False),
        sa.Column("recorded_at", sa.String(length=64), nullable=False),
        sa.Column("source_model_version", sa.String(length=128), nullable=True),
        sa.Column("feature_snapshot_json", sa.Text(), nullable=False),
    )
    op.create_index("ix_loan_outcomes_gstin", "loan_outcomes", ["gstin"], unique=False)
    op.create_index("ix_loan_outcomes_recorded_at", "loan_outcomes", ["recorded_at"], unique=False)

    op.create_table(
        "model_versions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("model_version", sa.String(length=128), nullable=False),
        sa.Column("trained_at", sa.String(length=64), nullable=False),
        sa.Column("training_sample_size", sa.Integer(), nullable=False),
        sa.Column("synthetic_sample_count", sa.Integer(), nullable=False),
        sa.Column("real_sample_count", sa.Integer(), nullable=False),
        sa.Column("real_label_ratio", sa.Float(), nullable=False),
        sa.Column("auc_before", sa.Float(), nullable=True),
        sa.Column("auc_after", sa.Float(), nullable=True),
        sa.Column("metrics_json", sa.Text(), nullable=False),
    )
    op.create_index("ix_model_versions_model_version", "model_versions", ["model_version"], unique=False)
    op.create_index("ix_model_versions_trained_at", "model_versions", ["trained_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_model_versions_trained_at", table_name="model_versions")
    op.drop_index("ix_model_versions_model_version", table_name="model_versions")
    op.drop_table("model_versions")

    op.drop_index("ix_loan_outcomes_recorded_at", table_name="loan_outcomes")
    op.drop_index("ix_loan_outcomes_gstin", table_name="loan_outcomes")
    op.drop_table("loan_outcomes")
