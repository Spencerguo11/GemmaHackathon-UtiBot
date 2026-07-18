"""PDF text extraction."""
from pathlib import Path
from typing import Optional


def extract_pdf_text(pdf_path: Path) -> Optional[str]:
    """
    Extract text from PDF using PyMuPDF.
    
    Args:
        pdf_path: Path to PDF file
    
    Returns:
        Extracted text or None if no text found
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise ImportError("PyMuPDF not installed. Run: pip install pymupdf")
    
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    
    try:
        doc = fitz.open(pdf_path)
        text = ""
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            text += page.get_text()
        
        doc.close()
        
        if not text.strip():
            return None
        
        return text
    
    except Exception as e:
        raise RuntimeError(f"Error extracting PDF text: {e}")


def render_pdf_pages_to_images(
    pdf_path: Path,
    max_pages: int = 2,
    zoom: float = 2.0,
) -> list[bytes]:
    """
    Render PDF pages to PNG image bytes for vision-model extraction.

    Used as a fallback when a PDF has no embedded text layer (e.g. a
    scanned/photographed bill), so a vision-capable model can still read
    the bill directly from the page image.

    Args:
        pdf_path: Path to PDF file
        max_pages: Maximum number of pages to render (keeps prompts small/fast)
        zoom: Render scale factor; higher improves legibility of small text

    Returns:
        List of PNG image byte strings, one per rendered page
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise ImportError("PyMuPDF not installed. Run: pip install pymupdf")

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    images: list[bytes] = []
    try:
        doc = fitz.open(pdf_path)
        matrix = fitz.Matrix(zoom, zoom)
        for page_num in range(min(len(doc), max_pages)):
            page = doc[page_num]
            pixmap = page.get_pixmap(matrix=matrix)
            images.append(pixmap.tobytes("png"))
        doc.close()
    except Exception as e:
        raise RuntimeError(f"Error rendering PDF to images: {e}")

    return images

