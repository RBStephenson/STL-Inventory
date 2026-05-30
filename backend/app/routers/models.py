from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Model, Creator
from app.schemas import ModelList, ModelRead, ModelDetail, CreatorRead

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
        q = q.filter(Model.tags.contains([tag]) | Model.auto_tags.contains([tag]))
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
    from sqlalchemy import text
    # Pull tags from both user tags and auto_tags JSON columns
    models = db.query(Model.tags, Model.auto_tags).all()
    counts: dict[str, int] = {}
    for user_tags, auto_tags in models:
        for tag in (user_tags or []) + (auto_tags or []):
            tag = tag.strip().lower()
            if tag:
                counts[tag] = counts.get(tag, 0) + 1
    return [
        {"tag": tag, "count": count}
        for tag, count in sorted(counts.items(), key=lambda x: -x[1])
    ]


@router.patch("/{model_id}")
def update_model(model_id: int, body: dict, db: Session = Depends(get_db)):
    """Partial update of model metadata fields."""
    model = db.query(Model).filter(Model.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    allowed = {
        "title", "description", "notes", "source_url", "source_site",
        "license", "category", "tags", "custom_attributes", "nsfw",
    }
    for key, value in body.items():
        if key in allowed:
            # Normalise tags: lowercase, strip, deduplicate
            if key == "tags" and isinstance(value, list):
                value = list(dict.fromkeys(t.strip().lower() for t in value if t.strip()))
            setattr(model, key, value)

    # Resolve creator by name if provided
    if "creator_name" in body and body["creator_name"]:
        from app.models import Creator
        creator = db.query(Creator).filter(Creator.name == body["creator_name"]).first()
        if not creator:
            creator = Creator(name=body["creator_name"])
            db.add(creator)
            db.flush()
        model.creator_id = creator.id

    model.needs_review = False
    model.updated_at = __import__("datetime").datetime.utcnow()
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
