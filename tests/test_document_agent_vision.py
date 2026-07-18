"""Tests for vision-based bill extraction and the scanned-PDF fallback path."""
from pathlib import Path
from unittest.mock import MagicMock

import fitz
import pytest

from agents.document_agent import extract_bill_from_images
from ingestion.pdf_extractor import render_pdf_pages_to_images


def _make_scanned_pdf(tmp_path: Path) -> Path:
    """Build a PDF with an image only (no embedded text layer)."""
    pdf_path = tmp_path / "scanned.pdf"
    img_doc = fitz.open()
    page = img_doc.new_page(width=200, height=200)
    page.draw_rect(fitz.Rect(10, 10, 190, 190), color=(0, 0, 0), fill=(1, 1, 1))
    pixmap = page.get_pixmap()
    img_bytes = pixmap.tobytes("png")
    img_doc.close()

    doc = fitz.open()
    page = doc.new_page(width=200, height=200)
    page.insert_image(fitz.Rect(0, 0, 200, 200), stream=img_bytes)
    doc.save(pdf_path)
    doc.close()
    return pdf_path


def test_render_pdf_pages_to_images_returns_png_bytes(tmp_path):
    pdf_path = _make_scanned_pdf(tmp_path)
    images = render_pdf_pages_to_images(pdf_path, max_pages=2)
    assert len(images) == 1
    assert images[0][:8] == b"\x89PNG\r\n\x1a\n"


def test_render_pdf_pages_to_images_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        render_pdf_pages_to_images(tmp_path / "missing.pdf")


def test_extract_bill_from_images_uses_evidence_for_dates():
    client = MagicMock()
    client.ensure_available.return_value = None
    client.extract_json.return_value = {
        "provider_name": "Salt Lake City Public Utilities",
        "utility_type": "water",
        "account_number_masked": "W2684909",
        "service_address": "1530 S West Temple",
        "billing_period_start": "2022-05-23",
        "billing_period_end": "2022-06-22",
        "statement_date": None,
        "due_date": "2022-07-14",
        "previous_balance": 176.55,
        "current_charges": 182.57,
        "amount_due": 182.57,
        "extraction_confidence": 0.95,
        "evidence": {
            "provider_name": "Salt Lake City Public Utilities",
            "amount_due": "$182.57",
            "due_date": "7/14/2026",
            "statement_date": None,
            "billing_period_start": "5/23/2026",
            "billing_period_end": "6/22/2026",
        },
    }

    extraction = extract_bill_from_images([b"fake-image-bytes"], client)

    assert extraction.provider_name == "Salt Lake City Public Utilities"
    assert str(extraction.amount_due) == "182.57"
    # Regex-parsed from evidence text, correcting the model's hallucinated year.
    assert extraction.due_date == "2026-07-14"
    assert extraction.billing_period_start == "2026-05-23"
    assert extraction.billing_period_end == "2026-06-22"
    client.extract_json.assert_called_once()
    _, kwargs = client.extract_json.call_args
    assert kwargs["images"] == [b"fake-image-bytes"]


def test_extract_bill_from_images_no_images_returns_zero_confidence():
    client = MagicMock()
    extraction = extract_bill_from_images([], client)
    assert extraction.extraction_confidence == 0.0
    client.extract_json.assert_not_called()


def test_extract_bill_from_images_handles_empty_model_response():
    client = MagicMock()
    client.ensure_available.return_value = None
    client.extract_json.return_value = None
    extraction = extract_bill_from_images([b"fake"], client)
    assert extraction.extraction_confidence == 0.0
