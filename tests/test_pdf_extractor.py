"""Test PDF text extraction."""
from pathlib import Path

import pytest

from ingestion.pdf_extractor import extract_pdf_text


def test_extract_pdf_text_missing_file():
    with pytest.raises(FileNotFoundError):
        extract_pdf_text(Path("does-not-exist.pdf"))
