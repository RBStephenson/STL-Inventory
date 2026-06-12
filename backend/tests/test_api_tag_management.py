"""Tests for tag rename, merge, and delete endpoints (#165)."""
import pytest
from tests.conftest import make_creator, make_model
from app.services.tag_sync import sync_model_tags
from app.models import ModelTag


def setup_tagged_models(db, client):
    """Create a creator and two models with overlapping tags."""
    creator = make_creator(db)
    m1 = make_model(db, creator, name="Alpha", tags=["figure", "bust"])
    m2 = make_model(db, creator, name="Beta", tags=["figure", "statue"])
    m3 = make_model(db, creator, name="Gamma", tags=["bust"])
    for m in (m1, m2, m3):
        sync_model_tags(m, db)
    db.commit()
    return m1, m2, m3


# ---------------------------------------------------------------------------
# GET /models/tags/all — baseline
# ---------------------------------------------------------------------------

def test_list_tags(client, db):
    setup_tagged_models(db, client)
    r = client.get("/models/tags/all")
    assert r.status_code == 200
    tags = {t["tag"]: t["count"] for t in r.json()}
    assert tags["figure"] == 2
    assert tags["bust"] == 2
    assert tags["statue"] == 1


# ---------------------------------------------------------------------------
# PATCH /models/tags/rename
# ---------------------------------------------------------------------------

def test_rename_tag(client, db):
    m1, m2, m3 = setup_tagged_models(db, client)
    r = client.patch("/models/tags/rename", json={"old_tag": "figure", "new_tag": "miniature"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["updated"] == 2

    db.refresh(m1); db.refresh(m2)
    assert "miniature" in m1.tags
    assert "figure" not in m1.tags
    assert "miniature" in m2.tags
    assert "figure" not in m2.tags
    # m3 was not affected
    db.refresh(m3)
    assert "figure" not in m3.tags


def test_rename_tag_no_duplicate(client, db):
    """Renaming 'figure' to 'bust' on a model that has both should not duplicate bust."""
    creator = make_creator(db)
    m = make_model(db, creator, tags=["figure", "bust"])
    sync_model_tags(m, db); db.commit()

    r = client.patch("/models/tags/rename", json={"old_tag": "figure", "new_tag": "bust"})
    assert r.status_code == 200
    db.refresh(m)
    assert m.tags.count("bust") == 1
    assert "figure" not in m.tags


def test_rename_tag_not_found(client, db):
    make_creator(db); db.commit()
    r = client.patch("/models/tags/rename", json={"old_tag": "nonexistent", "new_tag": "x"})
    assert r.status_code == 404


def test_rename_tag_missing_params(client, db):
    r = client.patch("/models/tags/rename", json={"old_tag": "figure"})
    assert r.status_code == 422

    r2 = client.patch("/models/tags/rename", json={"new_tag": "x"})
    assert r2.status_code == 422


def test_rename_tag_same_name_is_noop(client, db):
    creator = make_creator(db)
    m = make_model(db, creator, name="Model A", tags=["figure"])
    sync_model_tags(m, db); db.commit()
    r = client.patch("/models/tags/rename", json={"old_tag": "figure", "new_tag": "figure"})
    assert r.status_code == 200
    assert r.json()["updated"] == 0


# ---------------------------------------------------------------------------
# POST /models/tags/merge
# ---------------------------------------------------------------------------

def test_merge_tags(client, db):
    m1, m2, m3 = setup_tagged_models(db, client)
    # merge 'bust' into 'figure': m1 and m3 had bust; m2 did not
    r = client.post("/models/tags/merge", json={"source_tag": "bust", "target_tag": "figure"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["updated"] == 2  # m1 and m3

    db.refresh(m1); db.refresh(m3)
    assert "bust" not in m1.tags
    assert "figure" in m1.tags
    assert "bust" not in m3.tags
    assert "figure" in m3.tags


def test_merge_tags_already_has_target(client, db):
    """Model that already has both source and target ends up with target only, no dupe."""
    creator = make_creator(db)
    m = make_model(db, creator, tags=["figure", "bust"])
    sync_model_tags(m, db); db.commit()

    r = client.post("/models/tags/merge", json={"source_tag": "bust", "target_tag": "figure"})
    assert r.status_code == 200
    db.refresh(m)
    assert m.tags.count("figure") == 1
    assert "bust" not in m.tags


def test_merge_tags_source_not_found(client, db):
    make_creator(db); db.commit()
    r = client.post("/models/tags/merge", json={"source_tag": "ghost", "target_tag": "figure"})
    assert r.status_code == 404


def test_merge_same_tag_is_noop(client, db):
    creator = make_creator(db)
    make_model(db, creator, tags=["bust"]); db.commit()
    r = client.post("/models/tags/merge", json={"source_tag": "bust", "target_tag": "bust"})
    assert r.status_code == 200
    assert r.json()["updated"] == 0


# ---------------------------------------------------------------------------
# DELETE /models/tags/{tag}
# ---------------------------------------------------------------------------

def test_delete_tag(client, db):
    m1, m2, m3 = setup_tagged_models(db, client)
    r = client.delete("/models/tags/figure")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["updated"] == 2

    db.refresh(m1); db.refresh(m2)
    assert "figure" not in m1.tags
    assert "figure" not in m2.tags
    # bust still present on m1
    assert "bust" in m1.tags
    # m3 (bust only) not affected
    db.refresh(m3)
    assert m3.tags == ["bust"]


def test_delete_tag_not_found(client, db):
    make_creator(db); db.commit()
    r = client.delete("/models/tags/nonexistent")
    assert r.status_code == 404


def test_delete_tag_updates_model_tags_index(client, db):
    """After delete, the ModelTag index should have no row for that tag."""
    creator = make_creator(db)
    m = make_model(db, creator, tags=["bust", "figure"])
    sync_model_tags(m, db); db.commit()

    client.delete("/models/tags/bust")
    db.expire_all()
    remaining = db.query(ModelTag).filter(ModelTag.model_id == m.id).all()
    assert all(r.tag != "bust" for r in remaining)
    assert any(r.tag == "figure" for r in remaining)
