"""Extract text from a PDF by rendering each page and running Tesseract OCR."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil

import fitz
import pytesseract
from PIL import Image


"""
sudo apt install tesseract-ocr
"""
def extract_pdf_text(pdf_path: Path, dpi: int) -> str:
    """Render each page of a PDF and return its OCR text."""
    configure_tesseract()
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF does not exist: {pdf_path}")

    scale = dpi / 72
    render_matrix = fitz.Matrix(scale, scale)
    page_text = []

    with fitz.open(pdf_path) as document:
        for page in document:
            pixmap = page.get_pixmap(matrix=render_matrix, alpha=False)
            image = Image.frombytes(
                "RGB",
                (pixmap.width, pixmap.height),
                pixmap.samples,
            )
            page_text.append(pytesseract.image_to_string(image).strip())

    if not page_text:
        raise ValueError(f"PDF has no pages: {pdf_path}")
    return "\n\n".join(page_text)


def configure_tesseract() -> None:
    """Configure Tesseract and explain how to install or locate it."""
    configured_path = os.environ.get("TESSERACT_CMD")
    executable = configured_path or shutil.which("tesseract")
    if not executable:
        message = (
            "Tesseract is not installed or is not on PATH. Install the "
            "Tesseract OCR engine, then rerun this script. If it is installed "
            "outside PATH, set TESSERACT_CMD to its executable path."
        )
        raise RuntimeError(message)

    pytesseract.pytesseract.tesseract_cmd = executable


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert a PDF to text with Tesseract OCR"
    )
    parser.add_argument("pdf", type=Path, help="PDF to convert")
    parser.add_argument(
        "--output-file",
        type=Path,
        default="/tmp/output.txt",
        help=(
            "Text output path (defaults to the PDF name with a .txt extension)"
        ),
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=200,
        help="Resolution used to render each PDF page (default: 200)",
    )
    args = parser.parse_args()

    if args.dpi <= 0:
        parser.error("--dpi must be greater than zero")

    output_path = args.output or args.pdf.with_suffix(".txt")
    text = extract_pdf_text(args.pdf, args.dpi)
    output_path.write_text(text + "\n", encoding="utf-8")
    print(f"Extracted text saved to {output_path}")


if __name__ == "__main__":
    main()
