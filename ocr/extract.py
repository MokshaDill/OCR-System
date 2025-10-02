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


def extract_date_range(text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Find date ranges like '1.12.2024 to 24.11.2025' or '12-02-2025 to 23-11-2026',
    allowing noisy dots/spaces/hyphens.
    Returns (start_date, end_date) normalized with single dots (d.m.yyyy).
    """
    if not text:
        return None, None

    t = re.sub(r"[\u200b\r]+", " ", text)
    # day and month may contain optional spaces and optional dot or hyphen
    day = r"\d{1,2}"
    mon = r"\d{1,2}"
    year = r"\d{4}"
    sep = r"\s*[\.\-]\s*"     # <-- allow . or - between day/month/year
    date_pat = rf"{day}{sep}{mon}{sep}{year}"

    rgx = re.compile(
        rf"({date_pat}).{{0,40}}?\bto\b.{{0,40}}?({date_pat})",
        re.IGNORECASE | re.DOTALL
    )

    m = rgx.search(t)
    if not m:
        return None, None

    def _norm(s: str) -> str:
        s = re.sub(r"\s*[\.\-]\s*", ".", s)  # normalize both . and - into .
        s = re.sub(r"\s+", "", s)
        return s

    return _norm(m.group(1)), _norm(m.group(2))


