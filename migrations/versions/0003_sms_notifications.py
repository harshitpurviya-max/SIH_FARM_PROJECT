"""Add SMS delivery metadata to existing notifications."""
from alembic import op
import sqlalchemy as sa

revision = "0003_sms_notifications"
down_revision = "0002_demo_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("notifications")}
    additions = [
        ("event_type", sa.String(length=60), "IN_APP"),
        ("phone_number", sa.String(length=20), None),
        ("channel", sa.String(length=20), "IN_APP"),
        ("delivery_status", sa.String(length=20), "CREATED"),
        ("sent_at", sa.DateTime(timezone=True), None),
    ]
    for name, column_type, default in additions:
        if name not in columns:
            kwargs = {"nullable": True}
            if default is not None:
                kwargs["server_default"] = default
            op.add_column("notifications", sa.Column(name, column_type, **kwargs))
    op.execute(sa.text("UPDATE notifications SET event_type = notification_type WHERE event_type IS NULL"))
    op.execute(sa.text("UPDATE notifications SET channel = 'IN_APP' WHERE channel IS NULL"))
    op.execute(sa.text("UPDATE notifications SET delivery_status = 'CREATED' WHERE delivery_status IS NULL"))


def downgrade() -> None:
    raise NotImplementedError("SMS notification metadata migration is forward-only.")
