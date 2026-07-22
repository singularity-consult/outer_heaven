---
name: pdf
description: Extract text (and tables) from digital, text-based PDFs using pure-Python libraries, with no OCR. Use this whenever you need to pull text out of a PDF, whether a whole document, a page range, or tabular data. Triggers include "extract text from this PDF", "read this PDF", "get the tables out of this PDF", "what does page 12 of this PDF say", or any step that needs a PDF's contents as text (for example the `distill-book` skill checking a book source). Also covers detecting up front that a PDF is scanned or image-only and therefore not extractable without OCR, which this skill deliberately does not do.
---

# pdf

Pull text out of digital PDFs with pure-Python libraries. No OCR, no system binaries. The scope is deliberate: `pypdf` and `pdfplumber` are both permissively licensed (BSD/MIT) pure-Python packages, so nothing here needs a native install, which matters because outer_heaven is public.

## Scope, and the hard limit

- **In scope:** text extraction from digital PDFs (PDFs whose text is real text), a page range, and simple table extraction.
- **Out of scope:** OCR. A scanned or image-only PDF carries pictures of text, not text. This skill does not read those. It detects them and says so instead of grinding.

Do not reach for OCR tools (Tesseract, cloud OCR) here. If a document genuinely needs OCR, name that as an explicit, separate piece of future work and stop. Do not implement it as part of this skill.

## Detect a scanned PDF up front

Before promising a user any text, confirm the PDF actually yields some. The check is cheap: extract text from a sample of pages and count the non-whitespace characters. A digital PDF returns real characters on every page. A scanned one returns an empty string or a handful of stray characters per page.

The rule of thumb the helper script uses: under roughly 20 non-whitespace characters per sampled page, treat the PDF as image-only and tell the user it needs OCR, which is out of scope. Say this before doing any real work, not after.

Quick manual probe when you just want to know:

```python
from pypdf import PdfReader

reader = PdfReader("book.pdf")
sample = "".join((reader.pages[i].extract_text() or "") for i in range(min(5, len(reader.pages))))
print(len(sample.split()))  # near zero -> scanned/image-only, needs OCR
```

## How to extract

- **Flowing text:** `pypdf`'s `PdfReader(path).pages[i].extract_text()` per page. Join pages with a blank line between them.
- **A page range:** slice the pages you need (1-based inclusive for the user, 0-based in the API). Do not load the whole document when the user asked for pages 10-12.
- **Tables:** `pdfplumber`'s `page.extract_tables()`. It reconstructs cell grids far better than flat text extraction, which mangles columns. Use it only when the content is genuinely tabular; for prose, plain `pypdf` text is cleaner.
- **Large documents:** stream page by page rather than holding every page's text in memory at once, and write the output to a file when it is large rather than dumping it all into context.

## Helper script

`scripts/extract.py` wraps the above: text by default, `--pages "2-5"` for a range, `--tables` for pdfplumber table extraction. It resolves the page range against the real page count, and it exits with a clear non-zero status and message when the PDF looks scanned, rather than returning empty output.

Run it (this environment is Windows/PowerShell primary, Bash also available; the invocation is the same):

```powershell
python skills/pdf/scripts/extract.py document.pdf --pages "2-5"
python skills/pdf/scripts/extract.py report.pdf --tables
```

The dependencies are `pypdf` and (only for `--tables`) `pdfplumber`. Install them into the working environment if they are missing:

```powershell
pip install pypdf pdfplumber
```

`pdfplumber` is imported lazily, so plain text extraction works with `pypdf` alone.

## Conventions

- The helper script follows the `python` skill: type hints, `pathlib`, no bare `except`, a `__main__` guard, small single-purpose functions. Keep any additions to it in the same shape.
- This is a Windows/PowerShell-primary environment. Per `powershell-safety`, running Python and pip from PowerShell is fine; do not edit any existing `.ps1` file to wire this in without Benny's explicit approval.
- Keep the helper minimal and inside `skills/pdf/scripts/`. Do not pull in heavyweight or non-pure-Python PDF stacks; the point is that this stays install-clean in a public repo.
