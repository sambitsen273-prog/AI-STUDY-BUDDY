"""
utils/file_extractor.py — Extract text from files (PDF, DOCX, TXT, Images via Mistral vision)
"""
from __future__ import annotations
import os
import warnings
from pathlib import Path

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

# Tesseract (optional fallback)
try:
    import pytesseract
    from PIL import Image
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

# Our own vision function
from utils.llm_client import vision_chat

def extract_text(file_path: str) -> str:
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
        raise ImportError("PyPDF2 not installed. pip install PyPDF2")
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
        raise ImportError("python-docx not installed. pip install python-docx")
    doc = docx.Document(file_path)
    return "\n".join(p.text for p in doc.paragraphs)

def _extract_image(file_path: str) -> str:
    # 1. Try Mistral vision
    try:
        prompt = (
            "Extract and describe all text and visual content from this image. "
            "If there is code, show it clearly. If it's a diagram, explain the concepts. "
            "Give a structured summary."
        )
        result = vision_chat(file_path, prompt)
        # Ensure we return a string
        return result if result else "[No description returned]"
    except Exception as e:
        warnings.warn(f"Mistral vision failed: {e}. Falling back to Tesseract if available.")
        # 2. Fallback to Tesseract
        if TESSERACT_AVAILABLE:
            try:
                image = Image.open(file_path)
                text = pytesseract.image_to_string(image)
                return text if text else "[No text extracted via OCR]"
            except Exception as e2:
                warnings.warn(f"Tesseract failed: {e2}")
                return f"[OCR failed: {e2}]"
        else:
            return f"[Image processing failed: {e}]"

def summarize_extracted(text: str, max_len: int = 3000) -> str:
    return text[:max_len] + ("\n...[truncated]" if len(text) > max_len else "")