"""
OCR and extraction utilities for the OCR System project.

Responsibilities:
- Convert PDF pages to images (via pdf2image/poppler)
- Preprocess images for OCR (OpenCV)
- Run OCR using Tesseract (pytesseract) with configurable tesseract_cmd
- Extract fields using configurable regex patterns

These utilities are designed to be imported by the GUI entry point in main.py.
"""

from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Tuple
import csv
import os

import cv2  # type: ignore
import numpy as np  # type: ignore
from PIL import Image
from pdf2image import convert_from_path
import pytesseract


# ------------------------- Data Models -------------------------


@dataclass
class ExtractionResult:
    file_name: str
    license_id: Optional[str]
    date: Optional[str]
    reference_id: Optional[str]
    notes: Optional[str] = None


# ------------------------- PDF to Images -------------------------


def convert_pdf_to_images(
    pdf_path: str | Path,
    dpi: int = 300,
    poppler_path: Optional[str] = None,
) -> List[Image.Image]:
    """
    Convert a PDF into a list of PIL Images (one per page).

    On Windows, poppler must be installed and poppler_path should point to the
    "bin" directory, e.g., C:\\path\\to\\poppler-xx\\Library\\bin or ...\\poppler-xx\\bin
    """

    pdf_path = str(pdf_path)
    images = convert_from_path(pdf_path, dpi=dpi, poppler_path=poppler_path)
    return images


# ------------------------- Image Preprocessing -------------------------


