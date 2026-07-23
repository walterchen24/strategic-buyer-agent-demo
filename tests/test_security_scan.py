from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.security_scan import scan


class SecurityScanTests(unittest.TestCase):
    def test_clean_synthetic_file_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "safe.txt").write_text("contact@sample.example", encoding="utf-8")
            self.assertEqual(scan(root), [])

    def test_non_example_email_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "unsafe.txt").write_text("person@company.com", encoding="utf-8")
            self.assertTrue(scan(root))

    def test_private_key_marker_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "unsafe.txt").write_text(
                "-----BEGIN PRIVATE KEY-----", encoding="utf-8"
            )
            self.assertTrue(scan(root))


if __name__ == "__main__":
    unittest.main()
