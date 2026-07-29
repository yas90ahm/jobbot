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
        with open(path, encoding='utf-8') as f:
            text = f.read()

    else:
        raise ValueError(f"Unsupported resume format: {ext}")

    text = re.sub(r'\n\n\n+', '\n\n', text)
    return text
