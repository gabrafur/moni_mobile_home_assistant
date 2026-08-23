# SPDX-FileCopyrightText: 2026 Gabriel B. Furlan
# SPDX-License-Identifier: MIT
"""Regression tests for repository licensing metadata."""

from __future__ import annotations

from pathlib import Path
import unittest


REPOSITORY_ROOT = Path(__file__).parents[1]
SPDX_MARKER = "# SPDX-License-Identifier: MIT"


class RepositoryMetadataTest(unittest.TestCase):
    """Keep the repository-wide MIT declaration explicit and detectable."""

    def test_license_contains_standard_mit_grant(self) -> None:
        license_text = (REPOSITORY_ROOT / "LICENSE").read_text(encoding="utf-8")

        self.assertTrue(license_text.startswith("MIT License\n"))
        self.assertIn("Permission is hereby granted, free of charge", license_text)
        self.assertIn('THE SOFTWARE IS PROVIDED "AS IS"', license_text)

    def test_python_sources_declare_mit_spdx_identifier(self) -> None:
        source_files = sorted(
            (REPOSITORY_ROOT / "custom_components" / "moni_mobile").glob("*.py")
        ) + sorted((REPOSITORY_ROOT / "tests").glob("*.py"))

        self.assertTrue(source_files)
        for source_file in source_files:
            with self.subTest(source_file=source_file.relative_to(REPOSITORY_ROOT)):
                header = source_file.read_text(encoding="utf-8").splitlines()[:3]
                self.assertIn(SPDX_MARKER, header)


if __name__ == "__main__":
    unittest.main()
