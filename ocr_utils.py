"""
Compatibility shim that re-exports the modular OCR package for existing imports.

Prefer importing from the `ocr` package directly going forward, e.g.:
    from ocr import process_pdf_file, collect_pdfs_in_folder
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from ocr import (
    ExtractionResult,
    convert_pdf_to_images,
    preprocess_image,
    ocr_image_to_text,
)
from ocr import (
    DEFAULT_PATTERNS,
    compile_patterns,
    extract_first_match,
    extract_fields,
)
from ocr import (
    ocr_pdf_to_text,
    process_pdf_file,
    collect_pdfs_in_folder,
)
from ocr import append_rows_csv
from ocr import (
    generate_smart_patterns,
    extract_dynamic_fields,
    generate_window_patterns,
    infer_token_shape,
    normalize_text_for_license,
    extract_all_license_numbers,
    bulk_extract,
    bulk_extract_licenses,
    extract_address_between_markers,
    extract_date_range,
)

__all__ = [
    "ExtractionResult",
    "convert_pdf_to_images",
    "preprocess_image",
    "ocr_image_to_text",
    "DEFAULT_PATTERNS",
    "compile_patterns",
    "extract_first_match",
    "extract_fields",
    "ocr_pdf_to_text",
    "process_pdf_file",
    "collect_pdfs_in_folder",
    "append_rows_csv",
    "generate_smart_patterns",
    "extract_dynamic_fields",
    "generate_window_patterns",
    "infer_token_shape",
    "normalize_text_for_license",
    "extract_all_license_numbers",
    "bulk_extract",
    "bulk_extract_licenses",
    "extract_address_between_markers",
    "extract_date_range",
]
