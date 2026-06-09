from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health():
    """Liveness stub — proves the painting module is wired into the app (M0)."""
    return {"status": "ok", "module": "painting"}
