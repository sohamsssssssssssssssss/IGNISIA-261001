"""add industry and maturity fields to score assessments"""

from alembic import op
import sqlalchemy as sa


revision = "20260403_0005"
down_revision = "20260403_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("score_assessments") as batch_op:
        batch_op.add_column(
            sa.Column("industry_code", sa.String(length=32), nullable=True),
        )
        batch_op.add_column(
            sa.Column("months_active", sa.Float(), nullable=True),
        )
    op.execute("UPDATE score_assessments SET months_active = 0 WHERE months_active IS NULL")
    with op.batch_alter_table("score_assessments") as batch_op:
        batch_op.alter_column("months_active", nullable=False)


def downgrade() -> None:
    op.drop_column("score_assessments", "months_active")
    op.drop_column("score_assessments", "industry_code")
