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
from app.schemas import AppSettingsRead, AppSettingsUpdate

router = APIRouter(prefix="/settings", tags=["settings"])

DEFAULTS: dict = AppSettingsRead().model_dump()


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
