"""Test safe ZIP handling."""
import pytest
from pathlib import Path
import tempfile
import zipfile
from ingestion import validate_zip_file, extract_pdfs_from_zip


def test_validate_zip_rejects_path_traversal():
    """Test that path traversal attempts are rejected."""
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    
    # Create ZIP with path traversal
    with zipfile.ZipFile(tmp_path, 'w') as zf:
        zf.writestr("../../../evil.pdf", b"fake pdf")
    
    is_valid, pdfs, errors = validate_zip_file(tmp_path)
    
    assert not is_valid
    assert any("traversal" in err.lower() for err in errors)
    
    tmp_path.unlink()


def test_validate_zip_rejects_absolute_paths():
    """Test that absolute paths are rejected."""
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    
    with zipfile.ZipFile(tmp_path, 'w') as zf:
        zf.writestr("/etc/passwd", b"fake")
    
    is_valid, pdfs, errors = validate_zip_file(tmp_path)
    
    assert not is_valid
    assert any("absolute" in err.lower() for err in errors)
    
    tmp_path.unlink()


def test_validate_zip_accepts_valid_pdfs():
    """Test that valid PDF files are accepted."""
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    
    with zipfile.ZipFile(tmp_path, 'w') as zf:
        zf.writestr("bill1.pdf", b"%PDF-1.4 fake")
        zf.writestr("bill2.pdf", b"%PDF-1.4 fake")
    
    is_valid, pdfs, errors = validate_zip_file(tmp_path)
    
    assert is_valid
    assert len(pdfs) == 2
    assert "bill1.pdf" in pdfs
    assert "bill2.pdf" in pdfs
    
    tmp_path.unlink()


def test_validate_zip_rejects_non_pdf_files():
    """Test that non-PDF files are ignored."""
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    
    with zipfile.ZipFile(tmp_path, 'w') as zf:
        zf.writestr("document.txt", b"text")
        zf.writestr("bill.pdf", b"%PDF-1.4 fake")
    
    is_valid, pdfs, errors = validate_zip_file(tmp_path)
    
    assert is_valid
    assert len(pdfs) == 1
    assert pdfs[0] == "bill.pdf"
    
    tmp_path.unlink()
