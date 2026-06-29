"""
app/documents/ocr.py — OCR for scanned/low-text PDF pages.

Uses Tesseract (default) or EasyOCR (optional) depending on config.
OCR is called only when a page's character count is below the configured threshold.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class OcrResult:
    page_number: int
    text: str
    engine: str
    confidence: float | None = None  # mean confidence if available (0.0–1.0)
    success: bool = True
    error: str = ""


def ocr_page_image(
    image: Any,  # PIL Image
    engine: str = "tesseract",
    lang: str = "eng",
) -> OcrResult:
    """Run OCR on a single PIL Image and return an OcrResult."""
    if engine == "tesseract":
        return _tesseract(image, lang=lang, page_number=0)
    elif engine == "easyocr":
        return _easyocr(image, lang=lang, page_number=0)
    else:
        return OcrResult(
            page_number=0, text="", engine=engine, success=False, error=f"Unknown engine: {engine}"
        )


def ocr_pdf_page(
    pdf_path: str | Path,
    page_number: int,  # 1-indexed
    engine: str = "tesseract",
    lang: str = "eng",
    dpi: int = 300,
) -> OcrResult:
    """Convert one PDF page to an image and OCR it."""
    try:
        from pdf2image import convert_from_path  # type: ignore[import]
    except ImportError:
        return OcrResult(
            page_number=page_number,
            text="",
            engine=engine,
            success=False,
            error="pdf2image not installed; OCR unavailable.",
        )

    try:
        images = convert_from_path(
            str(pdf_path),
            dpi=dpi,
            first_page=page_number,
            last_page=page_number,
        )
    except Exception as exc:
        return OcrResult(
            page_number=page_number,
            text="",
            engine=engine,
            success=False,
            error=f"pdf2image conversion failed: {exc}",
        )

    if not images:
        return OcrResult(
            page_number=page_number,
            text="",
            engine=engine,
            success=False,
            error="No image generated.",
        )

    image = images[0]
    result = ocr_page_image(image, engine=engine, lang=lang)
    result.page_number = page_number
    return result


# ── Tesseract ─────────────────────────────────────────────────────────────────


def _configure_tesseract() -> None:
    """Point pytesseract at the Tesseract binary (Windows installs often omit PATH)."""
    import pytesseract  # type: ignore[import]

    from app.core.config import get_settings

    settings = get_settings()
    if settings.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd
        return

    for candidate in (
        Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
        Path("/usr/bin/tesseract"),
        Path("/usr/local/bin/tesseract"),
    ):
        if candidate.is_file():
            pytesseract.pytesseract.tesseract_cmd = str(candidate)
            return


def _tesseract(image: Any, lang: str = "eng", page_number: int = 0) -> OcrResult:
    try:
        import pytesseract  # type: ignore[import]
        from pytesseract import Output  # type: ignore[import]
    except ImportError:
        return OcrResult(
            page_number=page_number,
            text="",
            engine="tesseract",
            success=False,
            error="pytesseract not installed.",
        )

    _configure_tesseract()

    try:
        data = pytesseract.image_to_data(image, lang=lang, output_type=Output.DICT)
        text = pytesseract.image_to_string(image, lang=lang)
        # Compute mean confidence from non-empty word detections
        confidences = [c for c, w in zip(data["conf"], data["text"]) if w.strip() and c != -1]
        mean_conf = (sum(confidences) / len(confidences) / 100.0) if confidences else None
        return OcrResult(
            page_number=page_number, text=text, engine="tesseract", confidence=mean_conf
        )
    except Exception as exc:
        return OcrResult(
            page_number=page_number, text="", engine="tesseract", success=False, error=str(exc)
        )


# ── EasyOCR ───────────────────────────────────────────────────────────────────

_easyocr_reader: Any = None  # module-level cache


def _easyocr(image: Any, lang: str = "eng", page_number: int = 0) -> OcrResult:
    global _easyocr_reader
    try:
        import easyocr  # type: ignore[import]
        import numpy as np  # type: ignore[import]
    except ImportError:
        return OcrResult(
            page_number=page_number,
            text="",
            engine="easyocr",
            success=False,
            error="easyocr not installed.",
        )

    try:
        if _easyocr_reader is None:
            # "en" for English; EasyOCR uses different language codes
            langs = [lang] if lang != "eng" else ["en"]
            _easyocr_reader = easyocr.Reader(langs, gpu=False)

        img_array = np.array(image)
        results = _easyocr_reader.readtext(img_array)
        texts = [r[1] for r in results]
        confidences = [r[2] for r in results]
        full_text = "\n".join(texts)
        mean_conf = (sum(confidences) / len(confidences)) if confidences else None
        return OcrResult(
            page_number=page_number, text=full_text, engine="easyocr", confidence=mean_conf
        )
    except Exception as exc:
        return OcrResult(
            page_number=page_number, text="", engine="easyocr", success=False, error=str(exc)
        )
