from __future__ import annotations

import csv
import os
from typing import Dict, List


def append_rows_csv(rows: List[Dict[str, str]], out_file: str, columns: List[str]) -> None:
    file_exists = os.path.exists(out_file)
    with open(out_file, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        if not file_exists:
            writer.writeheader()
        for row in rows:
            clean = {col: row.get(col, "") for col in columns}
            writer.writerow(clean)


