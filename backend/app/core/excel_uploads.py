from pathlib import Path
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
