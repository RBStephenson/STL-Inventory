"""Reference-image acquisition: upload, STL-model-folder sourcing, and
user-supplied URL, with provenance tracking (spec §4.4 / §8.5).

The dependable spine of the spec's fallback chain (#535 + #494):

* **user_upload** — `store_upload` (the original #535 rung).
* **stl_model_folder** — `list_model_candidates` / `store_from_model`: the
  linked model's already-indexed folder images, zero-cost (rung 0).
* **web_research** — `store_from_url`: a user-supplied URL (the "paste a Google
  image result" rung 4), fetched server-side with attribution recorded.

The flaky accelerators (assisted web search, AI generation — rungs 2 & 3) need a
pluggable external provider and stay out of this module for now.
"""
from __future__ import annotations

import io
import uuid
from pathlib import Path

from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session

from app.models import Model
from app.painting.models import Guide, GuideReferenceImage
from app.routers.files import _is_safe_path
from app.services.thumbnails import ThumbnailDownloadError, fetch_image_bytes
from app.services.write_lock import data_dir

# Subdirectory under the local data dir (next to the SQLite DB) where uploaded
# reference images live. Deliberately not under a scan root — see data_dir().
_STORAGE_SUBDIR = "guide_reference_images"

_MAX_BYTES = 10 * 1024 * 1024  # 10 MB upload cap (also bounds vision token cost).

# Accepted upload content — Pillow format name -> (extension, Anthropic media type).
# These are the formats Claude vision accepts; we re-derive the type from the
# decoded image rather than trusting the client's Content-Type.
_FORMAT_MAP = {
    "PNG": (".png", "image/png"),
    "JPEG": (".jpg", "image/jpeg"),
    "WEBP": (".webp", "image/webp"),
    "GIF": (".gif", "image/gif"),
}


class ReferenceImageError(ValueError):
    """The supplied upload was missing, too large, or not a supported image."""


def _storage_root() -> Path:
    root = data_dir() / _STORAGE_SUBDIR
    root.mkdir(parents=True, exist_ok=True)
    return root


def _path_for(storage_key: str) -> Path:
    """Resolve a stored row's storage_key to an absolute path on disk."""
    return data_dir() / storage_key


def _decode(raw: bytes) -> tuple[Image.Image, str, str]:
    """Validate bytes as a supported image; return (image, extension, media_type)."""
    if not raw:
        raise ReferenceImageError("The uploaded file is empty.")
    if len(raw) > _MAX_BYTES:
        raise ReferenceImageError(
            f"Image is too large ({len(raw) // 1024} KB); the limit is "
            f"{_MAX_BYTES // (1024 * 1024)} MB."
        )
    try:
        image = Image.open(io.BytesIO(raw))
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise ReferenceImageError("The uploaded file is not a readable image.") from exc

    mapping = _FORMAT_MAP.get(image.format or "")
    if mapping is None:
        raise ReferenceImageError(
            f"Unsupported image format '{image.format}'. Use PNG, JPEG, WebP, or GIF."
        )
    extension, media_type = mapping
    return image, extension, media_type


def clear_reference(db: Session, guide: Guide) -> None:
    """Drop the guide's current reference image (FK + row + file), if any.

    Nulls the guide FK before deleting the row so the FK constraint never trips.
    No-op when the guide has no reference image.
    """
    image_id = guide.reference_image_id
    if image_id is None:
        return
    guide.reference_image_id = None
    db.flush()  # clear the FK before the row goes away

    row = db.get(GuideReferenceImage, image_id)
    if row is not None:
        path = _path_for(row.storage_key)
        db.delete(row)
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass  # row is the source of truth; an orphaned file is harmless


