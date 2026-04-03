"""add pipeline ingestion tables"""

from alembic import op
import sqlalchemy as sa


revision = "20260403_0002"
down_revision = "20260402_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pipeline_data",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("gstin", sa.String(length=32), nullable=False),
        sa.Column("pipeline_type", sa.String(length=32), nullable=False),
        sa.Column("epoch", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ingested_at", sa.String(length=64), nullable=False),
        sa.Column("data_json", sa.Text(), nullable=False),
        sa.UniqueConstraint(
            "gstin",
            "pipeline_type",
            name="uq_pipeline_data_gstin_pipeline_type",
        ),
    )
    op.create_index("ix_pipeline_data_gstin", "pipeline_data", ["gstin"], unique=False)
    op.create_index("ix_pipeline_data_ingested_at", "pipeline_data", ["ingested_at"], unique=False)

    op.create_table(
        "monitored_gstins",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("gstin", sa.String(length=32), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=True),
        sa.Column("added_at", sa.String(length=64), nullable=False),
    )
    op.create_index("ix_monitored_gstins_gstin", "monitored_gstins", ["gstin"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_monitored_gstins_gstin", table_name="monitored_gstins")
    op.drop_table("monitored_gstins")

    op.drop_index("ix_pipeline_data_ingested_at", table_name="pipeline_data")
    op.drop_index("ix_pipeline_data_gstin", table_name="pipeline_data")
    op.drop_table("pipeline_data")
