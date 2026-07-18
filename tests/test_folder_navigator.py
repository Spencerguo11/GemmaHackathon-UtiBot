"""Tests for folder navigator."""
from pathlib import Path

import pytest

from services.folder_navigator import find_zip_files, list_directory, resolve_user_path


def test_list_home_downloads_if_exists():
    downloads = Path.home() / "Downloads"
    if not downloads.exists():
        pytest.skip("Downloads folder not present")
    result = list_directory(str(downloads))
    assert "entries" in result
    assert result["path"]


def test_resolve_rejects_outside_allowed_roots():
    with pytest.raises(ValueError):
        resolve_user_path("/etc/passwd")
