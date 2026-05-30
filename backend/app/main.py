from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine, SessionLocal
from app.routers import models, scan, files, collections, scrape, enrich

Base.metadata.create_all(bind=engine)

app = FastAPI(title="STL Inventory", version="0.1.0")


@app.on_event("startup")
def _seed_tag_index():
    """Populate model_tags from JSON columns if the table is empty (one-time migration)."""
    import logging
    from sqlalchemy import func, text
    from app.models import Model, ModelTag
    from app.services.tag_sync import rebuild_all_tags

    logger = logging.getLogger(__name__)
    db = SessionLocal()
    try:
        tag_count = db.query(func.count(ModelTag.id)).scalar()
        model_count = db.query(func.count(Model.id)).scalar()
        if tag_count == 0 and model_count > 0:
            logger.info(f"model_tags empty with {model_count} models — running initial rebuild")
            rebuild_all_tags(db)
    except Exception:
        logger.exception("Failed to seed model_tags on startup")
    finally:
        db.close()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:80", "http://localhost"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(models.router)
app.include_router(scan.router)
app.include_router(files.router)
app.include_router(collections.router)
app.include_router(scrape.router)
app.include_router(enrich.router)


@app.get("/health")
def health():
    return {"status": "ok"}
