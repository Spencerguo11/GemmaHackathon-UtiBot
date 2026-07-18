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
