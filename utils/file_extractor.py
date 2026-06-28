"""
utils/file_extractor.py — Extract text from various file types (PDF, DOCX, TXT, Images)
"""
from __future__ import annotations
import os
import tempfile
from typing import Optional

# PDF
try:
    import PyPDF2
except ImportError:
    PyPDF2 = None

# DOCX
try:
    import docx
except ImportError:
    docx = None

# Images / OCR
try:
    from PIL import Image
    import pytesseract
except ImportError:
    Image = None
    pytesseract = None

def extract_text(file_path: str) -> str:
    """
    Route file to appropriate extractor based on extension.
    """
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".txt":
        return _extract_txt(file_path)
    elif ext == ".pdf":
        return _extract_pdf(file_path)
    elif ext in [".docx", ".doc"]:
        return _extract_docx(file_path)
    elif ext in [".png", ".jpg", ".jpeg", ".webp", ".bmp"]:
        return _extract_image(file_path)
    else:
        raise ValueError(f"Unsupported file type: {ext}")

def _extract_txt(file_path: str) -> str:
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()

def _extract_pdf(file_path: str) -> str:
    if PyPDF2 is None:
        raise ImportError("PyPDF2 not installed. Please install with: pip install PyPDF2")
    text = []
    with open(file_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text.append(page_text)
    return "\n".join(text)

def _extract_docx(file_path: str) -> str:
    if docx is None:
        raise ImportError("python-docx not installed. Please install with: pip install python-docx")
    doc = docx.Document(file_path)
    paragraphs = [p.text for p in doc.paragraphs]
    return "\n".join(paragraphs)

def _extract_image(file_path: str) -> str:
    if Image is None or pytesseract is None:
        raise ImportError("Pillow and/or pytesseract not installed. For OCR, please install: pip install pillow pytesseract")
    image = Image.open(file_path)
    text = pytesseract.image_to_string(image)
    return text

def summarize_extracted(text: str, max_len: int = 3000) -> str:
    """
    Truncate extracted text to avoid token limits.
    """
    if len(text) > max_len:
        return text[:max_len] + "\n...[truncated]"
    return text