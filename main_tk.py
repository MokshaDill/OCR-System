from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import List, Optional, Dict
import re

import pandas as pd  # type: ignore
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk

from ocr_utils import (
    collect_pdfs_in_folder,
    ocr_pdf_to_text,
    append_rows_csv,
    generate_smart_patterns,
    bulk_extract,
    generate_window_patterns,
    bulk_extract_licenses,
)
"""Tkinter GUI for OCR PDF Extractor (regex-only version)."""


APP_TITLE = "OCR PDF Extractor (Tkinter)"


def resource_path(relative_path: str) -> str:
    try:
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def guess_tesseract_path() -> str:
    candidates = [
        resource_path(os.path.join("tesseract", "tesseract.exe")),
        os.environ.get("TESSERACT_CMD", ""),
        r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe",
        r"C:\\Program Files (x86)\\Tesseract-OCR\\tesseract.exe",
        os.path.join(os.path.expanduser("~"), "AppData", "Local", "Programs", "Tesseract-OCR", "tesseract.exe"),
    ]
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    return ""


def guess_poppler_bin() -> str:
    env = os.environ.get("POPPLER_BIN", "")
    if env and os.path.isdir(env):
        return env
    # Check bundled poppler within app resources for packaged .exe
    try:
        bundled = resource_path(os.path.join("poppler-25.07.0", "Library", "bin"))
        if os.path.isdir(bundled):
            return bundled
        bundled2 = resource_path(os.path.join("poppler", "Library", "bin"))
        if os.path.isdir(bundled2):
            return bundled2
        bundled3 = resource_path(os.path.join("poppler-25.07.0", "bin"))
        if os.path.isdir(bundled3):
            return bundled3
    except Exception:
        pass
    base_candidates = [r"C:\\Tools", r"C:\\Program Files"]
    for base in base_candidates:
        if not os.path.isdir(base):
            continue
        try:
            for name in os.listdir(base):
                if name.lower().startswith("poppler"):
                    bin_path = os.path.join(base, name, "Library", "bin")
                    if os.path.isdir(bin_path):
                        return bin_path
                    bin_path2 = os.path.join(base, name, "bin")
                    if os.path.isdir(bin_path2):
                        return bin_path2
        except Exception:
            pass
    return ""


def validate_paths(in_folder: str, out_file: str) -> Optional[str]:
    if not in_folder:
        return "Please select an input folder."
    if not Path(in_folder).exists():
        return "Input folder does not exist."
    if not out_file:
        return "Please select an output file (CSV or XLSX)."
    out_dir = Path(out_file).parent
    if not out_dir.exists():
        return "Output directory does not exist."
    if not (out_file.lower().endswith(".csv") or out_file.lower().endswith(".xlsx")):
        return "Output file must be .csv or .xlsx"
    return None