def _persist(
    db: Session,
    guide: Guide,
    raw: bytes,
    *,
    provenance: str,
    source_url: str | None = None,
    alt_text: str | None = None,
) -> GuideReferenceImage:
    """Validate bytes, replace any existing reference, and store + wire the FK.

    Shared by every acquisition rung; only `provenance`/`source_url` differ.
    Raises ReferenceImageError on bad/oversize/unsupported bytes. Caller commits.
    """
    image, extension, _ = _decode(raw)
    width, height = image.size

    clear_reference(db, guide)

    filename = f"{guide.id}_{uuid.uuid4().hex}{extension}"
    storage_key = f"{_STORAGE_SUBDIR}/{filename}"
    (_storage_root() / filename).write_bytes(raw)

    row = GuideReferenceImage(
        guide_id=guide.id,
        storage_key=storage_key,
        provenance=provenance,
        source_url=source_url,
        alt_text=alt_text,
        width=width,
        height=height,
    )
    db.add(row)
    db.flush()  # assign row.id
    guide.reference_image_id = row.id
    return row


def store_upload(
    db: Session,
    guide: Guide,
    raw: bytes,
    *,
    alt_text: str | None = None,
) -> GuideReferenceImage:
    """Store an uploaded reference image for a guide and wire the guide FK.

    Replaces any existing reference image. Raises ReferenceImageError when the
    bytes are missing, oversize, or not a supported image. Caller commits.
    """
    return _persist(db, guide, raw, provenance="user_upload", alt_text=alt_text)


def list_model_candidates(db: Session, guide: Guide) -> list[str]:
    """Reference-image candidates from the guide's linked STL model (rung 0).

    Returns the linked model's indexed folder images (thumbnail first, then
    `image_paths`), deduped, restricted to existing files inside a scan root.
    Empty when the guide has no linked model or no indexed images.
    """
    if guide.model_id is None:
        return []
    model = db.get(Model, guide.model_id)
    if model is None:
        return []

    raw_paths: list[str] = []
    if model.thumbnail_path:
        raw_paths.append(model.thumbnail_path)
    raw_paths.extend(model.image_paths or [])

    candidates: list[str] = []
    seen: set[str] = set()
    for p in raw_paths:
        if p in seen:
            continue
        seen.add(p)
        path = Path(p)
        if _is_safe_path(path) and path.exists():
            candidates.append(p)
    return candidates


def store_from_model(
    db: Session,
    guide: Guide,
    path: str,
    *,
    alt_text: str | None = None,
) -> GuideReferenceImage:
    """Copy a linked-model folder image into the guide's reference store (rung 0).

    `path` must be one of `list_model_candidates(db, guide)` — guards against
    path traversal and against pulling an arbitrary file off the drive. Raises
    ReferenceImageError otherwise or when the bytes aren't a readable image.
    """
    if path not in set(list_model_candidates(db, guide)):
        raise ReferenceImageError(
            "That image isn't one of the linked model's folder images."
        )
    raw = Path(path).read_bytes()
    return _persist(db, guide, raw, provenance="stl_model_folder", alt_text=alt_text)


async def store_from_url(
    db: Session,
    guide: Guide,
    url: str,
    *,
    alt_text: str | None = None,
) -> GuideReferenceImage:
    """Fetch a user-supplied image URL and store it with attribution (rung 4).

    The "paste a Google image result" fallback. Reuses the hardened thumbnail
    downloader (http(s) only, size-capped, follows a product page's og:image
    one level). Records the URL as `source_url` for the hero credit. Raises
    ReferenceImageError on a bad URL/fetch or unreadable image. Caller commits.
    """
    try:
        _, raw = await fetch_image_bytes(url)
    except ThumbnailDownloadError as exc:
        raise ReferenceImageError(str(exc)) from exc
    return _persist(
        db, guide, raw, provenance="web_research", source_url=url, alt_text=alt_text
    )


def load_reference(db: Session, guide: Guide) -> tuple[bytes, str] | None:
    """Return (bytes, media_type) for the guide's reference image, or None.

    Used by both the preview endpoint and the generation vision path. Returns
    None when no image is set or the stored file has gone missing.
    """
    image_id = guide.reference_image_id
    if image_id is None:
        return None
    row = db.get(GuideReferenceImage, image_id)
    if row is None:
        return None
    path = _path_for(row.storage_key)
    if not path.exists():
        return None
    raw = path.read_bytes()
    try:
        _, _, media_type = _decode(raw)
    except ReferenceImageError:
        return None
    return raw, media_type
