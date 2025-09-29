from __future__ import annotations

from typing import Dict, Iterable


DEFAULT_PATTERNS: Dict[str, Iterable[str]] = {
    "license_id": [
        r"\bLIC[-_\s]?\d{3,}\b",
        r"\bLicense\s*ID[:#-]*\s*([A-Z0-9]{6,20})\b",
        r"\b[A-Z0-9]{6,20}\b",
    ],
    "date": [
        r"\b\d{2}[\/-]\d{2}[\/-]\d{4}\b",
        r"\b\d{4}[\/-]\d{2}[\/-]\d{2}\b",
    ],
    "reference_id": [
        r"\bREF[-_\s]*([A-Z0-9]{4,10})\b",
        r"\b(?:Reference|Ref)[\s:#-]*([A-Z0-9-]{4,10})\b",
        r"\b[A-Z0-9]{4,10}\b",
    ],
}


