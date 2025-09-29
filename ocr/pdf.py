from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from PIL import Image
from pdf2image import convert_from_path


def convert_pdf_to_images(
    pdf_path: str | Path,
    dpi: int = 300,
    poppler_path: Optional[str] = None,
) -> List[Image.Image]:
    pdf_path = str(pdf_path)
    images = convert_from_path(pdf_path, dpi=dpi, poppler_path=poppler_path)
    return images


def collect_pdfs_in_folder(folder_path: str | Path) -> List[Path]:
    folder = Path(folder_path)
    unique: dict[str, Path] = {}
    candidates = list(folder.glob("*.pdf")) + list(folder.glob("*.PDF"))
    for p in candidates:
        if p.is_file():
            key = str(p.resolve()).lower()
            unique[key] = p
    return sorted(unique.values(), key=lambda x: x.name.lower())


