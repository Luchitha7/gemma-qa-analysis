"""Lossless PDF to Markdown Converter Module.

Extracts text, structured tables, headers, SLA rules, and verbatim spiels from
company QA guideline PDF documents and converts them to formatted Markdown.
"""

import os
import re
from typing import Dict, Any, Tuple

try:
    import pymupdf as fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    try:
        import fitz
        PYMUPDF_AVAILABLE = True
    except ImportError:
        PYMUPDF_AVAILABLE = False


def convert_pdf_bytes_to_markdown(pdf_bytes: bytes, filename: str = "document.pdf") -> Tuple[str, int]:
    """Convert raw PDF bytes to clean Markdown string and return (markdown_text, page_count)."""
    markdown_pages = []
    page_count = 0

    if PYMUPDF_AVAILABLE:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page_count = len(doc)
        for page_num, page in enumerate(doc, start=1):
            markdown_pages.append(f"<!-- PAGE {page_num} START -->\n## Page {page_num}\n")
            
            try:
                # Check for tables in the page
                tabs = page.find_tables()
                if tabs.tables and len(tabs.tables) > 0:
                    for tab in tabs.tables:
                        table_md = tab.to_markdown()
                        markdown_pages.append(table_md)
                    # Also include any remaining text
                    text = page.get_text("text")
                    if text and len(text.strip()) > 50:
                        markdown_pages.append(text)
                else:
                    text = page.get_text("text")
                    markdown_pages.append(text)
            except Exception:
                text = page.get_text("text")
                markdown_pages.append(text)

            markdown_pages.append(f"\n<!-- PAGE {page_num} END -->\n")
        doc.close()
    else:
        from pypdf import PdfReader
        import io
        reader = PdfReader(io.BytesIO(pdf_bytes))
        page_count = len(reader.pages)
        for page_num, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            markdown_pages.append(f"<!-- PAGE {page_num} START -->\n## Page {page_num}\n")
            markdown_pages.append(text)
            markdown_pages.append(f"\n<!-- PAGE {page_num} END -->\n")

    full_md = "\n".join(markdown_pages)
    cleaned_md = clean_markdown(full_md)
    return cleaned_md, page_count


def convert_pdf_file_to_markdown(pdf_path: str) -> Tuple[str, int]:
    """Convert a PDF file on disk to Markdown."""
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found at {pdf_path}")
    with open(pdf_path, "rb") as f:
        return convert_pdf_bytes_to_markdown(f.read(), os.path.basename(pdf_path))


def clean_markdown(raw_md: str) -> str:
    """Format and normalize markdown extracted from PDF."""
    cleaned = re.sub(r"\r\n", "\n", raw_md)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    # Ensure headings have proper space after '#'
    cleaned = re.sub(r"^(#{1,6})([A-Za-z0-9])", r"\1 \2", cleaned, flags=re.MULTILINE)
    return cleaned.strip()
