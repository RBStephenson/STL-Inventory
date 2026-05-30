"""
File system scanner.

Folder structure on disk (variable depth):
  <root>/
    <Creator>/
      config.orynt3d             ← creator-level config (optional)
      <Character>/               ← user-created grouping folder
        Images/                  ← shared images (may be here or anywhere)
        <Product Variant>/       ← extracted from a ZIP ← Model
          Akuma/                 ← parts sub-folder (not a separate model)
          Base/
        <Another Variant -Pre Supported>/   ← separate Model

Leaf detection priority:
  1. config.orynt3d with modelMode == 2 (explicit Orynt3D leaf)
  2. Folder name contains scale/type/modifier signals (product boundary)
  3. Folder contains STLs and all child dirs look like parts sub-folders
  4. Folder contains STLs and has no children with STLs (deepest fallback)

Auto-tags are generated from detected scale, type, and modifier tokens.
needs_review=True is set when confidence is low.
"""
import logging
import threading
from datetime import datetime
from pathlib import Path
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Creator, Model, STLFile, ScanRoot
from app.services import orynt3d_parser, name_parser

logger = logging.getLogger(__name__)

STL_EXTENSIONS = {".stl", ".3mf", ".obj"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

_scan_lock = threading.Lock()
_scan_state: dict = {"running": False, "message": "idle", "models_found": 0, "files_found": 0}


def get_status() -> dict:
    return dict(_scan_state)


def scan_all_roots(db: Session | None = None):
    if not _scan_lock.acquire(blocking=False):
        return
    _scan_state.update(running=True, message="starting", models_found=0, files_found=0)
    try:
        _db = db or SessionLocal()
        own_db = db is None
        try:
            roots = _db.query(ScanRoot).filter(ScanRoot.enabled == True).all()
            for root in roots:
                _scan_root(root, _db)
                root.last_scanned = datetime.utcnow()
                _db.commit()
        finally:
            if own_db:
                _db.close()
    except Exception as e:
        logger.exception(f"Scan failed: {e}")
        _scan_state["message"] = f"error: {e}"
    finally:
        _scan_state["running"] = False
        _scan_lock.release()


def _scan_root(root: ScanRoot, db: Session):
    root_path = Path(root.path)
    if not root_path.exists():
        logger.warning(f"Scan root not found: {root.path}")
        _scan_state["message"] = f"path not found: {root.path}"
        return

    for creator_dir in sorted(root_path.iterdir()):
        if not creator_dir.is_dir():
            continue

        _scan_state["message"] = f"scanning {creator_dir.name}"

        creator_meta = orynt3d_parser.parse_creator_config(str(creator_dir)) or {}
        creator_name = creator_meta.get("creator_name") or creator_dir.name
        creator = _get_or_create_creator(creator_name, db)

        _walk_for_models(
            folder=creator_dir,
            creator=creator,
            inherited=creator_meta,
            db=db,
            creator_boundary=creator_dir,
            character=None,
        )


def _walk_for_models(
    folder: Path,
    creator: Creator,
    inherited: dict,
    db: Session,
    creator_boundary: Path,
    character: str | None,
    parent_names: list[str] | None = None,
):
    if not folder.is_dir():
        return

    # --- Step 1: explicit Orynt3D leaf ---
    model_meta = orynt3d_parser.parse_model_config(str(folder))
    if model_meta and model_meta.get("is_leaf"):
        _index_model(folder, creator, model_meta, inherited, db, creator_boundary, character)
        return

    child_dirs = [d for d in sorted(folder.iterdir()) if d.is_dir()]
    has_direct_stls = _has_stls(folder, recurse=False)

    # Collect file names for signal detection
    try:
        filenames = [f.name for f in folder.iterdir() if f.is_file()]
    except Exception:
        filenames = []

    # --- Step 2: name-based product detection (folder + files + parents) ---
    signals = name_parser.parse_folder(
        str(folder),
        filenames=filenames,
        parent_names=parent_names,
    )
    if signals.is_product:
        _index_model(folder, creator, model_meta, inherited, db, creator_boundary, character,
                     auto_signals=signals)
        return

    # --- Step 3: has STLs + children look like parts ---
    if has_direct_stls or _any_child_has_stls(child_dirs):
        child_names = [d.name for d in child_dirs]
        if has_direct_stls and name_parser.children_look_like_parts(child_names):
            _index_model(folder, creator, model_meta, inherited, db, creator_boundary, character,
                         auto_signals=signals)
            return

        # --- Step 4: deepest fallback — STLs here, nothing below ---
        if has_direct_stls and not _any_child_has_stls(child_dirs):
            _index_model(folder, creator, model_meta, inherited, db, creator_boundary, character,
                         auto_signals=signals)
            return

    # Not a leaf — recurse, carrying this folder name as character context
    # and adding it to parent_names for child signal detection.
    next_character = character
    if folder != creator_boundary and not signals.is_parts:
        next_character = folder.name

    next_parents = (parent_names or []) + [folder.name]

    for child in sorted(child_dirs):
        _walk_for_models(child, creator, inherited, db, creator_boundary,
                         character=next_character, parent_names=next_parents)


def _index_model(
    folder: Path,
    creator: Creator,
    model_meta: dict | None,
    inherited: dict,
    db: Session,
    creator_boundary: Path | None,
    character: str | None,
    auto_signals: name_parser.NameSignals | None = None,
):
    folder_path = str(folder)
    model = db.query(Model).filter(Model.folder_path == folder_path).first()

    if model is None:
        model = Model(
            name=folder.name,
            folder_path=folder_path,
            creator_id=creator.id,
        )
        db.add(model)
        db.flush()

    # Character grouping
    if character:
        model.character = character

    # Auto-detected signals
    if auto_signals:
        model.auto_tags = auto_signals.auto_tags
        # Only flag needs_review if the leaf detection itself was ambiguous
        # (low confidence AND no orynt3d config). Missing scale tags alone
        # are not a problem — many models genuinely don't state a scale.
        if not model_meta and auto_signals.confidence < 0.25:
            model.needs_review = True

    # orynt3d metadata
    if model_meta:
        if model_meta.get("name"):
            model.title = model_meta["name"]
        model.notes = model_meta.get("notes") or model.notes
        model.tags = model_meta.get("tags") or model.tags or []
        model.orynt3d_parsed = True
        model.source_site = (
            model_meta.get("source_site")
            or inherited.get("source_site")
            or model.source_site
        )
        model.source_url = model_meta.get("source_url") or model.source_url
        attrs = model_meta.get("attributes") or {}
        if attrs:
            model.custom_attributes = attrs
        model.orynt3d_collections = model_meta.get("collections") or model.orynt3d_collections or []
        if model_meta.get("cover_path"):
            model.thumbnail_path = model_meta["cover_path"]
    elif inherited:
        model.source_site = inherited.get("source_site") or model.source_site

    # Thumbnail: walk upward if not already set
    if not model.thumbnail_path:
        _find_thumbnail(model, folder, boundary=creator_boundary or folder)

    model.updated_at = datetime.utcnow()
    _index_stl_files(model, folder, db)
    db.commit()

    _scan_state["models_found"] += 1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _has_stls(folder: Path, recurse: bool = False) -> bool:
    if recurse:
        return any(f.suffix.lower() in STL_EXTENSIONS for f in folder.rglob("*") if f.is_file())
    return any(f.suffix.lower() in STL_EXTENSIONS for f in folder.iterdir() if f.is_file())


def _any_child_has_stls(child_dirs: list[Path]) -> bool:
    return any(_has_stls(d, recurse=True) for d in child_dirs)


def _find_thumbnail(model: Model, leaf: Path, boundary: Path):
    """
    Walk upward from leaf to creator boundary looking for an image.
    Checks preferred sub-folder names first at each level.
    """
    PREFERRED = {
        "renders", "render", "images", "image", "photos", "photo",
        "preview", "previews", "pics", "pictures", "gallery",
    }

    def first_image(folder: Path) -> Path | None:
        for sub in sorted(folder.iterdir()):
            if sub.is_dir() and sub.name.lower() in PREFERRED:
                for img in sorted(sub.iterdir()):
                    if img.is_file() and img.suffix.lower() in IMAGE_EXTENSIONS:
                        return img
        for img in sorted(folder.iterdir()):
            if img.is_file() and img.suffix.lower() in IMAGE_EXTENSIONS:
                return img
        return None

    current = leaf
    while True:
        found = first_image(current)
        if found:
            model.thumbnail_path = str(found)
            return
        if current == boundary or current.parent == current:
            break
        current = current.parent


def _index_stl_files(model: Model, folder: Path, db: Session):
    existing = {f.path for f in model.stl_files}
    for stl in sorted(folder.rglob("*")):
        if not stl.is_file() or stl.suffix.lower() not in STL_EXTENSIONS:
            continue
        path_str = str(stl)
        if path_str in existing:
            continue
        db.add(STLFile(
            model_id=model.id,
            path=path_str,
            filename=stl.name,
            size_bytes=stl.stat().st_size,
        ))
        _scan_state["files_found"] += 1


def _get_or_create_creator(name: str, db: Session) -> Creator:
    creator = db.query(Creator).filter(Creator.name == name).first()
    if not creator:
        creator = Creator(name=name)
        db.add(creator)
        db.flush()
    return creator
