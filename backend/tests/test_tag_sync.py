"""Unit tests for the model_tags index rebuild (services/tag_sync).

Locks in rebuild_all_tags behaviour (previously only sync_model_tags was
exercised, via the tag-management API) after the #56 dedup that routes both
through the shared _write_model_tags helper.
"""
from tests.conftest import make_creator, make_model
from app.models import ModelTag
from app.services.tag_sync import rebuild_all_tags, bulk_sync_model_tags


def test_rebuild_all_tags_merges_user_and_auto_tags(db):
    creator = make_creator(db)
    m1 = make_model(db, creator, name="Alpha", tags=["bust"])
    m1.auto_tags = ["figure", "bust"]          # "bust" also a user tag → user wins (is_auto False)
    m2 = make_model(db, creator, name="Beta", tags=["statue"])
    m2.auto_tags = ["figure"]
    m2.removed_auto_tags = ["figure"]          # suppressed → dropped from the index
    db.commit()

    # A stale row that a full rebuild must clear.
    db.add(ModelTag(model_id=m1.id, tag="ghost", is_auto=True))
    db.commit()

    count = rebuild_all_tags(db)

    rows = {(r.model_id, r.tag): r.is_auto for r in db.query(ModelTag).all()}
    assert rows == {
        (m1.id, "bust"): False,    # user tag wins over the same-named auto tag
        (m1.id, "figure"): True,
        (m2.id, "statue"): False,  # m2's "figure" auto tag was suppressed
    }
    assert count == len(rows)


# ---------------------------------------------------------------------------
# bulk_sync_model_tags (#654)
# ---------------------------------------------------------------------------

def test_bulk_sync_replaces_existing_rows(db):
    creator = make_creator(db)
    m1 = make_model(db, creator, name="A", tags=["bust"])
    m2 = make_model(db, creator, name="B", tags=["statue"])
    db.commit()

    # Seed stale rows that bulk_sync must replace.
    db.add(ModelTag(model_id=m1.id, tag="ghost", is_auto=True))
    db.add(ModelTag(model_id=m2.id, tag="phantom", is_auto=False))
    db.flush()

    bulk_sync_model_tags([m1, m2], db)

    rows = {(r.model_id, r.tag) for r in db.query(ModelTag).all()}
    assert rows == {(m1.id, "bust"), (m2.id, "statue")}


def test_bulk_sync_empty_list_is_noop(db):
    creator = make_creator(db)
    m = make_model(db, creator, name="A", tags=["bust"])
    db.add(ModelTag(model_id=m.id, tag="bust", is_auto=False))
    db.commit()

    bulk_sync_model_tags([], db)

    assert db.query(ModelTag).count() == 1


def test_bulk_sync_merges_auto_and_user_tags(db):
    creator = make_creator(db)
    m = make_model(db, creator, name="A", tags=["bust"])
    m.auto_tags = ["figure", "bust"]  # "bust" also user tag → is_auto False
    db.flush()

    bulk_sync_model_tags([m], db)

    rows = {r.tag: r.is_auto for r in db.query(ModelTag).filter(ModelTag.model_id == m.id)}
    assert rows == {"bust": False, "figure": True}
