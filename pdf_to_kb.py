"""PDF -> knowledge base feature (early steps).

A company hands us a playbook PDF. Before we can turn it into a knowledge base
(rules + question/answer pairs), we have to get the text out and cut it into
pieces small enough to hand to Gemma one at a time.

This standalone tool does two things and nothing else:
  STEP 1  read the PDF and pull clean text out, page by page.
  STEP 2  split that text into chunks (a few pages each) so a later step can
          feed one chunk to Gemma at a time.

It does not touch the live pipeline, rag.py, or knowledge_base.py.

    python pdf_to_kb.py path/to/playbook.pdf            # print the text
    python pdf_to_kb.py path/to/playbook.pdf chunks     # show how it splits
"""

import os
import sys

from pypdf import PdfReader
from pypdf.errors import PdfReadError, PdfStreamError

# How many pages go into one chunk. A playbook page is small, so a few pages
# together still fit comfortably in one Gemma call. Tune this later if needed.
PAGES_PER_CHUNK = 3


def extract_pages(pdf_path):
    """Return the PDF as a list of (page_number, text), one item per page.

    Pages with no extractable text (e.g. scanned images) come back with a
    clear placeholder instead of an empty string, so nothing downstream has to
    guess what an empty page means.
    """
    reader = PdfReader(pdf_path)
    pages = []
    for page_number, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        pages.append((page_number, text or "(no extractable text on this page)"))
    return pages


def extract_text(pdf_path):
    """The whole PDF as one string, with a marker before each page."""
    parts = []
    for page_number, text in extract_pages(pdf_path):
        parts.append(f"----- PAGE {page_number} -----")
        parts.append(text)
    return "\n".join(parts)


def chunk_pages(pages, pages_per_chunk=PAGES_PER_CHUNK):
    """Group pages into chunks of `pages_per_chunk` pages each.

    Takes the list from extract_pages and returns a list of dicts:
      {"pages": "1-3", "text": "...the text of those pages..."}

    Grouping by whole pages (instead of by raw character count) keeps each
    chunk on clean page boundaries, so a rule or Q&A never gets cut in half
    mid-sentence between two chunks.
    """
    chunks = []
    for start in range(0, len(pages), pages_per_chunk):
        group = pages[start:start + pages_per_chunk]
        first_page = group[0][0]
        last_page = group[-1][0]
        label = f"{first_page}" if first_page == last_page else f"{first_page}-{last_page}"
        body = "\n\n".join(f"[Page {num}]\n{text}" for num, text in group)
        chunks.append({"pages": label, "text": body})
    return chunks


def _die(message):
    print(message)
    sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        _die("Usage: python pdf_to_kb.py path/to/playbook.pdf [chunks]")

    pdf_path = sys.argv[1]
    show_chunks = len(sys.argv) > 2 and sys.argv[2].lower() == "chunks"

    if not os.path.exists(pdf_path):
        _die(f"File not found: {pdf_path}")
    if not pdf_path.lower().endswith(".pdf"):
        _die(f"That is not a PDF: {pdf_path}\n"
             "This tool only reads PDF files. If you have a Word document,\n"
             "open it and export/save it as a PDF first, then try again.")

    print(f"\nReading: {pdf_path}\n")
    try:
        pages = extract_pages(pdf_path)
    except (PdfReadError, PdfStreamError):
        _die("Could not read this PDF. It may be corrupted or not a real PDF.")

    if not show_chunks:
        # STEP 1: just print the text, page by page.
        for page_number, text in pages:
            print(f"----- PAGE {page_number} -----")
            print(text)
        print()
    else:
        # STEP 2: show how the text splits into chunks for Gemma.
        chunks = chunk_pages(pages)
        print(f"{len(pages)} page(s) split into {len(chunks)} chunk(s) "
              f"of up to {PAGES_PER_CHUNK} page(s) each.\n")
        for i, chunk in enumerate(chunks, start=1):
            preview = chunk["text"].replace("\n", " ")
            preview = (preview[:100] + "...") if len(preview) > 100 else preview
            print(f"  Chunk {i}  (pages {chunk['pages']}, "
                  f"{len(chunk['text'])} chars): {preview}")
        print()
