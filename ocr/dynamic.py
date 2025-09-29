from __future__ import annotations

import re
from typing import Dict, List, Optional


def generate_smart_patterns(sample_text: str, context_text: str | None = None) -> List[str]:
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

    seen: set[str] = set()
    deduped: List[str] = []
    for p in patterns:
        if p not in seen:
            seen.add(p)
            deduped.append(p)
    return deduped


def extract_dynamic_fields(text: str, field_to_patterns: Dict[str, List[str]]) -> Dict[str, str]:
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


def generate_window_patterns(
    sample_text: str,
    before_words: List[str],
    after_words: List[str],
    max_words_window: int = 3,
    shape_regex: Optional[str] = None,
) -> List[str]:
    if not sample_text:
        return []
    if shape_regex is None:
        shape_regex = infer_token_shape(sample_text)
    join_words = lambda ws: [re.escape(w) for w in ws if len(w) > 1]
    bw = join_words(before_words)[:max_words_window]
    aw = join_words(after_words)[:max_words_window]

    patterns: List[str] = []
    gap = rf"(?:\W+\w+){{0,{max_words_window}}}"

    for w in bw:
        patterns.append(rf"\b{w}\b{gap}\W+({shape_regex})")
    for w in aw:
        patterns.append(rf"({shape_regex})\W+{gap}\b{w}\b")

    seen: set[str] = set()
    out: List[str] = []
    for p in patterns:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def infer_token_shape(sample_text: str) -> str:
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


LICENSE_TYPE_A = r"\b[A-Z]{1,5}[ \-/]*\d{1,10}[ \t]*\(\s*[A-Z0-9/\-\s]{1,24}\s*\)"
LICENSE_TYPE_B = r"\b\d{1,6}/\d{1,6}\s*R\d+\b"


def normalize_text_for_license(text: str) -> str:
    t = text
    t = t.replace("（", "(").replace("）", ")").replace("[", "(").replace("]", ")")
    t = t.upper()
    t = re.sub(r"\s+", " ", t)
    t = t.replace("\u200b", "")

    def _fix_brackets(m: re.Match[str]) -> str:
        inner = m.group(1)
        fixed = re.sub(r"(?<=\d)O(?=\d)", "0", inner)
        return f"({fixed})"

    t = re.sub(r"\(([^)]{1,20})\)", _fix_brackets, t)
    return t


def extract_all_license_numbers(text: str) -> List[str]:
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


def bulk_extract(rows: List[Dict[str, str]], field_to_patterns: Dict[str, List[str]]) -> List[Dict[str, str]]:
    results: List[Dict[str, str]] = []
    for row in rows:
        text = row.get("Text", "") or ""
        extracted = extract_dynamic_fields(text, field_to_patterns)
        out_row: Dict[str, str] = {"File Name": row.get("File Name", "")}
        out_row.update(extracted)
        results.append(out_row)
    return results


def bulk_extract_licenses(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for r in rows:
        text = r.get("Text", "") or ""
        licenses = extract_all_license_numbers(text)
        out.append({
            "File Name": r.get("File Name", ""),
            "Licenses": "; ".join(licenses),
        })
    return out


