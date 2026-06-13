"""Server-persisted app settings (#180; the store #32 will extend).

A single key/value table backs all app-wide settings. AppSettingsRead in
schemas.py is the whitelist of known keys and their defaults: GET overlays
stored rows on it, and the PATCH schema (AppSettingsUpdate) rejects anything
outside it, so unknown keys can never be written.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AppSetting
from app.schemas import AppSettingsRead, AppSettingsUpdate, FilterPreset

router = APIRouter(prefix="/settings", tags=["settings"])

DEFAULTS: dict = AppSettingsRead().model_dump()

FILTER_PRESETS_KEY = "filter_presets"


def _merged(db: Session) -> dict:
    values = dict(DEFAULTS)
    for row in db.query(AppSetting).filter(AppSetting.key.in_(DEFAULTS)):
        values[row.key] = row.value
    return values


@router.get("", response_model=AppSettingsRead)
def get_settings(db: Session = Depends(get_db)):
    return _merged(db)


@router.patch("", response_model=AppSettingsRead)
def update_settings(body: AppSettingsUpdate, db: Session = Depends(get_db)):
    # exclude_none: a null value means "leave unchanged", and must never be
    # stored into a typed setting.
    for key, value in body.model_dump(exclude_unset=True, exclude_none=True).items():
        row = db.get(AppSetting, key)
        if row is None:
            db.add(AppSetting(key=key, value=value))
        else:
            row.value = value
    db.commit()
    return _merged(db)


def _stored_presets(db: Session) -> list[dict]:
    """The currently-stored preset list, straight from the DB (never a client
    snapshot). Falls back to the default empty list when the row is absent."""
    row = db.get(AppSetting, FILTER_PRESETS_KEY)
    return list(row.value) if row is not None else list(DEFAULTS[FILTER_PRESETS_KEY])


def _write_presets(db: Session, presets: list[dict]) -> None:
    row = db.get(AppSetting, FILTER_PRESETS_KEY)
    if row is None:
        db.add(AppSetting(key=FILTER_PRESETS_KEY, value=presets))
    else:
        row.value = presets
    db.commit()


@router.put("/filter-presets", response_model=AppSettingsRead)
def upsert_filter_preset(preset: FilterPreset, db: Session = Depends(get_db)):
    """Add or replace a single preset by name, atomically against the stored
    list. Single-preset semantics avoid the whole-list-replace clobber (#287)
    where a stale client snapshot could drop unrelated presets."""
    presets = [p for p in _stored_presets(db) if p.get("name") != preset.name]
    presets.append(preset.model_dump())
    _write_presets(db, presets)
    return _merged(db)


@router.delete("/filter-presets", response_model=AppSettingsRead)
def delete_filter_preset(name: str, db: Session = Depends(get_db)):
    """Remove a single preset by name, leaving the rest untouched (#287)."""
    presets = [p for p in _stored_presets(db) if p.get("name") != name]
    _write_presets(db, presets)
    return _merged(db)
