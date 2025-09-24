from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import List, Optional
import re

import pandas as pd  # type: ignore
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk

from ocr_utils import (
    ExtractionResult,
    collect_pdfs_in_folder,
    process_pdf_file,
)
from t5_extractor import extract_with_context_t5


APP_TITLE = "OCR PDF Extractor (Tkinter)"


def resource_path(relative_path: str) -> str:
    try:
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def guess_tesseract_path() -> str:
    candidates = [
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


def export_results(results: List[ExtractionResult], out_file: str) -> None:
    rows = [
        {
            "File Name": r.file_name,
            "License ID": r.license_id or "",
            "Date": r.date or "",
            "Reference ID": r.reference_id or "",
            "Notes": r.notes or "",
        }
        for r in results
    ]
    df = pd.DataFrame(rows, columns=["File Name", "License ID", "Date", "Reference ID", "Notes"])

    if out_file.lower().endswith(".csv"):
        df.to_csv(out_file, index=False, encoding="utf-8")
    else:
        with pd.ExcelWriter(out_file, engine="openpyxl") as writer:  # type: ignore
            df.to_excel(writer, index=False, sheet_name="Results")


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)

        self.in_folder_var = tk.StringVar(value="")
        self.out_file_var = tk.StringVar(value="")
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

        # Extraction method toggle
        self.extraction_method = tk.StringVar(value="t5")
        tk.Label(self, text="Extraction Method:", width=22, anchor="w").grid(row=4, column=0, **pad)
        tk.Radiobutton(self, text="T5 AI Model (Recommended)", variable=self.extraction_method, value="t5").grid(row=4, column=1, sticky="w", **pad)
        tk.Radiobutton(self, text="Regex Patterns", variable=self.extraction_method, value="regex").grid(row=4, column=2, sticky="w", **pad)

        # Pattern inputs frame (hidden by default)
        self.adv_frame = tk.Frame(self)
        self.adv_frame.grid(row=5, column=0, columnspan=3, sticky="we", padx=6, pady=2)

        tk.Label(self.adv_frame, text="License Regex (first match):", width=22, anchor="w").grid(row=0, column=0, padx=6, pady=4)
        self.license_pat = tk.Entry(self.adv_frame, width=60)
        self.license_pat.insert(0, r"\bLIC[-_\s]?\d{3,}\b|\b[A-Z0-9]{6,20}\b")
        self.license_pat.grid(row=0, column=1, padx=6, pady=4)
        tk.Button(self.adv_frame, text="Reset", command=lambda: self.license_pat.delete(0, 'end') or self.license_pat.insert(0, r"\bLIC[-_\s]?\d{3,}\b|\b[A-Z0-9]{6,20}\b")).grid(row=0, column=2, padx=6, pady=4)

        tk.Label(self.adv_frame, text="Date Regex:", width=22, anchor="w").grid(row=1, column=0, padx=6, pady=4)
        self.date_pat = tk.Entry(self.adv_frame, width=60)
        self.date_pat.insert(0, r"\b\d{2}[\/-]\d{2}[\/-]\d{4}\b|\b\d{4}[\/-]\d{2}[\/-]\d{2}\b")
        self.date_pat.grid(row=1, column=1, padx=6, pady=4)
        tk.Button(self.adv_frame, text="Reset", command=lambda: self.date_pat.delete(0, 'end') or self.date_pat.insert(0, r"\b\d{2}[\/-]\d{2}[\/-]\d{4}\b|\b\d{4}[\/-]\d{2}[\/-]\d{2}\b")).grid(row=1, column=2, padx=6, pady=4)

        tk.Label(self.adv_frame, text="Reference Regex:", width=22, anchor="w").grid(row=2, column=0, padx=6, pady=4)
        self.ref_pat = tk.Entry(self.adv_frame, width=60)
        self.ref_pat.insert(0, r"\bREF[-_\s]*([A-Z0-9]{4,10})\b|\b(?:Reference|Ref)[\s:#-]*([A-Z0-9-]{4,10})\b|\b[A-Z0-9]{4,10}\b")
        self.ref_pat.grid(row=2, column=1, padx=6, pady=4)
        tk.Button(self.adv_frame, text="Reset", command=lambda: self.ref_pat.delete(0, 'end') or self.ref_pat.insert(0, r"\bREF[-_\s]*([A-Z0-9]{4,10})\b|\b(?:Reference|Ref)[\s:#-]*([A-Z0-9-]{4,10})\b|\b[A-Z0-9]{4,10}\b")).grid(row=2, column=2, padx=6, pady=4)

        # Hide regex frame initially (T5 is default)
        self.adv_frame.grid_remove()

        # Controls
        tk.Button(self, text="Preview First PDF", command=self._preview).grid(row=7, column=0, sticky="w", **pad)
        tk.Button(self, text="Test Run (First PDF)", command=lambda: self._run(run_all=False)).grid(row=7, column=1, sticky="e", **pad)
        tk.Button(self, text="Run All", command=lambda: self._run(run_all=True), bg="#0078D4", fg="white").grid(row=7, column=2, sticky="w", **pad)
        tk.Button(self, text="Exit", command=self.destroy).grid(row=7, column=3, sticky="w", **pad)

        # Progress
        self.status_var = tk.StringVar(value="Idle")
        tk.Label(self, textvariable=self.status_var, anchor="w").grid(row=8, column=0, columnspan=2, sticky="w", **pad)
        self.progress = ttk.Progressbar(self, orient="horizontal", length=400, mode="determinate")
        self.progress.grid(row=8, column=2, sticky="e", **pad)

        self.log = tk.Text(self, width=100, height=16, state="disabled")
        self.log.grid(row=9, column=0, columnspan=3, padx=6, pady=(2, 8))

        # Results table (dynamic columns when using user-defined fields)
        cols = ("file", "license", "date", "reference", "notes")
        self.table = ttk.Treeview(self, columns=cols, show="headings", height=8)
        for cid, text in zip(cols, ["File Name", "License ID", "Date", "Reference ID", "Notes"]):
            self.table.heading(cid, text=text)
            self.table.column(cid, width=150 if cid != "notes" else 260)
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

        err = validate_paths(in_folder, out_file)
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

        # Choose extraction method
        if self.extraction_method.get() == "t5":
            # T5 AI Model extraction
            field_types = ["license_id", "date", "reference_id"]
            patterns = None  # T5 doesn't use patterns
        else:
            # Regex extraction
            def _split_patterns(s: str) -> List[str]:
                return [p for p in [part.strip() for part in s.split("|")] if p]
            patterns = {
                "license_id": _split_patterns(self.license_pat.get()),
                "date": _split_patterns(self.date_pat.get()),
                "reference_id": _split_patterns(self.ref_pat.get()),
            }
            field_types = None

        results: List[ExtractionResult] = []
        for i in self.table.get_children():
            self.table.delete(i)
        self.progress.configure(maximum=len(pdfs))
        
        # Real-time CSV updates
        csv_file = out_file if out_file.lower().endswith('.csv') else out_file.replace('.xlsx', '.csv')
        
        for idx, pdf_path in enumerate(pdfs, start=1):
            percentage = int((idx-1) * 100 / len(pdfs))
            self.status_var.set(f"Processing {pdf_path.name} ({idx}/{len(pdfs)}) - {percentage}%")
            self._append_log(f"[{idx}/{len(pdfs)}] Processing {pdf_path.name} ...")
            self.update_idletasks()
            
            if self.extraction_method.get() == "t5":
                # Use T5 extraction
                res = self._process_pdf_with_t5(
                    pdf_path,
                    tesseract_cmd=tesseract_path,
                    poppler_path=poppler_path,
                    field_types=field_types,
                )
            else:
                # Use regex extraction
                res = process_pdf_file(
                    pdf_path,
                    tesseract_cmd=tesseract_path,
                    poppler_path=poppler_path,
                    log=lambda m: self._append_log(m),
                    patterns=patterns,
                )
            results.append(res)
            
            # Update progress
            self.progress['value'] = idx
            percentage = int(idx * 100 / len(pdfs))
            self.status_var.set(f"Completed {pdf_path.name} ({idx}/{len(pdfs)}) - {percentage}%")
            
            # Add to results table
            self.table.insert("", "end", values=(res.file_name, res.license_id or "", res.date or "", res.reference_id or "", res.notes or ""))
            
            # Real-time CSV update
            try:
                export_results(results, csv_file)
                self._append_log(f"Updated CSV: {csv_file}")
            except Exception as exc:
                self._append_log(f"CSV update failed: {exc}")
            
            self._append_log(f"Completed: {pdf_path.name}")
            self.update_idletasks()

        try:
            export_results(results, out_file)
            self._append_log(f"Saved results to {out_file}")
            messagebox.showinfo("Done", "Extraction completed successfully.")
            self.status_var.set("Done")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Save Failed", f"Failed to save results: {exc}")

    def _preview(self) -> None:
        in_folder = self.in_folder_var.get().strip()
        if not in_folder or not Path(in_folder).exists():
            messagebox.showerror("Error", "Please select a valid input folder first.")
            return
        pdfs = collect_pdfs_in_folder(in_folder)
        if not pdfs:
            messagebox.showerror("Error", "No PDF files found in the selected folder.")
            return
        tesseract_path = self.tess_path_var.get().strip() or None
        poppler_path = self.poppler_var.get().strip() or None

        # Preview first page OCR text for first PDF
        from pdf2image import convert_from_path
        from ocr_utils import preprocess_image, ocr_image_to_text
        try:
            pages = convert_from_path(str(pdfs[0]), dpi=300, poppler_path=poppler_path)
            if not pages:
                messagebox.showerror("Preview", "Failed to render PDF first page.")
                return
            pre = preprocess_image(pages[0])
            txt = ocr_image_to_text(pre, tesseract_cmd=tesseract_path)
            # Show top of text in a simple dialog
            snippet = txt.strip()
            if len(snippet) > 2000:
                snippet = snippet[:2000] + "\n... (truncated)"
            preview = tk.Toplevel(self)
            preview.title(f"Preview: {pdfs[0].name}")
            frm = tk.Frame(preview)
            frm.pack(fill="both", expand=True)
            text_widget = tk.Text(frm, width=100, height=32)
            text_widget.grid(row=0, column=0, columnspan=4, sticky="nsew")
            text_widget.insert("1.0", snippet)
            # Enable selection for simple mode capture
            def _get_sel() -> str:
                try:
                    return text_widget.get("sel.first", "sel.last").strip()
                except Exception:
                    return ""
            def _apply_sel(target: str) -> None:
                s = _get_sel()
                if not s:
                    messagebox.showerror("Selection", "Please select text in the preview first.")
                    return
                
                # Get context (text around selection)
                try:
                    sel_start = text_widget.index("sel.first")
                    sel_end = text_widget.index("sel.last")
                    
                    # Get 50 characters before and after selection
                    context_start = text_widget.index(f"{sel_start} -50c")
                    context_end = text_widget.index(f"{sel_end} +50c")
                    context_text = text_widget.get(context_start, context_end)
                except Exception:
                    context_text = ""
                
                if target == "license":
                    self.sel_license = s
                    self.license_context = context_text
                elif target == "date":
                    self.sel_date = s
                    self.date_context = context_text
                else:
                    self.sel_ref = s
                    self.ref_context = context_text
                
                # Show the generated smart patterns
                def _generate_smart_patterns(sample_text: str, context: str) -> List[str]:
                    if not sample_text:
                        return []
                    
                    patterns = []
                    patterns.append(re.escape(sample_text))
                    
                    if re.match(r'\d{1,2}[/-]\d{1,2}[/-]\d{4}', sample_text):
                        patterns.extend([
                            r'\d{1,2}[/-]\d{1,2}[/-]\d{4}',
                            r'\d{4}[/-]\d{1,2}[/-]\d{1,2}',
                            r'\d{1,2}\s+\d{1,2}\s+\d{4}'
                        ])
                    elif re.match(r'[A-Z]{2,}\d+', sample_text):
                        patterns.extend([
                            r'[A-Z]{2,}\d+',
                            r'[A-Z]{2,}[-_\s]?\d+',
                            r'[A-Z]*\d+'
                        ])
                    elif re.match(r'\d+', sample_text):
                        patterns.extend([
                            r'\d+',
                            r'[A-Z]*\d+',
                            r'\d+[A-Z]*'
                        ])
                    
                    if context:
                        context_words = context.split()
                        for word in context_words[:3]:
                            if len(word) > 2:
                                patterns.append(f'\\b{re.escape(word)}.*?{re.escape(sample_text)}')
                    
                    return list(set(patterns))
                
                patterns = _generate_smart_patterns(s, context_text)
                pattern_text = "\n".join([f"• {p}" for p in patterns[:5]])  # Show first 5 patterns
                
                messagebox.showinfo("Saved", f"Captured {target} sample:\n{s}\n\nContext: {context_text[:100]}...\n\nSmart patterns generated:\n{pattern_text}")
            tk.Button(frm, text="Use Selection as License", command=lambda: _apply_sel("license")).grid(row=1, column=1, pady=6)
            tk.Button(frm, text="Use Selection as Date", command=lambda: _apply_sel("date")).grid(row=1, column=2, pady=6)
            tk.Button(frm, text="Use Selection as Reference", command=lambda: _apply_sel("ref")).grid(row=1, column=3, pady=6)
            frm.grid_rowconfigure(0, weight=1)
            frm.grid_columnconfigure(0, weight=1)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Preview", f"Failed to preview: {exc}")

    def _toggle_advanced(self) -> None:
        if self.extraction_method.get() == "regex":
            self.adv_frame.grid()
        else:
            self.adv_frame.grid_remove()
    
    def _process_pdf_with_t5(self, pdf_path: Path, tesseract_cmd: Optional[str], poppler_path: Optional[str], field_types: List[str]) -> ExtractionResult:
        """
        Process PDF using T5 model for extraction.
        """
        from pdf2image import convert_from_path
        from ocr_utils import preprocess_image, ocr_image_to_text
        
        file_name = pdf_path.name
        try:
            self._append_log(f"Converting PDF to images: {file_name}")
            pil_pages = convert_from_path(pdf_path, dpi=300, poppler_path=poppler_path)
            
            all_text_parts = []
            for idx, pil_img in enumerate(pil_pages, start=1):
                self._append_log(f"Preprocessing page {idx} of {file_name}")
                pre = preprocess_image(pil_img)
                self._append_log(f"Running OCR on page {idx} of {file_name}")
                txt = ocr_image_to_text(pre, tesseract_cmd=tesseract_cmd)
                all_text_parts.append(txt)
            
            full_text = "\n".join(all_text_parts)
            self._append_log(f"Running T5 extraction on {file_name}")
            
            # Use T5 model for extraction
            extracted_fields = extract_with_context_t5(full_text, field_types, "tf_model.h5")
            
            license_id = extracted_fields.get("license_id")
            date = extracted_fields.get("date")
            reference_id = extracted_fields.get("reference_id")
            
            notes = None
            if not any([license_id, date, reference_id]):
                notes = "No fields extracted by T5 model"
            
            return ExtractionResult(
                file_name=file_name,
                license_id=license_id,
                date=date,
                reference_id=reference_id,
                notes=notes,
            )
        except Exception as exc:
            return ExtractionResult(
                file_name=file_name,
                license_id=None,
                date=None,
                reference_id=None,
                notes=f"Error: {exc}",
            )


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()


