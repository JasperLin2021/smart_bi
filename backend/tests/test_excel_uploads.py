import tempfile
import unittest
from pathlib import Path


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


if __name__ == "__main__":
    unittest.main()
