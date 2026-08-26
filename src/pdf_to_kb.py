"""STEP 1 of the PDF -> knowledge base feature: read the text out of a PDF.

A company hands us a playbook PDF. Before we can turn it into a knowledge base
(rules + question/answer pairs), we need clean text out of the file. This script
does ONLY that: open the PDF, pull the text from every page, and print it.

Nothing here touches the live pipeline, rag.py, or knowledge_base.py. It's a
standalone tool so we can see exactly what text a PDF gives us before we ask
Gemma to make sense of it.

    python pdf_to_kb.py path/to/playbook.pdf
"""

import sys

from pypdf import PdfReader


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
    print(f"\nReading: {pdf_path}\n")
    print(extract_text(pdf_path))
    print()