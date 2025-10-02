from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional, Tuple
import re


def compile_patterns(patterns: Dict[str, Iterable[str]]) -> Dict[str, List[re.Pattern[str]]]:
    compiled: Dict[str, List[re.Pattern[str]]] = {}
    for key, exprs in patterns.items():
        compiled[key] = [re.compile(expr, flags=re.IGNORECASE) for expr in exprs]
    return compiled


def extract_first_match(text: str, regex_list: Iterable[re.Pattern[str]]) -> Optional[str]:
    for rgx in regex_list:
        m = rgx.search(text)
        if m:
            if m.lastindex:
                return m.group(1)
            return m.group(0)
    return None


def extract_fields(
    text: str,
    patterns: Optional[Dict[str, Iterable[str]]] = None,
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    from .patterns import DEFAULT_PATTERNS

    to_use = compile_patterns(patterns or DEFAULT_PATTERNS)

    license_id = extract_first_match(text, to_use.get("license_id", []))
    date = extract_first_match(text, to_use.get("date", []))
    reference_id = extract_first_match(text, to_use.get("reference_id", []))

    return license_id, date, reference_id


import re
from typing import Optional

def extract_address_between_markers(text: str) -> Optional[str]:
    """
    Extract address associated with telecommunication tower references.
    Handles variants like:
      - 'Telecommunication Tower at ... of Dialog Axiata PLC'
      - 'Transmission Tower Providing Facilities for Telecommunication at ... situated ...'
      - '(Telecommunication tower), ... situated ...'
    """
    if not text:
        return None

    t = re.sub(r"[\u200b\r]+", " ", text)

    pattern = re.compile(
        r"""
        (?:Telecommunication|Transmission)[\w\s,()/-]*?          # tower-related phrase
        \s+at\s+                                                # 'at' introducing address
        (.*?)                                                   # <-- capture address text
        (?=                                                     # stop capturing at these keywords
            \s+of\s+Dialog|
            \s*situated|
            \s*within|
            \s*under|
            $                                                  # or end of string
        )
        """,
        flags=re.IGNORECASE | re.DOTALL | re.VERBOSE,
    )

    match = pattern.search(t)
    if match:
        addr = match.group(1)
        addr = re.sub(r"\s{2,}", " ", addr)
        addr = addr.strip(" ,.;:-")
        return addr

    return None


import re
from typing import Tuple, Optional

import re
from typing import Tuple, Optional

def extract_date_range(text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract date ranges from text, handling:
    - Numeric: 12.02.2025 or 21-32-2024 (even if invalid month/day)
    - Textual: 10th May 2025
    - OCR variant: 15" May 2025
    Returns normalized numeric format: d.m.yyyy
    """
    if not text:
        return None, None

    t = re.sub(r"[\u200b\r]+", " ", text)

    # --- Numeric date pattern ---
    day = r"\d{1,2}"
    mon = r"\d{1,2}"
    year = r"\d{4}"
    sep = r"\s*[\.\-]\s*" 
    numeric_date = rf"{day}{sep}{mon}{sep}{year}"

    # --- Textual date pattern (ordinal or OCR double-quote) ---
    day_suffix = r'(?:st|nd|rd|th|"|”)?'  # handle OCR quotes or ordinal
    day_text = rf"\d{{1,2}}{day_suffix}"
    month_text = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|" \
                 r"January|February|March|April|May|June|July|August|September|October|November|December)"
    textual_date = rf"{day_text}\s*{month_text}\s+{year}"

    # Combine patterns
    date_pat = rf"(?:{numeric_date}|{textual_date})"

    # Match "date to date"
    rgx = re.compile(
        rf"({date_pat}).{{0,40}}?\bto\b.{{0,40}}?({date_pat})",
        re.IGNORECASE | re.DOTALL
    )

    m = rgx.search(t)
    if not m:
        return None, None

    def _normalize_date(s: str) -> str:
        # Remove ordinal suffixes or OCR quotes
        s = re.sub(r'(\d{1,2})(st|nd|rd|th|"|”)', r'\1', s, flags=re.IGNORECASE)
        # Convert textual month to number
        month_map = {
            'jan':1,'feb':2,'mar':3,'apr':4,'may':5,'jun':6,
            'jul':7,'aug':8,'sep':9,'oct':10,'nov':11,'dec':12
        }
        def replace_month(mo):
            m = mo.group(0).lower()[:3]
            return str(month_map[m])
        s = re.sub(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|'
                   r'January|February|March|April|May|June|July|August|September|October|November|December)',
                   replace_month, s, flags=re.IGNORECASE)
        # Replace separators/spaces with dot
        s = re.sub(r"[\s\.\-]+", ".", s)
        return s

    start, end = _normalize_date(m.group(1)), _normalize_date(m.group(2))

    return start, end

