"""add narrative column plus chat and apriori persistence tables"""

from alembic import op
import sqlalchemy as sa


revision = "20260403_0006"
down_revision = "20260403_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("score_assessments") as batch_op:
        batch_op.add_column(sa.Column("narrative", sa.Text(), nullable=True))

    op.create_table(
        "chat_sessions",
        sa.Column("session_id", sa.String(length=36), primary_key=True),
        sa.Column("gstin", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.String(length=64), nullable=False),
        sa.Column("last_active_at", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.String(length=64), nullable=False),
    )
    op.create_index("ix_chat_sessions_gstin", "chat_sessions", ["gstin"], unique=False)
    op.create_index("ix_chat_sessions_created_at", "chat_sessions", ["created_at"], unique=False)
    op.create_index("ix_chat_sessions_last_active_at", "chat_sessions", ["last_active_at"], unique=False)
    op.create_index("ix_chat_sessions_expires_at", "chat_sessions", ["expires_at"], unique=False)

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(length=36), sa.ForeignKey("chat_sessions.session_id"), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sources_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.String(length=64), nullable=False),
    )
    op.create_index("ix_chat_messages_session_id", "chat_messages", ["session_id"], unique=False)
    op.create_index("ix_chat_messages_created_at", "chat_messages", ["created_at"], unique=False)

    op.create_table(
        "apriori_rules",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("antecedents_json", sa.Text(), nullable=False),
        sa.Column("consequent", sa.String(length=32), nullable=False),
        sa.Column("support", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("lift", sa.Float(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("created_at", sa.String(length=64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_apriori_rules_consequent", "apriori_rules", ["consequent"], unique=False)
    op.create_index("ix_apriori_rules_created_at", "apriori_rules", ["created_at"], unique=False)
    op.create_index("ix_apriori_rules_is_active", "apriori_rules", ["is_active"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_apriori_rules_is_active", table_name="apriori_rules")
    op.drop_index("ix_apriori_rules_created_at", table_name="apriori_rules")
    op.drop_index("ix_apriori_rules_consequent", table_name="apriori_rules")
    op.drop_table("apriori_rules")

    op.drop_index("ix_chat_messages_created_at", table_name="chat_messages")
    op.drop_index("ix_chat_messages_session_id", table_name="chat_messages")
    op.drop_table("chat_messages")

    op.drop_index("ix_chat_sessions_expires_at", table_name="chat_sessions")
    op.drop_index("ix_chat_sessions_last_active_at", table_name="chat_sessions")
    op.drop_index("ix_chat_sessions_created_at", table_name="chat_sessions")
    op.drop_index("ix_chat_sessions_gstin", table_name="chat_sessions")
    op.drop_table("chat_sessions")

    with op.batch_alter_table("score_assessments") as batch_op:
        batch_op.drop_column("narrative")
