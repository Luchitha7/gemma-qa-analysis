"""STEP 1 of the PDF -> knowledge base feature: read the text out of a PDF.

A company hands us a playbook PDF. Before we can turn it into a knowledge base
(rules + question/answer pairs), we need clean text out of the file. This script
does ONLY that: open the PDF, pull the text from every page, and print it.

Nothing here touches the live pipeline, rag.py, or knowledge_base.py. It's a
standalone tool so we can see exactly what text a PDF gives us before we ask
Gemma to make sense of it.

    python pdf_to_kb.py path/to/playbook.pdf
"""

import os
import sys

from pypdf import PdfReader
from pypdf.errors import PdfReadError, PdfStreamError


def extract_text(pdf_path):
    """Return the full text of a PDF as one string, page by page.

    Each page is separated by a marker so we can see where one ends and the
    next begins. Pages with no extractable text (e.g. scanned images) come
    back empty and are marked as such.
    """
    reader = PdfReader(pdf_path)
    parts = []
    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        parts.append(f"----- PAGE {page_number} -----")
        parts.append(text.strip() or "(no extractable text on this page)")
    return "\n".join(parts)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python pdf_to_kb.py path/to/playbook.pdf")
        sys.exit(1)

    pdf_path = sys.argv[1]

    if not os.path.exists(pdf_path):
        print(f"File not found: {pdf_path}")
        sys.exit(1)

    if not pdf_path.lower().endswith(".pdf"):
        print(f"That is not a PDF: {pdf_path}")
        print("This tool only reads PDF files. If you have a Word document,")
        print("open it and export/save it as a PDF first, then try again.")
        sys.exit(1)

    print(f"\nReading: {pdf_path}\n")
    try:
        print(extract_text(pdf_path))
    except (PdfReadError, PdfStreamError):
        print("Could not read this PDF. It may be corrupted or not a real PDF.")
        sys.exit(1)
    print()
