"""Nullable paint_id + name on guide_swatches (#477)

A single swatch that doesn't resolve to a shelf paint is kept as a name-only row
instead of being dropped, so it round-trips. Relaxes the NOT NULL on paint_id
(SQLite needs a table rebuild → batch mode) and adds the name column. Mirrors the
mix-component change in 0011 (#425). create_all handles fresh DBs; this brings
already Alembic-stamped DBs up to date.

Revision ID: 0012
Revises: 0011
Create Date: 2026-06-21
"""
import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"]: c for c in inspector.get_columns("guide_swatches")}
    with op.batch_alter_table("guide_swatches") as batch:
        if "name" not in cols:
            batch.add_column(sa.Column("name", sa.String(), nullable=True))
        if cols.get("paint_id", {}).get("nullable") is False:
            batch.alter_column("paint_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("guide_swatches") as batch:
        batch.alter_column("paint_id", existing_type=sa.Integer(), nullable=False)
        batch.drop_column("name")
