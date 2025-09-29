from __future__ import annotations

from typing import List

import cv2  # type: ignore
import numpy as np  # type: ignore
from PIL import Image


def preprocess_image(pil_image: Image.Image) -> np.ndarray:
    image = np.array(pil_image)
    if len(image.shape) == 3 and image.shape[2] == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    else:
        gray = image

    denoised = cv2.bilateralFilter(gray, d=7, sigmaColor=75, sigmaSpace=75)

    try:
        edges = cv2.Canny(denoised, threshold1=50, threshold2=150, apertureSize=3)
        lines = cv2.HoughLines(edges, 1, np.pi / 180.0, 120)
        if lines is not None and len(lines) > 0:
            angles: List[float] = []
            for line in lines[:100]:
                rho, theta = line[0]
                angle_deg = (theta * 180.0 / np.pi) - 90.0
                while angle_deg <= -45.0:
                    angle_deg += 90.0
                while angle_deg > 45.0:
                    angle_deg -= 90.0
                angles.append(angle_deg)
            if angles:
                median_angle = float(np.median(angles))
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


