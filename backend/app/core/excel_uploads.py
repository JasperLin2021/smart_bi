from pathlib import Path
import re
from uuid import uuid4


BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_UPLOAD_BASE_DIR = BACKEND_DIR / "uploads"
ALLOWED_EXCEL_SUFFIXES = {".xlsx", ".xls"}


def is_allowed_excel_filename(filename: str) -> bool:
    suffix = Path(filename or "").suffix.lower()
    return suffix in ALLOWED_EXCEL_SUFFIXES


def ensure_excel_upload_dir(base_dir: str | Path | None = None) -> Path:
    root_dir = Path(base_dir) if base_dir else DEFAULT_UPLOAD_BASE_DIR
    upload_dir = root_dir / "excel"
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def build_excel_storage_path(filename: str, base_dir: str | Path | None = None) -> Path:
    suffix = Path(filename).suffix.lower()
    safe_name = Path(filename).stem.strip().replace(" ", "_")
    if not safe_name:
        safe_name = "excel"
    unique_name = f"{safe_name}_{uuid4().hex}{suffix}"
    return ensure_excel_upload_dir(base_dir=base_dir) / unique_name


def resolve_excel_source_path(
    file_path: str,
    search_roots: list[str | Path] | None = None,
) -> str:
    candidate = Path(file_path)
    if candidate.is_file():
        return str(candidate)

    filename = candidate.name
    roots = [Path(root) for root in (search_roots or [DEFAULT_UPLOAD_BASE_DIR, BACKEND_DIR, BACKEND_DIR.parent])]
    fallback_candidates: list[Path] = []
    for root in roots:
        fallback_candidates.append(root / filename)
        fallback_candidates.append(root / "excel" / filename)
        fallback_candidates.append(root / "uploads" / "excel" / filename)

    for fallback in fallback_candidates:
        if fallback.is_file():
            return str(fallback)

    stem = candidate.stem
    stem_without_uuid = re.sub(r"_[0-9a-fA-F]{32}$", "", stem)
    if stem_without_uuid and stem_without_uuid != stem:
        for root in roots:
            for pattern in (
                f"{stem_without_uuid}{candidate.suffix}",
                f"{stem_without_uuid}_*{candidate.suffix}",
            ):
                for matched in root.glob(pattern):
                    if matched.is_file():
                        return str(matched)
                for matched in (root / "excel").glob(pattern):
                    if matched.is_file():
                        return str(matched)
                for matched in (root / "uploads" / "excel").glob(pattern):
                    if matched.is_file():
                        return str(matched)

    return str(candidate)
