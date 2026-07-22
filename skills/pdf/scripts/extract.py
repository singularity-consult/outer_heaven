"""Extract text from a digital (text-based) PDF.

Pure Python, no system binaries, no OCR. If the PDF is scanned or image-only,
this script detects that and exits with a clear message instead of returning
empty output. See ../SKILL.md for scope and usage.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# A text PDF yields real characters on every page. A scanned or image-only PDF
# yields almost nothing. Below this many non-whitespace chars per sampled page
# we treat the document as image-only and refuse, rather than return garbage.
MIN_CHARS_PER_PAGE = 20


def parse_page_range(spec: str, page_count: int) -> list[int]:
    """Turn "3", "2-5", "2-", or "-4" into a list of 0-based page indices."""
    spec = spec.strip()
    if "-" in spec:
        lo_s, hi_s = spec.split("-", 1)
        lo = int(lo_s) if lo_s else 1
        hi = int(hi_s) if hi_s else page_count
    else:
        lo = hi = int(spec)
    if lo < 1 or hi > page_count or lo > hi:
        raise ValueError(f"page range {spec!r} out of bounds for {page_count} page(s)")
    return list(range(lo - 1, hi))


def extract_text(pdf_path: Path, pages: list[int] | None) -> tuple[str, int]:
    """Return (text, sampled_page_count) using pypdf."""
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    indices = pages if pages is not None else range(len(reader.pages))
    chunks: list[str] = []
    sampled = 0
    for i in indices:
        chunks.append(reader.pages[i].extract_text() or "")
        sampled += 1
    return "\n\n".join(chunks), sampled


def looks_scanned(text: str, sampled_pages: int) -> bool:
    """True when the sampled pages carry too little text to be a digital PDF."""
    if sampled_pages == 0:
        return False
    non_ws = len("".join(text.split()))
    return non_ws < MIN_CHARS_PER_PAGE * sampled_pages


def extract_tables(pdf_path: Path, pages: list[int] | None) -> str:
    """Extract tables as tab-separated blocks using pdfplumber (lazy import)."""
    import pdfplumber

    lines: list[str] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        indices = pages if pages is not None else range(len(pdf.pages))
        for i in indices:
            for table in pdf.pages[i].extract_tables():
                for row in table:
                    lines.append("\t".join("" if c is None else str(c) for c in row))
                lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract text from a digital PDF. No OCR."
    )
    parser.add_argument("pdf", type=Path, help="path to the PDF file")
    parser.add_argument(
        "--pages", help='page range, e.g. "3" or "2-5" (1-based, inclusive)'
    )
    parser.add_argument(
        "--tables",
        action="store_true",
        help="extract tables via pdfplumber instead of flowing text",
    )
    args = parser.parse_args()

    if not args.pdf.is_file():
        print(f"error: no such file: {args.pdf}", file=sys.stderr)
        return 2

    from pypdf import PdfReader

    page_count = len(PdfReader(str(args.pdf)).pages)
    pages = parse_page_range(args.pages, page_count) if args.pages else None

    text, sampled = extract_text(args.pdf, pages)
    if looks_scanned(text, sampled):
        non_ws = len("".join(text.split()))
        print(
            f"error: {args.pdf.name} yields almost no extractable text "
            f"({non_ws} chars over {sampled} page(s)). It is most likely scanned "
            "or image-only. This skill does not do OCR, so extraction is not "
            "possible here.",
            file=sys.stderr,
        )
        return 3

    print(extract_tables(args.pdf, pages) if args.tables else text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
