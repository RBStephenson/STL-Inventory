"""Serve local image files and STL files from the mounted drives."""
import io
import os
import time
import logging
import platform
import subprocess
import zipfile
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/files", tags=["files"])

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
ALLOWED_STL_EXTENSIONS = {".stl", ".3mf", ".obj"}

# Cache the allowlist briefly — image serving is a hot path (a grid loads dozens
# of thumbnails at once) and scan roots change rarely (only via the Settings UI).
_roots_cache: tuple[float, list[Path]] | None = None
_ROOTS_TTL = 5.0


# Directories the file server is allowed to read from
def _allowed_roots() -> list[Path]:
    global _roots_cache
    now = time.monotonic()
    if _roots_cache is not None and now - _roots_cache[0] < _ROOTS_TTL:
        return _roots_cache[1]

    roots = [Path(r) for r in settings.stl_root_list]

    # Roots added through the Settings UI live in the scan_roots table, not the
    # STL_ROOTS env var. Include them so file serving works in standalone mode
    # (where STL_ROOTS is empty and drives are added entirely through the UI).
    try:
        from app.database import SessionLocal
        from app.models import ScanRoot
        db = SessionLocal()
        try:
            for (path,) in db.query(ScanRoot.path).filter(ScanRoot.enabled == True):
                if path:
                    roots.append(Path(path))
        finally:
            db.close()
    except Exception:
        logger.exception("Failed to load scan roots for the file-serving allowlist")

    if settings.orynt3d_thumbnail_cache:
        roots.append(Path(settings.orynt3d_thumbnail_cache))

    # De-duplicate while preserving order.
    seen: set[str] = set()
    unique: list[Path] = []
    for r in roots:
        key = str(r)
        if key not in seen:
            seen.add(key)
            unique.append(r)

    _roots_cache = (now, unique)
    return unique


def _is_safe_path(p: Path) -> bool:
    resolved = p.resolve()
    return any(
        resolved.is_relative_to(root.resolve())
        for root in _allowed_roots()
    )


@router.get("/image")
def serve_image(path: str):
    p = Path(path)
    if p.suffix.lower() not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Not an image file")
    if not _is_safe_path(p):
        raise HTTPException(status_code=403, detail="Path not allowed")
    if not p.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(p)


@router.get("/stl")
def serve_stl(path: str):
    p = Path(path)
    if p.suffix.lower() not in ALLOWED_STL_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Not an STL/3MF/OBJ file")
    if not _is_safe_path(p):
        raise HTTPException(status_code=403, detail="Path not allowed")
    if not p.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(p, media_type="application/octet-stream")


@router.post("/download-zip")
def download_zip(body: dict):
    """
    Build a zip archive from a list of STL file IDs and stream it to the client.
    Body: { "file_ids": [1, 2, 3], "zip_name": "My Model 2026-05-30" }
    """
    from app.database import SessionLocal
    from app.models import STLFile

    file_ids: list[int] = body.get("file_ids", [])
    zip_name: str = body.get("zip_name", "kit-build")

    if not file_ids:
        raise HTTPException(status_code=400, detail="No file IDs provided")

    db = SessionLocal()
    try:
        files = db.query(STLFile).filter(STLFile.id.in_(file_ids)).all()
    finally:
        db.close()

    if not files:
        raise HTTPException(status_code=404, detail="No matching files found")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            p = Path(f.path)
            if not _is_safe_path(p) or not p.exists():
                continue
            zf.write(p, arcname=f.filename)
    buf.seek(0)

    safe_name = "".join(c if c.isalnum() or c in " .-_()" else "_" for c in zip_name).strip()
    filename = f"{safe_name}.zip"

    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/open-folder")
def open_folder(path: str):
    """
    Open a folder in the native file manager.
    Only works when the backend is running directly on the host (standalone mode).
    In Docker mode the container has no GUI so this returns 501.
    """
    p = Path(path)
    if not _is_safe_path(p):
        raise HTTPException(status_code=403, detail="Path not allowed")
    if not p.exists():
        raise HTTPException(status_code=404, detail="Folder not found")

    system = platform.system()
    try:
        if system == "Windows":
            os.startfile(str(p))
        elif system == "Darwin":
            subprocess.Popen(["open", str(p)])
        elif system == "Linux":
            subprocess.Popen(["xdg-open", str(p)])
        else:
            raise HTTPException(status_code=501, detail="Unsupported OS")
    except (AttributeError, FileNotFoundError, OSError) as e:
        raise HTTPException(status_code=501, detail=f"Cannot open folder: {e}")

    return {"ok": True}


@router.get("/model-images/{model_id}")
def list_model_images(model_id: int):
    """List all images in a model's folder tree and sibling dirs up to the scan root.

    Walks upward from the model folder to the scan root boundary, recursing into
    each parent's subdirectories — but skipping subdirectories that are themselves
    indexed as model folders so we don't redundantly re-collect other models' images.
    This handles images stored in sibling render/preview folders at the character level.
    """
    from app.database import SessionLocal
    from app.models import Model as ModelDB

    db = SessionLocal()
    try:
        model = db.query(ModelDB).filter(ModelDB.id == model_id).first()
        if not model:
            raise HTTPException(status_code=404, detail="Model not found")
        folder = Path(model.folder_path)
        if not folder.exists():
            return []

        roots = {str(r) for r in _allowed_roots()}

        # Find the search boundary — the highest ancestor before the scan root.
        boundary = folder
        current = folder.parent
        while current != current.parent:
            if str(current) in roots:
                break
            boundary = current
            current = current.parent
        # boundary is now the topmost dir we'll search (e.g. creator dir)

        # Only load model folder paths within the search scope — not all 12,500.
        # Use a prefix filter on the boundary path to limit the query.
        boundary_prefix = str(boundary)
        model_folders = {
            p
            for (p,) in db.query(ModelDB.folder_path).filter(
                ModelDB.folder_path.like(f"{boundary_prefix}%")
            ).all()
            if p
        }
        # Always include the current model's own folder so we recurse into it.
        model_folders.discard(str(folder))

        seen: set[str] = set()
        images: list[dict] = []

        def _collect_dir(search_path: Path):
            """Recursively collect images, skipping subdirs that are model folders."""
            try:
                entries = search_path.iterdir()
            except PermissionError:
                return
            for entry in entries:
                if entry.is_dir():
                    if str(entry) not in model_folders:
                        _collect_dir(entry)
                elif entry.is_file() and entry.suffix.lower() in ALLOWED_IMAGE_EXTENSIONS:
                    key = str(entry)
                    if key not in seen:
                        seen.add(key)
                        images.append({
                            "path": key,
                            "filename": entry.name,
                            "url": f"/api/files/image?path={entry}",
                        })

        # Walk upward from the model folder to the scan root, collecting images
        # at each level (including siblings of the model folder).
        current = folder
        while current != current.parent:
            if str(current) in roots:
                break
            _collect_dir(current)
            current = current.parent

        return images
    finally:
        db.close()
