import tempfile
import unittest
from pathlib import Path

import pandas as pd


class ExcelUploadTests(unittest.TestCase):
    def test_excel_extensions_are_allowed_case_insensitively(self):
        from app.core.excel_uploads import is_allowed_excel_filename

        self.assertTrue(is_allowed_excel_filename("report.xlsx"))
        self.assertTrue(is_allowed_excel_filename("report.XLS"))
        self.assertFalse(is_allowed_excel_filename("report.csv"))
        self.assertFalse(is_allowed_excel_filename("report"))

    def test_build_storage_path_uses_excel_upload_dir_and_preserves_suffix(self):
        from app.core.excel_uploads import build_excel_storage_path

        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = build_excel_storage_path("Sales Report 2026.xlsx", base_dir=tmpdir)

        self.assertEqual(storage_path.suffix, ".xlsx")
        self.assertEqual(storage_path.parent.name, "excel")
        self.assertNotIn(" ", storage_path.name)
        self.assertTrue(storage_path.name.endswith(".xlsx"))

    def test_ensure_upload_dir_creates_excel_directory(self):
        from app.core.excel_uploads import ensure_excel_upload_dir

        with tempfile.TemporaryDirectory() as tmpdir:
            upload_dir = ensure_excel_upload_dir(base_dir=tmpdir)

            self.assertTrue(upload_dir.exists())
            self.assertTrue(upload_dir.is_dir())
            self.assertEqual(upload_dir, Path(tmpdir) / "excel")

    def test_resolve_excel_source_path_falls_back_to_current_upload_dir_by_basename(self):
        from app.core.excel_uploads import resolve_excel_source_path

        with tempfile.TemporaryDirectory() as tmpdir:
            upload_dir = Path(tmpdir) / "uploads" / "excel"
            upload_dir.mkdir(parents=True, exist_ok=True)
            actual_file = upload_dir / "legacy_file.xlsx"
            actual_file.write_bytes(b"demo")

            resolved = resolve_excel_source_path(
                "/home/qqr/smart_bi/backend/uploads/excel/legacy_file.xlsx",
                search_roots=[Path(tmpdir) / "uploads", Path(tmpdir)],
            )

        self.assertEqual(resolved, str(actual_file))

    def test_resolve_excel_source_path_falls_back_to_project_root_file(self):
        from app.core.excel_uploads import resolve_excel_source_path

        with tempfile.TemporaryDirectory() as tmpdir:
            actual_file = Path(tmpdir) / "ChatBI数据.xlsx"
            actual_file.write_bytes(b"demo")

            resolved = resolve_excel_source_path(
                "/home/qqr/smart_bi/backend/uploads/excel/ChatBI数据.xlsx",
                search_roots=[Path(tmpdir)],
            )

        self.assertEqual(resolved, str(actual_file))

    def test_resolve_excel_source_path_matches_original_name_without_uuid_suffix(self):
        from app.core.excel_uploads import resolve_excel_source_path

        with tempfile.TemporaryDirectory() as tmpdir:
            actual_file = Path(tmpdir) / "ChatBI数据.xlsx"
            actual_file.write_bytes(b"demo")

            resolved = resolve_excel_source_path(
                "/home/qqr/smart_bi/backend/uploads/excel/ChatBI数据_364bb7b394384173856b7424fb5c6eb5.xlsx",
                search_roots=[Path(tmpdir)],
            )

        self.assertEqual(resolved, str(actual_file))

    def test_generate_excel_metadata_includes_sample_values_for_key_dimensions(self):
        from app.core.excel_executor import generate_excel_metadata

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "demo.xlsx"
            with pd.ExcelWriter(path, engine="openpyxl") as writer:
                pd.DataFrame(
                    [
                        {"ASI": None, "LINE": "MPP REPS-4th FC", "NGTYPE": "1001/OP100 - Failed Hall Cal test", "STN": "OP100D"},
                        {"ASI": None, "LINE": "REPS3 BSI", "NGTYPE": "LS CW REGION 7 FAIL/", "STN": "OP100A"},
                    ]
                ).to_excel(writer, sheet_name="IP_PA_NGTYPE-失效详情", index=False)

            prompt = generate_excel_metadata(str(path))

        self.assertIn("LINE 示例值: MPP REPS-4th FC, REPS3 BSI", prompt)
        self.assertIn("NGTYPE 示例值: 1001/OP100 - Failed Hall Cal test, LS CW REGION 7 FAIL/", prompt)
        self.assertIn("STN 示例值: OP100D, OP100A", prompt)
        self.assertNotIn("ASI 示例值", prompt)


if __name__ == "__main__":
    unittest.main()
