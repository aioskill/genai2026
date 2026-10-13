"""Run Baidu Unlimited-OCR on every page of a PDF.

Install the model dependencies from the repository root:
    pip install -r requirements-unlimited-ocr.txt

Run with a CUDA-enabled PyTorch environment:
    python rags/ex03_unlimited_ocr/ocr_pdf.py scanned_document.pdf


Note: this script requires a GPU enabled system

"""

from __future__ import annotations

import argparse
from pathlib import Path
import tempfile

import fitz
import torch
from transformers import AutoModel, AutoTokenizer


MODEL_NAME = "baidu/Unlimited-OCR"


def load_model() -> tuple[AutoTokenizer, AutoModel]:
    """Load Unlimited-OCR on the current CUDA device."""
    if not torch.cuda.is_available():
        message = "Unlimited-OCR inference requires a CUDA-enabled GPU"
        raise RuntimeError(message)

    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_NAME,
        trust_remote_code=True,
    )
    model = AutoModel.from_pretrained(
        MODEL_NAME,
        trust_remote_code=True,
        use_safetensors=True,
        torch_dtype=torch.bfloat16,
    )
    model = model.eval().cuda()
    return tokenizer, model


def run_ocr(pdf_path: Path, output_dir: Path, dpi: int) -> None:
    """Render a PDF and run the model's multi-page document parser."""
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF does not exist: {pdf_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    tokenizer, model = load_model()

    with tempfile.TemporaryDirectory(prefix="unlimited_ocr_") as temp_dir:
        image_paths = render_pdf(pdf_path, Path(temp_dir), dpi)
        model.infer_multi(
            tokenizer,
            prompt="<image>Multi page parsing.",
            image_files=image_paths,
            output_path=str(output_dir),
            image_size=1024,
            max_length=32768,
            no_repeat_ngram_size=35,
            ngram_window=1024,
            save_results=True,
        )


def render_pdf(pdf_path: Path, output_dir: Path, dpi: int) -> list[str]:
    """Render all PDF pages into an existing temporary directory."""
    matrix = fitz.Matrix(dpi / 72, dpi / 72)
    image_paths = []

    with fitz.open(pdf_path) as document:
        for page_number, page in enumerate(document, start=1):
            image_path = output_dir / f"page_{page_number:04}.png"
            page.get_pixmap(matrix=matrix).save(image_path)
            image_paths.append(str(image_path))

    if not image_paths:
        raise ValueError(f"PDF has no pages: {pdf_path}")
    return image_paths


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract document content from a PDF with Unlimited-OCR"
    )
    parser.add_argument("pdf", type=Path, help="PDF to parse")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/tmp/unlimited_ocr_output"),
        help="Directory where the model saves OCR results",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=200,
        help="Resolution used to render each PDF page",
    )
    args = parser.parse_args()

    if args.dpi <= 0:
        parser.error("--dpi must be greater than zero")
    run_ocr(args.pdf, args.output_dir, args.dpi)
    print(f"OCR results saved under {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
