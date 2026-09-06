"""Add localized content fields to procurement notices."""
from alembic import op
import sqlalchemy as sa

revision = "0005_notice_localization"
down_revision = "0004_notices"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("notices")}
    for name, column_type in (
        ("title_en", sa.String(length=180)),
        ("title_hi", sa.String(length=180)),
        ("title_mr", sa.String(length=180)),
        ("description_en", sa.Text()),
        ("description_hi", sa.Text()),
        ("description_mr", sa.Text()),
    ):
        if name not in columns:
            op.add_column("notices", sa.Column(name, column_type, nullable=True))
    op.execute(sa.text("UPDATE notices SET title_en = title WHERE title_en IS NULL"))
    op.execute(sa.text("UPDATE notices SET description_en = description WHERE description_en IS NULL"))


def downgrade() -> None:
    raise NotImplementedError("Notice localization migration is forward-only.")