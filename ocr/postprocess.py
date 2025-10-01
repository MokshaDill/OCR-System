from __future__ import annotations
import re
from typing import Dict, List, Callable, Optional


def postprocess_results(
    rows: List[Dict[str, str]],
    compute_new_column: Optional[Callable[[Dict[str, str]], str]] = None,
    new_column_name: str = "Summary",
) -> List[Dict[str, str]]:
    """
    Create a new column on final results using either a user-supplied function
    or enhanced default logic.

    Default behavior now:
      - Extract the number part from 'Licenses' (e.g., 'RO05' -> '5', 'R0012' -> '12')
      - Format it as "X times"
      - If 'Licenses' is missing, fallback to combining 'Licenses' and 'Address' if available

    Args:
        rows: List of result dictionaries (already filtered and with columns set).
        compute_new_column: Optional function mapping a row -> string value.
        new_column_name: Name of the added column.

    Returns:
        A new list of rows with the added column added.
    """

    out: List[Dict[str, str]] = []

    for row in rows:
        if compute_new_column is not None:
            # Custom rule provided by user
            value = compute_new_column(row)
        else:
            lic = (row.get("Licenses") or "").strip()
            addr = (row.get("Address") or "").strip()

            # Step 1: Extract text inside parentheses if exists
            match = re.search(r"\(([^)]+)\)", lic)
            code = match.group(1) if match else lic  # e.g., "RO05" or "R0012"

            # Step 2: Extract only digits
            number_match = re.search(r"(\d+)", code)
            if number_match:
                number = int(number_match.group(1))  # remove leading zeros
                value = f"{number} times"
            else:
                # Step 3: Fallback if no number found
                if lic and addr:
                    value = f"{lic} | {addr}"
                else:
                    value = lic or addr

        new_row = dict(row)
        new_row[new_column_name] = value
        out.append(new_row)

    return out
