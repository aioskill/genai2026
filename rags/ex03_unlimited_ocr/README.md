# Unlimited-OCR PDF example

This example uses [Baidu Unlimited-OCR](https://github.com/baidu/Unlimited-OCR)
to parse a scanned or image-based PDF. It renders each PDF page and sends all
pages to the model's multi-page inference method. The saved OCR output can then
be used as text input for a RAG index.

## Setup

Use Python 3.12 and install the pinned model dependencies from the repository
root:

```bash
pip install -r requirements-unlimited-ocr.txt
```

The upstream Transformers example requires an NVIDIA GPU with CUDA. Model
weights are downloaded from Hugging Face on the first run.

## Run

```bash
python rags/ex03_unlimited_ocr/ocr_pdf.py ./scanned_document.pdf \
    --output-dir ./unlimited_ocr_output
```

The model writes its OCR result files to `unlimited_ocr_output/`. To change the
page rendering resolution, pass `--dpi` (default: `200`).

This example focuses on OCR preprocessing. For a complete retrieval and answer
flow, see [`ex01_pdf_rag`](../ex01_pdf_rag/).
