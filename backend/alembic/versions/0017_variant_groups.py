"""Add variant_groups table + models.variant_group_id, backfill from (creator, character)

Revision ID: 0017
Revises: 0016
Create Date: 2026-06-28
"""
from collections import defaultdict

import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "variant_groups" not in inspector.get_table_names():
        op.create_table(
            "variant_groups",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("creator_id", sa.Integer(), nullable=False),
            sa.Column("label", sa.String(), nullable=True),
            sa.Column("rep_model_id", sa.Integer(), nullable=True),
            sa.Column("source", sa.String(), nullable=False, server_default="auto"),
            sa.Column("reason", sa.String(), nullable=True),
            sa.Column("confidence", sa.Float(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["creator_id"], ["creators.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["rep_model_id"], ["models.id"], ondelete="SET NULL"),
        )
        op.create_index("ix_variant_groups_creator_id", "variant_groups", ["creator_id"])

    cols = {c["name"] for c in inspector.get_columns("models")}
    if "variant_group_id" not in cols:
        with op.batch_alter_table("models") as batch:
            batch.add_column(sa.Column("variant_group_id", sa.Integer(), nullable=True))
        op.create_index("ix_models_variant_group_id", "models", ["variant_group_id"])

    _backfill(bind)


def _backfill(bind) -> None:
    """Create one auto group per (creator_id, character) with >1 non-excluded model."""
    rows = bind.execute(
        sa.text(
            "SELECT id, creator_id, character, COALESCE(is_group_rep, 0) AS is_rep "
            "FROM models "
            "WHERE excluded = 0 AND creator_id IS NOT NULL "
            "AND character IS NOT NULL AND character != ''"
        )
    ).fetchall()

    members: dict[tuple[int, str], list] = defaultdict(list)
    for r in rows:
        members[(r.creator_id, r.character)].append(r)

    for (creator_id, character), grp in members.items():
        if len(grp) < 2:
            continue
        rep = next((m.id for m in grp if m.is_rep), grp[0].id)
        result = bind.execute(
            sa.text(
                "INSERT INTO variant_groups (creator_id, label, rep_model_id, source, created_at) "
                "VALUES (:creator_id, :label, :rep, 'auto', CURRENT_TIMESTAMP)"
            ),
            {"creator_id": creator_id, "label": character, "rep": rep},
        )
        group_id = result.lastrowid
        ids = [m.id for m in grp]
        bind.execute(
            sa.text(
                "UPDATE models SET variant_group_id = :gid "
                "WHERE id IN (" + ",".join(str(i) for i in ids) + ")"
            ),
            {"gid": group_id},
        )


def downgrade() -> None:
    op.drop_index("ix_models_variant_group_id", table_name="models")
    with op.batch_alter_table("models") as batch:
        batch.drop_column("variant_group_id")
    op.drop_index("ix_variant_groups_creator_id", table_name="variant_groups")
    op.drop_table("variant_groups")
