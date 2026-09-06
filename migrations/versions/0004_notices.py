"""Add targeted procurement notices."""
from alembic import op
import sqlalchemy as sa

revision = "0004_notices"
down_revision = "0003_sms_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("notices"):
        op.create_table(
            "notices",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("title", sa.String(length=180), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("notice_type", sa.String(length=30), nullable=False, server_default="GENERAL"),
            sa.Column("scope", sa.String(length=20), nullable=False, server_default="GLOBAL"),
            sa.Column("district", sa.String(length=120), nullable=True),
            sa.Column("center_id", sa.Integer(), sa.ForeignKey("mandis.id"), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="DRAFT"),
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
    existing_indexes = {index["name"] for index in sa.inspect(bind).get_indexes("notices")}
    for name, column in (("ix_notices_district", "district"), ("ix_notices_center_id", "center_id"), ("ix_notices_status", "status"), ("ix_notices_created_by", "created_by")):
        if name not in existing_indexes:
            op.create_index(name, "notices", [column])


def downgrade() -> None:
    raise NotImplementedError("Notice migration is forward-only for the SIH demo.")