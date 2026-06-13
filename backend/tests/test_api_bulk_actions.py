"""Tests for bulk model actions: exclude/restore and needs-review (#164)."""
from tests.conftest import make_creator, make_model


def _three_models(db):
    creator = make_creator(db)
    a = make_model(db, creator, name="Alpha")
    b = make_model(db, creator, name="Bravo")
    c = make_model(db, creator, name="Charlie")
    db.commit()
    return a, b, c


# ---------------------------------------------------------------------------
# PATCH /models/bulk/exclude
# ---------------------------------------------------------------------------

class TestBulkExclude:
    def test_excludes_multiple_models(self, client, db):
        a, b, c = _three_models(db)
        r = client.patch("/models/bulk/exclude", json={"ids": [a.id, b.id], "excluded": True})
        assert r.status_code == 200
        assert r.json() == {"ok": True, "updated": 2}

        names = {i["name"] for i in client.get("/models").json()["items"]}
        assert names == {"Charlie"}

    def test_restores_multiple_models(self, client, db):
        a, b, c = _three_models(db)
        client.patch("/models/bulk/exclude", json={"ids": [a.id, b.id], "excluded": True})
        r = client.patch("/models/bulk/exclude", json={"ids": [a.id, b.id], "excluded": False})
        assert r.json()["updated"] == 2
        assert client.get("/models").json()["total"] == 3

    def test_excluding_clears_queue_state(self, client, db):
        a, _, _ = _three_models(db)
        client.patch(f"/models/{a.id}/print-status", json={"status": "queued"})
        client.patch("/models/bulk/exclude", json={"ids": [a.id], "excluded": True})
        db.refresh(a)
        assert a.excluded is True
        assert a.print_status == "none"
        assert a.queue_position is None

    def test_empty_ids_returns_400(self, client, db):
        _three_models(db)
        r = client.patch("/models/bulk/exclude", json={"ids": [], "excluded": True})
        assert r.status_code == 400

    def test_unknown_ids_are_ignored(self, client, db):
        a, _, _ = _three_models(db)
        r = client.patch("/models/bulk/exclude", json={"ids": [a.id, 99999], "excluded": True})
        assert r.status_code == 200
        assert r.json()["updated"] == 1

    def test_bulk_not_parsed_as_model_id(self, client, db):
        """Route ordering guard: /bulk/exclude must not match /{model_id}/exclude."""
        a, _, _ = _three_models(db)
        r = client.patch("/models/bulk/exclude", json={"ids": [a.id], "excluded": True})
        assert r.status_code == 200  # not a 422 from int("bulk")


# ---------------------------------------------------------------------------
# PATCH /models/bulk/review
# ---------------------------------------------------------------------------

class TestBulkReview:
    def test_marks_multiple_needs_review(self, client, db):
        a, b, c = _three_models(db)
        r = client.patch("/models/bulk/review", json={"ids": [a.id, b.id], "needs_review": True})
        assert r.status_code == 200
        assert r.json()["updated"] == 2
        db.refresh(a); db.refresh(b); db.refresh(c)
        assert a.needs_review is True
        assert b.needs_review is True
        assert c.needs_review is False

    def test_clears_needs_review(self, client, db):
        a, _, _ = _three_models(db)
        client.patch("/models/bulk/review", json={"ids": [a.id], "needs_review": True})
        client.patch("/models/bulk/review", json={"ids": [a.id], "needs_review": False})
        db.refresh(a)
        assert a.needs_review is False

    def test_reflected_in_needs_review_filter(self, client, db):
        a, b, _ = _three_models(db)
        client.patch("/models/bulk/review", json={"ids": [a.id, b.id], "needs_review": True})
        data = client.get("/models?needs_review=true").json()
        assert data["total"] == 2

    def test_empty_ids_returns_400(self, client, db):
        _three_models(db)
        r = client.patch("/models/bulk/review", json={"ids": [], "needs_review": True})
        assert r.status_code == 400
