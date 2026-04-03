"""add feature schema version to model versions"""

from alembic import op
import sqlalchemy as sa


revision = "20260403_0004"
down_revision = "20260403_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "model_versions",
        sa.Column("feature_schema_version", sa.String(length=128), nullable=True),
    )
    op.execute(
        "UPDATE model_versions SET feature_schema_version = 'lagged-panel-interactions-v12-tail-calibrated-real-feedback' "
        "WHERE feature_schema_version IS NULL"
    )
    with op.batch_alter_table("model_versions") as batch_op:
        batch_op.alter_column("feature_schema_version", nullable=False)


def downgrade() -> None:
    op.drop_column("model_versions", "feature_schema_version")
