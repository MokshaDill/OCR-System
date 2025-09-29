from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ExtractionResult:
    file_name: str
    license_id: Optional[str]
    date: Optional[str]
    reference_id: Optional[str]
    address: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    notes: Optional[str] = None


