"""expand apriori rule fields for behavioral pattern intelligence"""

from alembic import op
import sqlalchemy as sa


revision = "20260404_0009"
down_revision = "20260403_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("apriori_rules") as batch_op:
        batch_op.add_column(sa.Column("record_count", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("generated_at", sa.String(length=64), nullable=True))

    op.execute("UPDATE apriori_rules SET generated_at = created_at WHERE generated_at IS NULL")

    with op.batch_alter_table("apriori_rules") as batch_op:
        batch_op.alter_column("generated_at", existing_type=sa.String(length=64), nullable=False)
        batch_op.create_index("ix_apriori_rules_generated_at", ["generated_at"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("apriori_rules") as batch_op:
        batch_op.drop_index("ix_apriori_rules_generated_at")
        batch_op.drop_column("generated_at")
        batch_op.drop_column("record_count")
