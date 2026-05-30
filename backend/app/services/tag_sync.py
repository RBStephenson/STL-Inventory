"""
Tag index maintenance.

model_tags is a denormalized index derived from models.tags and models.auto_tags.
Call sync_model_tags() after any write that modifies either column.
Call rebuild_all_tags() once at startup when migrating from JSON-only storage.
"""
import logging
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models import Model, ModelTag

logger = logging.getLogger(__name__)


def sync_model_tags(model: Model, db: Session) -> None:
    """Rebuild model_tags rows for a single model from its JSON tag columns."""
    db.query(ModelTag).filter(ModelTag.model_id == model.id).delete(synchronize_session=False)

    # Merge auto_tags and user tags; user tags override is_auto flag.
    tag_map: dict[str, bool] = {}  # tag -> is_auto
    for raw in (model.auto_tags or []):
        t = raw.strip().lower()
        if t:
            tag_map[t] = True
    for raw in (model.tags or []):
        t = raw.strip().lower()
        if t:
            tag_map[t] = False  # user tag wins

    for tag, is_auto in tag_map.items():
        db.add(ModelTag(model_id=model.id, tag=tag, is_auto=is_auto))


def rebuild_all_tags(db: Session) -> int:
    """Full rebuild of model_tags from all models. Returns number of tag rows inserted."""
    logger.info("Rebuilding model_tags index…")
    db.query(ModelTag).delete(synchronize_session=False)
    db.flush()

    count = 0
    batch_size = 500
    offset = 0

    while True:
        models = db.query(Model).offset(offset).limit(batch_size).all()
        if not models:
            break
        for model in models:
            tag_map: dict[str, bool] = {}
            for raw in (model.auto_tags or []):
                t = raw.strip().lower()
                if t:
                    tag_map[t] = True
            for raw in (model.tags or []):
                t = raw.strip().lower()
                if t:
                    tag_map[t] = False
            for tag, is_auto in tag_map.items():
                db.add(ModelTag(model_id=model.id, tag=tag, is_auto=is_auto))
                count += 1
        db.flush()
        offset += batch_size

    db.commit()
    logger.info(f"model_tags rebuild complete: {count} rows")
    return count
