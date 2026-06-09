"""Paint Shelf (inventory) endpoints — stubs until M1 (CSV import + shelf UI)."""
from fastapi import APIRouter, HTTPException

router = APIRouter()

_NOT_IMPLEMENTED = HTTPException(
    status_code=501, detail="The Paint Shelf is not implemented yet (coming in M1)."
)


@router.get("/paints")
def list_paints():
    raise _NOT_IMPLEMENTED


@router.post("/paints")
def create_paint():
    raise _NOT_IMPLEMENTED