def export_results(rows: List[dict], out_file: str, columns: List[str]) -> None:
    df = pd.DataFrame(rows, columns=columns)
    if out_file.lower().endswith(".csv"):
        df.to_csv(out_file, index=False, encoding="utf-8")
    else:
        with pd.ExcelWriter(out_file, engine="openpyxl") as writer:  # type: ignore
            df.to_excel(writer, index=False, sheet_name="Results")


    # CSV appends handled by backend helper append_rows_csv


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        # Set window icon from PNG (resource-aware). Fallback silently if missing.
        try:
            icon_path = resource_path("8005785.png")
            if os.path.isfile(icon_path):
                self.icon_img = tk.PhotoImage(file=icon_path)
                self.iconphoto(True, self.icon_img)
        except Exception:
            pass

        self.in_folder_var = tk.StringVar(value="")
        self.out_file_var = tk.StringVar(value="")
        # Configure bundled runtimes if present
        try:
            bundled_tess = resource_path(os.path.join("tesseract", "tesseract.exe"))
            if os.path.isfile(bundled_tess):
                os.environ["TESSERACT_CMD"] = bundled_tess
                tessdata_path = resource_path(os.path.join("tesseract", "tessdata"))
                if os.path.isdir(tessdata_path):
                    os.environ["TESSDATA_PREFIX"] = tessdata_path
                # Ensure PATH includes bundled dir
                os.environ["PATH"] = os.path.dirname(bundled_tess) + os.pathsep + os.environ.get("PATH", "")
        except Exception:
            pass
        try:
            bundled_poppler = guess_poppler_bin()
            if bundled_poppler:
                os.environ["POPPLER_BIN"] = bundled_poppler
                os.environ["PATH"] = bundled_poppler + os.pathsep + os.environ.get("PATH", "")
        except Exception:
            pass
        self.tess_path_var = tk.StringVar(value=guess_tesseract_path())
        self.poppler_var = tk.StringVar(value=guess_poppler_bin())

        # User-defined field samples (from preview selections)
        self.sel_license = ""
        self.sel_date = ""
        self.sel_ref = ""
        
        # Smart pattern context (background text around selection)
        self.license_context = ""
        self.date_context = ""
        self.ref_context = ""

        # Persisted selection patterns for final extract
        self.field_to_patterns: Dict[str, List[str]] = {}

        self._build_widgets()

    def _build_widgets(self) -> None:
        pad = {"padx": 6, "pady": 4}

        tk.Label(self, text="Input Folder (PDFs):", width=22, anchor="w").grid(row=0, column=0, **pad)
        tk.Entry(self, textvariable=self.in_folder_var, width=60).grid(row=0, column=1, **pad)
        tk.Button(self, text="Browse", command=self._choose_in_folder).grid(row=0, column=2, **pad)

        tk.Label(self, text="Output File (CSV/XLSX):", width=22, anchor="w").grid(row=1, column=0, **pad)
        tk.Entry(self, textvariable=self.out_file_var, width=60).grid(row=1, column=1, **pad)
        tk.Button(self, text="Save As", command=self._choose_out_file).grid(row=1, column=2, **pad)

        tk.Label(self, text="Tesseract Path:", width=22, anchor="w").grid(row=2, column=0, **pad)
        tk.Entry(self, textvariable=self.tess_path_var, width=60).grid(row=2, column=1, **pad)
        tk.Button(self, text="Browse", command=self._choose_tesseract).grid(row=2, column=2, **pad)

        tk.Label(self, text="Poppler bin Folder:", width=22, anchor="w").grid(row=3, column=0, **pad)
        tk.Entry(self, textvariable=self.poppler_var, width=60).grid(row=3, column=1, **pad)
        tk.Button(self, text="Browse", command=self._choose_poppler).grid(row=3, column=2, **pad)

        # Extraction method removed; regex is always used

        # Remove regex/custom field UI; we'll show a live OCR viewer instead
        self.viewer_frame = tk.Frame(self)
        self.viewer_frame.grid(row=5, column=0, columnspan=3, sticky="nsew", padx=6, pady=2)
        self.grid_rowconfigure(5, weight=1)
        tk.Label(self.viewer_frame, text="Current PDF:", width=22, anchor="w").grid(row=0, column=0, sticky="w")
        self.current_file_var = tk.StringVar(value="(none)")
        tk.Label(self.viewer_frame, textvariable=self.current_file_var, anchor="w").grid(row=0, column=1, columnspan=2, sticky="w")
        self.ocr_text_view = tk.Text(self.viewer_frame, width=100, height=18)
        self.ocr_text_view.grid(row=1, column=0, columnspan=3, sticky="nsew")
        self.viewer_frame.grid_rowconfigure(1, weight=1)
        self.viewer_frame.grid_columnconfigure(1, weight=1)

        # Step controls
        tk.Button(self, text="Process All", command=lambda: self._run(run_all=True), bg="#0078D4", fg="white").grid(row=6, column=0, sticky="w", **pad)
        tk.Button(self, text="Select Fields (First PDF)", command=self._open_extractor).grid(row=6, column=1, sticky="w", **pad)
        tk.Button(self, text="Final Extract", command=self._final_extract, bg="#0E7C86", fg="white").grid(row=6, column=2, sticky="e", **pad)

        # Legacy controls removed (simplified flow)

        # Progress
        self.status_var = tk.StringVar(value="Idle")
        tk.Label(self, textvariable=self.status_var, anchor="w").grid(row=8, column=0, columnspan=2, sticky="w", **pad)
        self.progress = ttk.Progressbar(self, orient="horizontal", length=300, mode="determinate")
        # Center the progress bar by placing in middle column
        self.progress.grid(row=8, column=1, **pad)

        self.log = tk.Text(self, width=100, height=16, state="disabled")
        self.log.grid(row=9, column=0, columnspan=3, padx=6, pady=(2, 8))

        # Results table: reused to show final extracted fields (compact)
        self.table = ttk.Treeview(self, columns=("File Name",), show="headings", height=10)
        self.table.heading("File Name", text="File Name")
        self.table.column("File Name", width=220)
        self.table.grid(row=10, column=0, columnspan=3, padx=6, pady=(0, 8), sticky="nsew")
        self.grid_rowconfigure(10, weight=1)
        self.grid_columnconfigure(1, weight=1)

    def _append_log(self, message: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", message + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _choose_in_folder(self) -> None:
        path = filedialog.askdirectory()
        if path:
            self.in_folder_var.set(path)

    def _choose_out_file(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv"), ("Excel", "*.xlsx")])
        if path:
            self.out_file_var.set(path)

    def _choose_tesseract(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Tesseract", "tesseract.exe"), ("Executable", "*.exe")])
        if path:
            self.tess_path_var.set(path)

    def _choose_poppler(self) -> None:
        path = filedialog.askdirectory()
        if path:
            self.poppler_var.set(path)

    def _run(self, run_all: bool = True) -> None:
        in_folder = self.in_folder_var.get().strip()
        out_file = self.out_file_var.get().strip()
        tesseract_path = self.tess_path_var.get().strip() or None
        poppler_path = self.poppler_var.get().strip() or None

        # Only require input folder; final output will be saved during extraction step
        err = None
        if not in_folder:
            err = "Please select an input folder."
        if err:
            messagebox.showerror("Error", err)
            return

        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

        self._append_log(f"Scanning folder: {in_folder}")
        pdfs = collect_pdfs_in_folder(in_folder)
        if not pdfs:
            self._append_log("No PDF files found.")
            return

        if not run_all:
            pdfs = pdfs[:1]

        # Clear results table
        for iid in self.table.get_children():
            self.table.delete(iid)
        cols = ["File Name", "Text"]  # in-memory only; not saved to disk

        rows: List[dict] = []
        self.progress.configure(maximum=len(pdfs))
        
        # Real-time CSV updates
        csv_file = out_file if out_file.lower().endswith('.csv') else out_file.replace('.xlsx', '.csv')
        
        for idx, pdf_path in enumerate(pdfs, start=1):
            percentage = int((idx-1) * 100 / len(pdfs))
            self.status_var.set(f"Processing {pdf_path.name} ({idx}/{len(pdfs)}) - {percentage}%")
            self._append_log(f"[{idx}/{len(pdfs)}] Processing {pdf_path.name} ...")
            self.update_idletasks()
            
            # OCR the PDF to text, updating the viewer live
            try:
                self.current_file_var.set(pdf_path.name)
                def on_page(page_text: str, idx_page: int, total_pages: int) -> None:
                    existing = self.ocr_text_view.get("1.0", "end")
                    new_text = (existing + ("\n\n" if existing.strip() else "") + page_text)[-8000:]
                    self.ocr_text_view.delete("1.0", "end")
                    self.ocr_text_view.insert("1.0", new_text)
                    self.ocr_text_view.see("end")
                    self.update_idletasks()
                full_text = ocr_pdf_to_text(
                pdf_path,
                tesseract_cmd=tesseract_path,
                poppler_path=poppler_path,
                    on_page=on_page,
                log=lambda m: self._append_log(m),
                )
            except Exception as exc:  # noqa: BLE001
                full_text = ""
                self._append_log(f"OCR failed for {pdf_path.name}: {exc}")

            row: dict = {"File Name": pdf_path.name, "Text": full_text}
            rows.append(row)
            
            # Update progress
            self.progress['value'] = idx
            percentage = int(idx * 100 / len(pdfs))
            self.status_var.set(f"Completed {pdf_path.name} ({idx}/{len(pdfs)}) - {percentage}%")
            
            # Add to results table using a short snippet
            snippet = (full_text.strip().replace("\r", " ").replace("\n", " ")[:180] + ("..." if len(full_text) > 180 else "")) if full_text else ""
            self.table.insert("", "end", values=(pdf_path.name, snippet, ""))
            
            self._append_log(f"Completed: {pdf_path.name}")
            self.update_idletasks()

        # Do not save OCR text to disk; keep in memory for extractor
        self.status_var.set("OCR texts ready. Use 'Select Fields (First PDF)' then 'Final Extract'.")

        # Cache OCR rows for extractor step
        self._ocr_rows_cache = rows

    # Preview functionality removed; live viewer shows OCR during processing

    # Removed: _toggle_advanced and T5 processing; regex-only mode

    def _open_extractor(self) -> None:
        # Require OCR data
        rows: List[Dict[str, str]] = getattr(self, "_ocr_rows_cache", [])
        if not rows:
            messagebox.showerror("Extractor", "Run OCR first to populate texts.")
            return

        dlg = tk.Toplevel(self)
        dlg.title("Extractor - Define Fields by Selection")
        dlg.geometry("900x600")
        # Apply same icon to dialog
        try:
            if hasattr(self, "icon_img"):
                dlg.iconphoto(True, self.icon_img)
        except Exception:
            pass

        # Left: list of files
        file_list = tk.Listbox(dlg, width=40, exportselection=False)
        file_list.grid(row=0, column=0, rowspan=3, sticky="nsw", padx=6, pady=6)
        for r in rows:
            file_list.insert("end", r.get("File Name", ""))

        # Right: text viewer
        text_view = tk.Text(dlg, width=80, height=24, exportselection=False)
        text_view.grid(row=0, column=1, columnspan=3, sticky="nsew", padx=6, pady=6)
        dlg.grid_columnconfigure(1, weight=1)
        dlg.grid_rowconfigure(0, weight=1)

        # Field name and patterns view
        tk.Label(dlg, text="Field Name:").grid(row=1, column=1, sticky="w", padx=6)
        field_name_var = tk.StringVar(value="Field1")
        tk.Entry(dlg, textvariable=field_name_var, width=30).grid(row=1, column=2, sticky="w", padx=6)
        tk.Button(dlg, text="Use Selection", command=lambda: add_field_from_selection()).grid(row=1, column=3, sticky="e", padx=6)

        tk.Label(dlg, text="Fields & Patterns:").grid(row=2, column=1, sticky="nw", padx=6)
        patterns_view = tk.Text(dlg, width=80, height=10)
        patterns_view.grid(row=2, column=2, columnspan=2, sticky="nsew", padx=6, pady=6)

        field_to_patterns: Dict[str, List[str]] = dict(self.field_to_patterns)
        last_sel = {"start": None, "end": None}

        def refresh_text(*_args: object) -> None:
            idxs = file_list.curselection()
            if not idxs:
                text_view.delete("1.0", "end")
                return
            fn = file_list.get(idxs[0])
            txt = next((r.get("Text", "") for r in rows if r.get("File Name") == fn), "")
            text_view.delete("1.0", "end")
            text_view.insert("1.0", txt)

        file_list.bind("<<ListboxSelect>>", refresh_text)
        if rows:
            file_list.selection_set(0)
            refresh_text()

        # Track selection range so clicking buttons doesn't lose it
        def _remember_selection(_event: object = None) -> None:
            try:
                last_sel["start"] = text_view.index("sel.first")
                last_sel["end"] = text_view.index("sel.last")
            except Exception:
                last_sel["start"] = None
                last_sel["end"] = None
        text_view.bind("<<Selection>>", _remember_selection)
        text_view.bind("<ButtonRelease-1>", _remember_selection)

        def add_field_from_selection() -> None:
            try:
                sample = text_view.get("sel.first", "sel.last").strip()
            except Exception:
                # Fall back to last remembered selection
                if last_sel["start"] and last_sel["end"]:
                    try:
                        sample = text_view.get(last_sel["start"], last_sel["end"]).strip()
                    except Exception:
                        sample = ""
                else:
                    sample = ""
            if not sample:
                messagebox.showerror("Selection", "Please select sample text in the viewer.")
                return
            # Get lightweight context
            try:
                sel_start = text_view.index("sel.first") if text_view.tag_ranges("sel") else (last_sel["start"] or "1.0")
                sel_end = text_view.index("sel.last") if text_view.tag_ranges("sel") else (last_sel["end"] or "1.0")
                ctx_start = text_view.index(f"{sel_start} -50c")
                ctx_end = text_view.index(f"{sel_end} +50c")
                ctx = text_view.get(ctx_start, ctx_end)
            except Exception:
                ctx = ""

            pats = generate_smart_patterns(sample, ctx)[:6]
            # Add optional windowed patterns based on first/last 3 words around selection
            # Build word lists from the entire line around the selection to stabilize anchors
            # Get the full line content for stronger context words
            try:
                line_start = text_view.index("sel.first linestart") if text_view.tag_ranges("sel") else (last_sel["start"] or "1.0")
                line_end = text_view.index("sel.last lineend") if text_view.tag_ranges("sel") else (last_sel["end"] or "1.0")
                line_text = text_view.get(line_start, line_end)
            except Exception:
                line_text = ctx or ""
            words = [w for w in re.split(r"\W+", line_text) if w]
            before = words[:3] if words else []
            after = words[-3:] if words else []
            pats += generate_window_patterns(sample, before_words=before, after_words=after, max_words_window=3)
            fname = field_name_var.get().strip() or "Field"
            existing = field_to_patterns.get(fname, [])
            # merge and dedupe
            merged = existing + [p for p in pats if p not in existing]
            field_to_patterns[fname] = merged
            # Show in patterns view
            patterns_view.delete("1.0", "end")
            for k, v in field_to_patterns.items():
                patterns_view.insert("end", f"{k}:\n")
                for p in v:
                    patterns_view.insert("end", f"  - {p}\n")
            patterns_view.see("end")
            # Persist into main state so we can close the window after selection
            self.field_to_patterns = dict(field_to_patterns)

        def run_extraction() -> None:
            if not field_to_patterns:
                messagebox.showerror("Extract", "Add at least one field.")
                return
            # Close after field selection; final extract happens from main window
            messagebox.showinfo("Selection", "Fields captured. Now click 'Final Extract' in the main window.")
            dlg.destroy()

        tk.Button(dlg, text="Use Selection & Close", command=run_extraction).grid(row=3, column=3, sticky="e", padx=6, pady=6)

    def _final_extract(self) -> None:
        # Use persisted OCR rows and field patterns to extract over all PDFs
        rows: List[Dict[str, str]] = getattr(self, "_ocr_rows_cache", [])
        if not rows:
            messagebox.showerror("Final Extract", "Run 'Process All' first to OCR PDFs.")
            return
        if not self.field_to_patterns:
            messagebox.showerror("Final Extract", "Use 'Select Fields (First PDF)' to define fields.")
            return
        out_path = self.out_file_var.get().strip()
        if not out_path:
            messagebox.showerror("Final Extract", "Please set 'Output File' before exporting.")
            return
        results = bulk_extract(rows, self.field_to_patterns)
        lic_rows = bulk_extract_licenses(rows)
        lic_map = {r.get("File Name", ""): r.get("Licenses", "") for r in lic_rows}
        for r in results:
            r["Licenses"] = lic_map.get(r.get("File Name", ""), "")
        cols = ["File Name", "Licenses"] + list(self.field_to_patterns.keys())
        filtered = []
        for r in results:
            has_data = (r.get("Licenses", "").strip() != "") or any((r.get(k, "").strip() != "") for k in self.field_to_patterns.keys())
            if has_data:
                filtered.append({c: r.get(c, "") for c in cols})
        try:
            export_results(filtered, out_path, columns=cols)
            messagebox.showinfo("Final Extract", f"Saved final output to: {out_path}")
            # Rebuild table to show final extracted fields compactly
            for iid in self.table.get_children():
                self.table.delete(iid)
            self.table["columns"] = cols
            for cid in cols:
                self.table.heading(cid, text=cid)
                self.table.column(cid, width=160 if cid != "File Name" else 220)
            for r in filtered:
                self.table.insert("", "end", values=[r.get(c, "") for c in cols])
        except Exception as exc:
            messagebox.showerror("Final Extract", f"Failed to save: {exc}")


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()


