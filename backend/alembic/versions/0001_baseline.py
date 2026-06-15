"""baseline — anchor for all pre-Alembic schema

All tables and columns represented here already exist in production DBs via
create_all + the legacy _migrate_schema() loop. This revision is a no-op;
it exists only as the down_revision anchor for future migrations.

Existing DBs are stamped at this revision on first startup (see main.py
_run_migrations). New DBs get create_all, then are also stamped here.

Revision ID: 0001
Revises:
Create Date: 2026-06-15
"""
from alembic import op  # noqa: F401

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Schema is already in place via SQLAlchemy create_all + legacy migrations.
    pass


def downgrade() -> None:
    pass
