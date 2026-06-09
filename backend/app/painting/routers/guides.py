"""Guide CRUD endpoints — stubs until M2 (guide model + renderer)."""
from fastapi import APIRouter, HTTPException

router = APIRouter()

_NOT_IMPLEMENTED = HTTPException(
    status_code=501, detail="Painting guides are not implemented yet (coming in M2)."
)


@router.get("/guides")
def list_guides():
    raise _NOT_IMPLEMENTED


@router.post("/guides")
def create_guide():
    raise _NOT_IMPLEMENTED
