import re
from pathlib import Path


def load_resume(path: str) -> str:
    """Load resume text from PDF, DOCX, TXT, or MD file.

    Args:
        path: File path to resume.

    Returns:
        Resume text with 3+ consecutive newlines collapsed to 2.

    Raises:
        FileNotFoundError: If file does not exist.
        ValueError: If file format is not supported.
        ImportError: If required library (pypdf or python-docx) is missing.
    """
    path_obj = Path(path)

    if not path_obj.exists():
        raise FileNotFoundError(f"Resume file not found: {path}")

    ext = path_obj.suffix.lower()

    if ext == '.pdf':
        try:
            from pypdf import PdfReader
        except ImportError:
            raise ImportError("pypdf is required for PDF support")

        reader = PdfReader(path)
        text = ''.join(page.extract_text() or '' for page in reader.pages)

    elif ext == '.docx':
        try:
            from docx import Document
        except ImportError:
            raise ImportError("python-docx is required for DOCX support")

        doc = Document(path)
        text = '\n'.join(para.text for para in doc.paragraphs)

    elif ext in ('.txt', '.md'):
        with open(path, encoding='utf-8', errors='replace') as f:
            text = f.read()

    elif ext == '.doc':
        raise ValueError(
            "Old Word .doc format is not supported - open it in Word and "
            "Save As .docx (or .pdf), then upload that.")

    else:
        raise ValueError(f"Unsupported resume format: {ext} - use .pdf, .docx, .txt, or .md")

    text = re.sub(r'\n\n\n+', '\n\n', text)
    if len(text.strip()) < 150:
        raise ValueError(
            "Could not read text from this file - if it is a scanned/image PDF, "
            "export a text version (.docx or a text-based PDF) and upload that.")
    return text
