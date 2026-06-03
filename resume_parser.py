"""
PDF + Word resume parser — extracts clean text from uploaded resumes.
Supports: .pdf, .docx, .doc, .txt
"""

import os
import pdfplumber
import docx


def parse_resume(file_path: str) -> str:
    """Extract plain text from a resume file. Supports PDF, DOCX, TXT."""
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        return _parse_pdf(file_path)
    elif ext in (".docx", ".doc"):
        return _parse_docx(file_path)
    elif ext == ".txt":
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    else:
        raise ValueError(f"Unsupported file type: {ext}. Use PDF, DOCX, or TXT.")


def _parse_pdf(path: str) -> str:
    text_blocks = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                text_blocks.append(text.strip())
    return "\n\n".join(text_blocks)


def _parse_docx(path: str) -> str:
    doc = docx.Document(path)
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    return "\n".join(paragraphs)


def parse_and_score(file_path: str, candidate_name: str, job_title: str,
                    job_description: str = "", job_requirements: str = "") -> dict:
    """Parse a resume file and immediately score it. Returns score dict."""
    from candidate_scorer import score_candidate_from_resume
    text = parse_resume(file_path)
    return score_candidate_from_resume(text, candidate_name, job_title, job_description, job_requirements)
