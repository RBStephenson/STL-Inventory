import threading
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ScanRoot
from app.schemas import ScanStatus
from app.services import scanner
from app.config import settings

router = APIRouter(prefix="/scan", tags=["scan"])


@router.post("/start", response_model=ScanStatus)
def start_scan(db: Session = Depends(get_db)):
    status = scanner.get_status()
    if status["running"]:
        raise HTTPException(status_code=409, detail="Scan already running")

    # Ensure scan roots exist in db from env config
    _sync_roots_from_config(db)

    thread = threading.Thread(target=scanner.scan_all_roots, daemon=True)
    thread.start()

    return ScanStatus(running=True, message="scan started")


@router.get("/status", response_model=ScanStatus)
def scan_status():
    s = scanner.get_status()
    return ScanStatus(**s)


@router.get("/roots")
def list_roots(db: Session = Depends(get_db)):
    return db.query(ScanRoot).all()


def _sync_roots_from_config(db: Session):
    """Ensure each path in STL_ROOTS env var exists as a ScanRoot row."""
    for path in settings.stl_root_list:
        exists = db.query(ScanRoot).filter(ScanRoot.path == path).first()
        if not exists:
            db.add(ScanRoot(path=path, enabled=True))
    db.commit()
