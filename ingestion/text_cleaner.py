"""Text cleaning and normalization."""
import re
from typing import Optional


def clean_bill_text(text: str) -> str:
    """
    Clean and normalize bill text for extraction.
    
    Args:
        text: Raw extracted text
    
    Returns:
        Cleaned text
    """
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Remove special characters but keep common punctuation
    text = re.sub(r'[^\w\s\-\.:/(),$]', '', text)
    
    # Normalize line breaks
    text = text.strip()
    
    return text


def extract_sentence_context(text: str, search_term: str, context_words: int = 10) -> Optional[str]:
    """
    Extract context around a search term.
    
    Args:
        text: Full text to search
        search_term: Term to find
        context_words: Number of words before/after
    
    Returns:
        Context string or None if not found
    """
    words = text.split()
    search_term_lower = search_term.lower()
    
    for i, word in enumerate(words):
        if search_term_lower in word.lower():
            start = max(0, i - context_words)
            end = min(len(words), i + context_words + 1)
            context = " ".join(words[start:end])
            return context
    
    return None
