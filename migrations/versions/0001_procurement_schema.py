"""Add procurement lifecycle schema while preserving legacy token states.

Revision ID: 0001_procurement_schema
Revises:
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_procurement_schema"
down_revision = None
branch_labels = None
depends_on = None


def _enum_values(enum_name: str) -> set[str]:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT enumlabel FROM pg_enum WHERE enumtypid = CAST(:type AS regtype)"),
        {"type": enum_name},
    )
    return {row[0] for row in rows}


def _add_enum_values(enum_name: str, values: list[str]) -> None:
    existing = _enum_values(enum_name)
    for value in values:
        if value not in existing:
            op.execute(sa.text(f"ALTER TYPE {enum_name} ADD VALUE '{value}'"))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("mandis"):
        from backend.database import Base
        from backend import models

        Base.metadata.create_all(bind=bind)
        return

    _add_enum_values(
        "token_status",
        [
            "ARRIVED", "WAITING", "QUALITY_CHECK", "WEIGHMENT", "ACCEPTED", "REJECTED",
            "PAYMENT_PENDING", "PAYMENT_INITIATED", "PAYMENT_PROCESSING", "PAYMENT_COMPLETED", "PAYMENT_FAILED",
        ],
    )
    user_role = postgresql.ENUM("FARMER", "OFFICER", "ADMIN", name="user_role")
    payment_status = postgresql.ENUM("PENDING", "INITIATED", "PROCESSING", "COMPLETED", "FAILED", name="payment_status")
    user_role.create(bind, checkfirst=True)
    payment_status.create(bind, checkfirst=True)

    existing_columns = {column["name"] for column in inspector.get_columns("mandis")}
    if "is_active" not in existing_columns:
        op.add_column("mandis", sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False))
    if "procurement_window_start" not in existing_columns:
        op.add_column("mandis", sa.Column("procurement_window_start", sa.Time(), nullable=True))
    if "procurement_window_end" not in existing_columns:
        op.add_column("mandis", sa.Column("procurement_window_end", sa.Time(), nullable=True))
    if "available_crops" not in existing_columns:
        op.add_column("mandis", sa.Column("available_crops", sa.JSON(), nullable=True))
    if "last_updated_at" not in existing_columns:
        op.add_column("mandis", sa.Column("last_updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))

    slot_columns = {column["name"] for column in inspector.get_columns("slots")}
    if "created_at" not in slot_columns:
        op.add_column("slots", sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))

    user_table = "users"
    if not inspector.has_table(user_table):
        op.create_table(
            user_table,
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("phone", sa.String(length=20), nullable=False),
            sa.Column("full_name", sa.String(length=150), nullable=True),
            sa.Column("password_hash", sa.String(length=255), server_default="", nullable=False),
            sa.Column("role", user_role, nullable=False, server_default="FARMER"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("phone", name="uq_users_phone"),
        )
        op.create_index("ix_users_phone", "users", ["phone"], unique=False)
    elif "password_hash" not in {column["name"] for column in inspector.get_columns("users")}:
        op.add_column("users", sa.Column("password_hash", sa.String(length=255), server_default="", nullable=False))

    if not inspector.has_table("bookings"):
        op.create_table(
            "bookings",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("farmer_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("slot_id", sa.Integer(), sa.ForeignKey("slots.id"), nullable=False),
            sa.Column("crop_type", sa.String(length=100), nullable=False),
            sa.Column("expected_tonnage", sa.Numeric(10, 3), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_bookings_farmer_id", "bookings", ["farmer_id"])
        op.create_index("ix_bookings_slot_id", "bookings", ["slot_id"])

    token_columns = {column["name"] for column in inspector.get_columns("tokens")}
    for name, foreign_key in (("booking_id", "bookings.id"), ("farmer_id", "users.id"), ("mandi_id", "mandis.id")):
        if name not in token_columns:
            op.add_column("tokens", sa.Column(name, sa.Integer(), nullable=True))
            op.create_foreign_key(f"fk_tokens_{name}", "tokens", "bookings" if name == "booking_id" else ("users" if name == "farmer_id" else "mandis"), [name], ["id"])
            op.create_index(f"ix_tokens_{name}", "tokens", [name])
    if "token_code" in token_columns:
        op.alter_column("tokens", "token_code", type_=sa.String(length=12), existing_type=sa.String(length=6), existing_nullable=False)
    for name, nullable in (("created_at", False), ("arrived_at", True), ("last_updated_at", False)):
        if name not in token_columns:
            op.add_column("tokens", sa.Column(name, sa.DateTime(timezone=True), server_default=sa.func.now() if name != "arrived_at" else None, nullable=nullable))

    token_enum = postgresql.ENUM(name="token_status", create_type=False)
    if not inspector.has_table("procurement_status_history"):
        op.create_table(
            "procurement_status_history",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("token_id", sa.Integer(), sa.ForeignKey("tokens.id"), nullable=False),
            sa.Column("previous_status", token_enum, nullable=True),
            sa.Column("new_status", token_enum, nullable=False),
            sa.Column("changed_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("remarks", sa.Text(), nullable=True),
            sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_procurement_status_history_token_id", "procurement_status_history", ["token_id"])
        op.create_index("ix_procurement_status_history_changed_at", "procurement_status_history", ["changed_at"])

    if not inspector.has_table("quality_inspections"):
        op.create_table(
            "quality_inspections",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("token_id", sa.Integer(), sa.ForeignKey("tokens.id"), nullable=False, unique=True),
            sa.Column("inspector_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("grade", sa.String(length=20), nullable=True),
            sa.Column("moisture_percentage", sa.Numeric(5, 2), nullable=True),
            sa.Column("decision", sa.String(length=20), nullable=True),
            sa.Column("remarks", sa.Text(), nullable=True),
            sa.Column("rejection_reason", sa.Text(), nullable=True),
            sa.Column("inspected_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_quality_inspections_inspector_id", "quality_inspections", ["inspector_id"])

    if not inspector.has_table("weighments"):
        op.create_table(
            "weighments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("token_id", sa.Integer(), sa.ForeignKey("tokens.id"), nullable=False, unique=True),
            sa.Column("operator_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("gross_weight", sa.Numeric(10, 3), nullable=False),
            sa.Column("tare_weight", sa.Numeric(10, 3), nullable=False),
            sa.Column("net_weight", sa.Numeric(10, 3), nullable=False),
            sa.Column("reference_number", sa.String(length=100), nullable=True),
            sa.Column("remarks", sa.Text(), nullable=True),
            sa.Column("weighed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_weighments_operator_id", "weighments", ["operator_id"])

    if not inspector.has_table("payments"):
        op.create_table(
            "payments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("token_id", sa.Integer(), sa.ForeignKey("tokens.id"), nullable=False, unique=True),
            sa.Column("farmer_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("amount", sa.Numeric(12, 2), nullable=False),
            sa.Column("status", payment_status, nullable=False, server_default="PENDING"),
            sa.Column("initiated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("reference_number", sa.String(length=100), nullable=True),
            sa.Column("failure_reason", sa.Text(), nullable=True),
        )
        op.create_index("ix_payments_farmer_id", "payments", ["farmer_id"])

    if not inspector.has_table("required_documents"):
        op.create_table(
            "required_documents",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("mandi_id", sa.Integer(), sa.ForeignKey("mandis.id"), nullable=False),
            sa.Column("document_key", sa.String(length=80), nullable=False),
            sa.Column("label", sa.String(length=150), nullable=False),
            sa.Column("description", sa.String(length=255), nullable=True),
            sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.UniqueConstraint("mandi_id", "document_key", name="uq_required_document_mandi_key"),
        )
        op.create_index("ix_required_documents_mandi_id", "required_documents", ["mandi_id"])

    if not inspector.has_table("notifications"):
        op.create_table(
            "notifications",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("recipient_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("token_id", sa.Integer(), sa.ForeignKey("tokens.id"), nullable=True),
            sa.Column("notification_type", sa.String(length=60), nullable=False),
            sa.Column("title", sa.String(length=150), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_notifications_recipient_id", "notifications", ["recipient_id"])
        op.create_index("ix_notifications_token_id", "notifications", ["token_id"])
        op.create_index("ix_notifications_created_at", "notifications", ["created_at"])


def downgrade() -> None:
    raise NotImplementedError("The initial procurement migration is forward-only to protect existing data.")
