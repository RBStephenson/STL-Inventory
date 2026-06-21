"""Verbatim series-badge chips for sibling cross-link round-trip (#271)

Adds guides.series_badge — the ordered .series-badge chips ([{label, filename,
active}]) captured verbatim so sibling cross-links round-trip without deriving
them across guides. create_all handles fresh DBs; this brings already
Alembic-stamped DBs up to the same schema.

Revision ID: 0010
Revises: 0009
Create Date: 2026-06-21
"""
import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("guides")}
    if "series_badge" not in cols:
        op.add_column("guides", sa.Column("series_badge", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("guides", "series_badge")
