from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional

from .models import ExtractionResult
from .pdf import convert_pdf_to_images
from .preprocess import preprocess_image
from .ocr_engine import ocr_image_to_text
from .extract import extract_fields, extract_address_between_markers, extract_date_range


def ocr_pdf_to_text(
    pdf_path: str | Path,
    tesseract_cmd: Optional[str] = None,
    poppler_path: Optional[str] = None,
    on_page: Optional[Callable[[str, int, int], None]] = None,
    log: Optional[Callable[[str], None]] = None,
) -> str:
    if log:
        log(f"Converting PDF to images: {Path(pdf_path).name}")
    pil_pages = convert_pdf_to_images(pdf_path, dpi=300, poppler_path=poppler_path)

    total = len(pil_pages)
    all_text_parts: List[str] = []
    for idx, pil_img in enumerate(pil_pages, start=1):
        if log:
            log(f"Preprocessing page {idx} of {total} for {Path(pdf_path).name}")
        pre = preprocess_image(pil_img)
        if log:
            log(f"Running OCR on page {idx} of {total} for {Path(pdf_path).name}")
        page_text = ocr_image_to_text(pre, tesseract_cmd=tesseract_cmd)
        all_text_parts.append(page_text)
        if on_page:
            try:
                on_page(page_text, idx, total)
            except Exception:
                pass
    return "\n".join(all_text_parts)


def process_pdf_file(
    pdf_path: str | Path,
    tesseract_cmd: Optional[str] = None,
    poppler_path: Optional[str] = None,
    log: Optional[Callable[[str], None]] = None,
    patterns: Optional[Dict[str, Iterable[str]]] = None,
) -> ExtractionResult:
    file_name = Path(pdf_path).name
    try:
        if log:
            log(f"Converting PDF to images: {file_name}")
        pil_pages = convert_pdf_to_images(pdf_path, dpi=300, poppler_path=poppler_path)

        all_text_parts: List[str] = []
        for idx, pil_img in enumerate(pil_pages, start=1):
            if log:
                log(f"Preprocessing page {idx} of {file_name}")
            pre = preprocess_image(pil_img)
            if log:
                log(f"Running OCR on page {idx} of {file_name}")
            txt = ocr_image_to_text(pre, tesseract_cmd=tesseract_cmd)
            all_text_parts.append(txt)

        full_text = "\n".join(all_text_parts)
        license_id, date, reference_id = extract_fields(full_text, patterns=patterns)
        address = extract_address_between_markers(full_text)
        start_date, end_date = extract_date_range(full_text)

        notes = None
        if not any([license_id, date, reference_id]):
            notes = "No patterns matched"

        return ExtractionResult(
            file_name=file_name,
            license_id=license_id,
            date=date,
            reference_id=reference_id,
            address=address,
            start_date=start_date,
            end_date=end_date,
            notes=notes,
        )
    except Exception as exc:  # noqa: BLE001
        return ExtractionResult(
            file_name=file_name,
            license_id=None,
            date=None,
            reference_id=None,
            notes=f"Error: {exc}",
        )