def preprocess_image(pil_image: Image.Image) -> np.ndarray:
    """
    Basic preprocessing to improve OCR:
    - Convert to grayscale
    - Apply bilateral filter (denoise while keeping edges)
    - Adaptive threshold to increase contrast
    - Optional morphology to clean noise
    Returns OpenCV image (numpy array).
    """

    image = np.array(pil_image)
    if len(image.shape) == 3 and image.shape[2] == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    else:
        gray = image

    denoised = cv2.bilateralFilter(gray, d=7, sigmaColor=75, sigmaSpace=75)

    # Attempt deskew using Hough line angle estimation
    try:
        edges = cv2.Canny(denoised, threshold1=50, threshold2=150, apertureSize=3)
        lines = cv2.HoughLines(edges, 1, np.pi / 180.0, 120)
        if lines is not None and len(lines) > 0:
            angles: List[float] = []
            for line in lines[:100]:
                rho, theta = line[0]
                angle_deg = (theta * 180.0 / np.pi) - 90.0
                # Normalize to [-45, 45]
                while angle_deg <= -45.0:
                    angle_deg += 90.0
                while angle_deg > 45.0:
                    angle_deg -= 90.0
                angles.append(angle_deg)
            if angles:
                median_angle = float(np.median(angles))
                # Clip to avoid wild rotations
                median_angle = float(np.clip(median_angle, -10.0, 10.0))
                if abs(median_angle) > 0.5:
                    (h, w) = denoised.shape[:2]
                    center = (w // 2, h // 2)
                    rot_mat = cv2.getRotationMatrix2D(center, median_angle, 1.0)
                    denoised = cv2.warpAffine(
                        denoised,
                        rot_mat,
                        (w, h),
                        flags=cv2.INTER_CUBIC,
                        borderMode=cv2.BORDER_REPLICATE,
                    )
    except Exception:
        # If deskew fails, continue with the original denoised image
        pass

    thresh = cv2.adaptiveThreshold(
        denoised,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        35,
        11,
    )

    kernel = np.ones((1, 1), np.uint8)
    opened = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
    return opened


# ------------------------- OCR -------------------------


def ocr_image_to_text(
    image: np.ndarray | Image.Image,
    tesseract_cmd: Optional[str] = None,
    psm: int = 6,
    oem: int = 3,
    lang: str = "eng",
) -> str:
    """
    Run OCR on an image using pytesseract.

    - tesseract_cmd: path to tesseract executable (e.g., C:\\Program Files\\Tesseract-OCR\\tesseract.exe)
    - psm: page segmentation mode (6: assume a single uniform block of text)
    - oem: OCR engine mode (3: default, based on what is available)
    - lang: language(s)
    """

    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    if isinstance(image, Image.Image):
        pil_img = image
    else:
        pil_img = Image.fromarray(image)

    config = f"--psm {psm} --oem {oem}"
    text = pytesseract.image_to_string(pil_img, lang=lang, config=config)
    return text


# ------------------------- Extraction -------------------------


DEFAULT_PATTERNS: Dict[str, Iterable[str]] = {
    # License ID: broad but controlled: 6-20 uppercase letters/digits, or common prefixes
    "license_id": [
        r"\bLIC[-_\s]?\d{3,}\b",
        r"\bLicense\s*ID[:#-]*\s*([A-Z0-9]{6,20})\b",
        r"\b[A-Z0-9]{6,20}\b",
    ],
    # Dates: dd/mm/yyyy, dd-mm-yyyy, yyyy/mm/dd, yyyy-mm-dd
    "date": [
        r"\b\d{2}[\/-]\d{2}[\/-]\d{4}\b",
        r"\b\d{4}[\/-]\d{2}[\/-]\d{2}\b",
    ],
    # Reference numbers: generic 4-10 alnum, including labeled variants
    "reference_id": [
        r"\bREF[-_\s]*([A-Z0-9]{4,10})\b",
        r"\b(?:Reference|Ref)[\s:#-]*([A-Z0-9-]{4,10})\b",
        r"\b[A-Z0-9]{4,10}\b",
    ],
}


def compile_patterns(patterns: Dict[str, Iterable[str]]) -> Dict[str, List[re.Pattern[str]]]:
    compiled: Dict[str, List[re.Pattern[str]]] = {}
    for key, exprs in patterns.items():
        compiled[key] = [re.compile(expr, flags=re.IGNORECASE) for expr in exprs]
    return compiled


def extract_first_match(text: str, regex_list: Iterable[re.Pattern[str]]) -> Optional[str]:
    for rgx in regex_list:
        m = rgx.search(text)
        if m:
            # If there is a capturing group, prefer it; else the full match
            if m.lastindex:
                return m.group(1)
            return m.group(0)
    return None


def extract_fields(
    text: str,
    patterns: Optional[Dict[str, Iterable[str]]] = None,
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Return (license_id, date, reference_id)
    """

    to_use = compile_patterns(patterns or DEFAULT_PATTERNS)

    license_id = extract_first_match(text, to_use["license_id"]) if "license_id" in to_use else None
    date = extract_first_match(text, to_use["date"]) if "date" in to_use else None
    reference_id = extract_first_match(text, to_use["reference_id"]) if "reference_id" in to_use else None

    return license_id, date, reference_id


# ------------------------- Smart patterns and dynamic extraction -------------------------


def generate_smart_patterns(sample_text: str, context_text: str | None = None) -> List[str]:
    """
    Generate a small set of regex patterns based on a user-selected sample and its nearby context.
    The first pattern is the exact escaped sample. Others are heuristics for dates, alphanumerics, etc.
    """
    if not sample_text:
        return []

    patterns: List[str] = []
    patterns.append(re.escape(sample_text))

    try:
        if re.match(r"\d{1,2}[/-]\d{1,2}[/-]\d{4}", sample_text):
            patterns.extend([
                r"\d{1,2}[/-]\d{1,2}[/-]\d{4}",
                r"\d{4}[/-]\d{1,2}[/-]\d{1,2}",
                r"\d{1,2}\s+\d{1,2}\s+\d{4}",
            ])
        elif re.match(r"[A-Z]{2,}\d+", sample_text):
            patterns.extend([
                r"[A-Z]{2,}\d+",
                r"[A-Z]{2,}[-_\s]?\d+",
                r"[A-Z]*\d+",
            ])
        elif re.match(r"\d+", sample_text):
            patterns.extend([
                r"\d+",
                r"[A-Z]*\d+",
                r"\d+[A-Z]*",
            ])
    except Exception:
        pass

    if context_text:
        try:
            context_words = context_text.split()
            for word in context_words[:3]:
                if len(word) > 2:
                    patterns.append(fr"\b{re.escape(word)}.*?{re.escape(sample_text)}")
        except Exception:
            pass

    # De-dupe while preserving order
    seen: set[str] = set()
    deduped: List[str] = []
    for p in patterns:
        if p not in seen:
            seen.add(p)
            deduped.append(p)
    return deduped


def extract_dynamic_fields(text: str, field_to_patterns: Dict[str, List[str]]) -> Dict[str, str]:
    """
    For each field, try its regex list in order and return the first match (group1 if available).
    """
    out: Dict[str, str] = {}
    for field_name, patterns in field_to_patterns.items():
        value: Optional[str] = None
        for raw in patterns:
            try:
                rgx = re.compile(raw, flags=re.IGNORECASE)
                m = rgx.search(text)
                if m:
                    value = m.group(1) if m.lastindex else m.group(0)
                    break
            except Exception:
                continue
        out[field_name] = value or ""
    return out


def bulk_extract(rows: List[Dict[str, str]], field_to_patterns: Dict[str, List[str]]) -> List[Dict[str, str]]:
    """
    rows: list of {"File Name": str, "Text": str}
    Returns new rows with extracted fields alongside file name.
    """
    results: List[Dict[str, str]] = []
    for row in rows:
        text = row.get("Text", "") or ""
        extracted = extract_dynamic_fields(text, field_to_patterns)
        out_row: Dict[str, str] = {"File Name": row.get("File Name", "")}
        out_row.update(extracted)
        results.append(out_row)
    return results


def generate_window_patterns(
    sample_text: str,
    before_words: List[str],
    after_words: List[str],
    max_words_window: int = 3,
    shape_regex: Optional[str] = None,
) -> List[str]:
    """
    Build regex patterns that constrain the selection to appear within a window
    of up to `max_words_window` words after any of the `before_words`, or within
    `max_words_window` words before any of the `after_words`.

    The patterns keep the selected value as the primary capture group when possible.
    """
    if not sample_text:
        return []
    # Infer a generic shape for the target token so we don't require exact match
    if shape_regex is None:
        shape_regex = infer_token_shape(sample_text)
    join_words = lambda ws: [re.escape(w) for w in ws if len(w) > 1]
    bw = join_words(before_words)[:max_words_window]
    aw = join_words(after_words)[:max_words_window]

    patterns: List[str] = []

    # Between words window uses up to N intermediate words: (?:\W+\w+){0,N}
    gap = rf"(?:\W+\w+){{0,{max_words_window}}}"

    for w in bw:
        # BEFORE words then capture a token matching the shape
        patterns.append(rf"\b{w}\b{gap}\W+({shape_regex})")
    for w in aw:
        # Capture token followed by AFTER words
        patterns.append(rf"({shape_regex})\W+{gap}\b{w}\b")

    # De-duplicate
    seen: set[str] = set()
    out: List[str] = []
    for p in patterns:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def infer_token_shape(sample_text: str) -> str:
    """
    Infer a permissive token shape from a sample string without fixing exact characters.
    The result is a regex fragment suitable for a single capturing group.
    """
    s = sample_text.strip()
    if not s:
        return r"\S{2,20}"
    has_alpha = any(c.isalpha() for c in s)
    has_digit = any(c.isdigit() for c in s)
    min_len = max(2, min(4, len(s)))
    max_len = min(40, max(len(s) + 6, 8))
    if has_alpha and has_digit:
        cls = r"[A-Za-z0-9/()\-\s]"
    elif has_digit and not has_alpha:
        cls = r"[0-9/()\-\s]"
    else:
        cls = r"[A-Za-z/()\-\s]"
    return rf"{cls}{{{min_len},{max_len}}}"


# ------------------------- License Patterns (Type A & B) -------------------------

# Type A: Letters + number + bracketed token
# - Allow multiple spaces
# - Allow hyphens, slashes and spaces inside brackets
# - Allow slightly longer lengths to accommodate OCR noise
LICENSE_TYPE_A = r"\bB\s\d{5}\(R[0-9O]\)\b" ##\b[A-Z]{1,4}\s*\d{1,9}\s*\(\s*[A-Z0-9/\-\s]{1,20}\s*\)\b
# Type B: number/number with REQUIRED trailing R+digits (exclude plain dates)
LICENSE_TYPE_B = r"\b\d{1,6}/\d{1,6}\s*R\d+\b"

LICENSE_REGEXES: List[re.Pattern[str]] = [
    re.compile(LICENSE_TYPE_A, flags=re.IGNORECASE),
    re.compile(LICENSE_TYPE_B, flags=re.IGNORECASE),
]


def extract_all_license_numbers(text: str) -> List[str]:
    """
    Find license numbers matching Type A or Type B.
    Only one structure is returned per text: prefer Type A; else Type B.
    """
    txt = normalize_text_for_license(text or "")
    type_a: List[str] = []
    type_b: List[str] = []
    seen_a: set[str] = set()
    seen_b: set[str] = set()

    for m in re.finditer(LICENSE_TYPE_A, txt, flags=re.IGNORECASE):
        val = m.group(0).strip()
        key = val.upper()
        if key not in seen_a:
            seen_a.add(key)
            type_a.append(val)

    for m in re.finditer(LICENSE_TYPE_B, txt, flags=re.IGNORECASE):
        val = m.group(0).strip()
        key = val.upper()
        if key not in seen_b:
            seen_b.add(key)
            type_b.append(val)

    return type_a if type_a else type_b


def normalize_text_for_license(text: str) -> str:
    """
    Normalize OCR quirks to improve license matching:
    - Unify unicode parentheses/brackets to ()
    - Collapse multiple spaces
    - Replace common OCR confusions (O<->0) inside bracket tokens
    - Uppercase for consistent matching
    """
    t = text
    # Normalize brackets (full-width and square to normal parentheses)
    t = t.replace("（", "(").replace("）", ")").replace("[", "(").replace("]", ")")
    # Uppercase
    t = t.upper()
    # Collapse whitespace
    t = re.sub(r"\s+", " ", t)
    # Remove zero-width spaces
    t = t.replace("\u200b", "")
    # Light fix: inside brackets, allow O/0 confusion by mapping letter O to 0 when surrounded by digits
    def _fix_brackets(m: re.Match[str]) -> str:
        inner = m.group(1)
        fixed = re.sub(r"(?<=\d)O(?=\d)", "0", inner)
        return f"({fixed})"
    t = re.sub(r"\(([^)]{1,20})\)", _fix_brackets, t)
    return t


def bulk_extract_licenses(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    For each row {"File Name":, "Text":}, extract all licenses (Type A/B).
    """
    out: List[Dict[str, str]] = []
    for r in rows:
        text = r.get("Text", "") or ""
        licenses = extract_all_license_numbers(text)
        out.append({
            "File Name": r.get("File Name", ""),
            "Licenses": "; ".join(licenses),
        })
    return out


# ------------------------- High-level PDF processor -------------------------


def ocr_pdf_to_text(
    pdf_path: str | Path,
    tesseract_cmd: Optional[str] = None,
    poppler_path: Optional[str] = None,
    on_page: Optional[Callable[[str, int, int], None]] = None,
    log: Optional[Callable[[str], None]] = None,
) -> str:
    """
    OCR a PDF and return full text. Optional on_page callback receives
    (page_text, page_index starting at 1, total_pages) to enable streaming UI.
    """
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
                # UI callback failures should not stop OCR
                pass
    return "\n".join(all_text_parts)


def process_pdf_file(
    pdf_path: str | Path,
    tesseract_cmd: Optional[str] = None,
    poppler_path: Optional[str] = None,
    log: Optional[Callable[[str], None]] = None,
    patterns: Optional[Dict[str, Iterable[str]]] = None,
) -> ExtractionResult:
    """
    Process a single PDF: render pages to images, OCR them, extract fields.
    Returns an ExtractionResult with the first matches found across pages.
    """

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

        notes = None
        if not any([license_id, date, reference_id]):
            notes = "No patterns matched"

        return ExtractionResult(
            file_name=file_name,
            license_id=license_id,
            date=date,
            reference_id=reference_id,
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


def collect_pdfs_in_folder(folder_path: str | Path) -> List[Path]:
    folder = Path(folder_path)
    # Deduplicate by normalized lowercase absolute path to avoid double counting on Windows
    unique: dict[str, Path] = {}
    candidates = list(folder.glob("*.pdf")) + list(folder.glob("*.PDF"))
    for p in candidates:
        if p.is_file():
            key = str(p.resolve()).lower()
            unique[key] = p
    return sorted(unique.values(), key=lambda x: x.name.lower())


# ------------------------- CSV helpers -------------------------


def append_rows_csv(rows: List[Dict[str, str]], out_file: str, columns: List[str]) -> None:
    """
    Append rows to a CSV, writing header if the file does not exist.
    Uses the built-in csv module to avoid heavy dependencies.
    """
    file_exists = os.path.exists(out_file)
    with open(out_file, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        if not file_exists:
            writer.writeheader()
        for row in rows:
            # Only keep known columns
            clean = {col: row.get(col, "") for col in columns}
            writer.writerow(clean)



