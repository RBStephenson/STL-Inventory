from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, exists
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Model, Creator, ModelTag
from app.schemas import ModelList, ModelRead, ModelDetail, CreatorRead
from app.services.tag_sync import sync_model_tags

router = APIRouter(prefix="/models", tags=["models"])


@router.get("", response_model=ModelList)
def list_models(
    page: int = Query(1, ge=1),
    page_size: int = Query(48, ge=1, le=200),
    search: str = Query("", alias="q"),
    creator_id: int | None = None,
    character: str | None = None,
    source_site: str | None = None,
    tag: str | None = None,
    has_thumbnail: bool | None = None,
    needs_review: bool | None = None,
    nsfw: bool | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(Model)

    if search:
        like = f"%{search}%"
        q = q.filter(
            Model.title.ilike(like)
            | Model.name.ilike(like)
            | Model.description.ilike(like)
            | Model.character.ilike(like)
        )
    if creator_id:
        q = q.filter(Model.creator_id == creator_id)
    if character:
        q = q.filter(Model.character.ilike(f"%{character}%"))
    if source_site:
        q = q.filter(Model.source_site == source_site)
    if tag:
        tag_norm = tag.strip().lower()
        q = q.filter(
            exists().where(
                (ModelTag.model_id == Model.id) & (ModelTag.tag == tag_norm)
            )
        )
    if has_thumbnail is True:
        q = q.filter(
            (Model.thumbnail_path != None) | (Model.thumbnail_url != None)
        )
    if has_thumbnail is False:
        q = q.filter(
            (Model.thumbnail_path == None) & (Model.thumbnail_url == None)
        )
    if needs_review is not None:
        q = q.filter(Model.needs_review == needs_review)
    if nsfw is not None:
        q = q.filter(Model.nsfw == nsfw)

    total = q.count()
    items = q.order_by(Model.character, Model.name).offset((page - 1) * page_size).limit(page_size).all()

    return ModelList(total=total, page=page, page_size=page_size, items=items)


@router.get("/creators/list", response_model=list[CreatorRead])
def list_creators(db: Session = Depends(get_db)):
    creators = db.query(Creator).order_by(Creator.name).all()
    result = []
    for c in creators:
        count = db.query(func.count(Model.id)).filter(Model.creator_id == c.id).scalar()
        cr = CreatorRead.model_validate(c)
        cr.model_count = count
        result.append(cr)
    return result


@router.get("/stats")
def model_stats(db: Session = Depends(get_db)):
    total = db.query(func.count(Model.id)).scalar()
    needs_review = db.query(func.count(Model.id)).filter(Model.needs_review == True).scalar()
    no_thumbnail = db.query(func.count(Model.id)).filter(
        Model.thumbnail_path == None, Model.thumbnail_url == None
    ).scalar()
    return {"total": total, "needs_review": needs_review, "no_thumbnail": no_thumbnail}


@router.get("/tags/all")
def list_tags(db: Session = Depends(get_db)):
    """Return all unique tags with usage counts, sorted by frequency."""
    rows = (
        db.query(ModelTag.tag, func.count(ModelTag.id).label("count"))
        .group_by(ModelTag.tag)
        .order_by(func.count(ModelTag.id).desc())
        .all()
    )
    return [{"tag": row.tag, "count": row.count} for row in rows]


@router.post("/tags/rebuild")
def rebuild_tags(db: Session = Depends(get_db)):
    """Rebuild the model_tags index from the JSON tag columns on all models."""
    from app.services.tag_sync import rebuild_all_tags
    count = rebuild_all_tags(db)
    return {"ok": True, "rows": count}


@router.patch("/bulk")
def bulk_tag_models(body: dict, db: Session = Depends(get_db)):
    """Add or remove tags across multiple models in one request."""
    ids = body.get("ids", [])
    add_tags = [t.strip().lower() for t in body.get("add_tags", []) if t.strip()]
    remove_set = {t.strip().lower() for t in body.get("remove_tags", []) if t.strip()}

    if not ids:
        raise HTTPException(status_code=400, detail="No model IDs provided")

    models_to_update = db.query(Model).filter(Model.id.in_(ids)).all()
    for model in models_to_update:
        current = list(model.tags or [])
        if add_tags:
            current = list(dict.fromkeys(current + add_tags))
        if remove_set:
            current = [t for t in current if t not in remove_set]
        model.tags = current
        model.updated_at = datetime.utcnow()
        sync_model_tags(model, db)

    db.commit()
    return {"ok": True, "updated": len(models_to_update)}


@router.patch("/{model_id}")
def update_model(model_id: int, body: dict, db: Session = Depends(get_db)):
    """Partial update of model metadata fields."""
    model = db.query(Model).filter(Model.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    allowed = {
        "title", "description", "notes", "source_url", "source_site",
        "license", "category", "tags", "custom_attributes", "nsfw",
        "needs_review",
    }
    for key, value in body.items():
        if key in allowed:
            if key == "tags" and isinstance(value, list):
                value = list(dict.fromkeys(t.strip().lower() for t in value if t.strip()))
            setattr(model, key, value)

    if "creator_name" in body and body["creator_name"]:
        creator = db.query(Creator).filter(Creator.name == body["creator_name"]).first()
        if not creator:
            creator = Creator(name=body["creator_name"])
            db.add(creator)
            db.flush()
        model.creator_id = creator.id

    if "needs_review" not in body:
        model.needs_review = False

    model.updated_at = datetime.utcnow()
    sync_model_tags(model, db)
    db.commit()
    return {"ok": True}


@router.patch("/{model_id}/thumbnail")
def set_thumbnail(model_id: int, body: dict, db: Session = Depends(get_db)):
    """Set thumbnail_path or thumbnail_url on a model."""
    model = db.query(Model).filter(Model.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    if "thumbnail_path" in body:
        model.thumbnail_path = body["thumbnail_path"] or None
    if "thumbnail_url" in body:
        model.thumbnail_url = body["thumbnail_url"] or None
    db.commit()
    return {"ok": True}


@router.get("/{model_id}", response_model=ModelDetail)
def get_model(model_id: int, db: Session = Depends(get_db)):
    model = (
        db.query(Model)
        .options(joinedload(Model.stl_files), joinedload(Model.creator))
        .filter(Model.id == model_id)
        .first()
    )
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return model
