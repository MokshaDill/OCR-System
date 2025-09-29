from __future__ import annotations

from typing import Optional

import pytesseract
from PIL import Image
import numpy as np  # type: ignore


def ocr_image_to_text(
    image: np.ndarray | Image.Image,
    tesseract_cmd: Optional[str] = None,
    psm: int = 6,
    oem: int = 3,
    lang: str = "eng",
) -> str:
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    if isinstance(image, Image.Image):
        pil_img = image
    else:
        pil_img = Image.fromarray(image)

    config = f"--psm {psm} --oem {oem}"
    text = pytesseract.image_to_string(pil_img, lang=lang, config=config)
    return text


