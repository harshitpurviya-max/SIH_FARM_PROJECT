"""Add Farmer ID and procurement-center metadata for the demo workflow."""
from alembic import op
import sqlalchemy as sa

revision = "0002_demo_metadata"
down_revision = "0001_procurement_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    mandi_columns = {column["name"] for column in inspector.get_columns("mandis")}
    additions = [
        ("district", sa.String(length=120)),
        ("state", sa.String(length=120), {"server_default": "Madhya Pradesh"}),
        ("address", sa.String(length=255)),
        ("daily_capacity_quintals", sa.Numeric(12, 2), {"server_default": "200.00"}),
    ]
    for addition in additions:
        name, column_type, *options = addition
        if name not in mandi_columns:
            op.add_column("mandis", sa.Column(name, column_type, nullable=True, **(options[0] if options else {})))

    user_columns = {column["name"] for column in inspector.get_columns("users")}
    if "farmer_id" not in user_columns:
        op.add_column("users", sa.Column("farmer_id", sa.String(length=40), nullable=True))
        op.create_index("ix_users_farmer_id", "users", ["farmer_id"], unique=True)

    op.execute(
        sa.text(
            "UPDATE users SET farmer_id = 'MP-FRM-' || LPAD(id::text, 6, '0') "
            "WHERE role = 'FARMER' AND farmer_id IS NULL"
        )
    )


def downgrade() -> None:
    raise NotImplementedError("Demo metadata migration is forward-only to preserve Farmer IDs.")
