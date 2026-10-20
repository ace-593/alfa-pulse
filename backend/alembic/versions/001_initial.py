import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("email", sa.String(254), unique=True, nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("password_hash", sa.String(512), nullable=False),
        sa.Column("admin", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "sessions",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("user_id", sa.String(128), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_table(
        "refresh_tokens",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("session_id", sa.String(128), sa.ForeignKey("sessions.id"), nullable=False),
        sa.Column("used", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_refresh_tokens_session_id", "refresh_tokens", ["session_id"])
    op.create_table(
        "resources",
        sa.Column("kind", sa.String(40), primary_key=True),
        sa.Column("key", sa.String(512), primary_key=True),
        sa.Column("data", postgresql.JSONB(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_resource_data", "resources", ["data"], postgresql_using="gin")


def downgrade():
    for table in ["resources", "refresh_tokens", "sessions", "users"]:
        op.drop_table(table)
