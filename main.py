from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import List, Optional

import PySimpleGUI as sg  # type: ignore
import pandas as pd  # type: ignore

from ocr import (
    ExtractionResult,
    collect_pdfs_in_folder,
    process_pdf_file,
)


APP_TITLE = "OCR PDF Extractor"
SPLASH_TITLE = "OCR System"

def resource_path(relative_path: str) -> str:
    """
    Get absolute path to resource, works for dev and for PyInstaller.
    """
    try:
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def bundled_poppler_path() -> str:
    """
    Return bundled poppler bin path when frozen; else guess empty.
    Looks for 'poppler-25.07.0/Library/bin' or 'poppler/Library/bin' relative to bundle.
    """
    candidates = [
        resource_path(os.path.join("poppler-25.07.0", "Library", "bin")),
        resource_path(os.path.join("poppler", "Library", "bin")),
        resource_path(os.path.join("poppler-25.07.0", "bin")),
        resource_path(os.path.join("poppler", "bin")),
    ]
    for c in candidates:
        if os.path.isdir(c):
            return c
    # Fallback: try relative to exe directory for portable sharing
    try:
        exe_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
        relative_candidates = [
            os.path.join(exe_dir, "poppler-25.07.0", "Library", "bin"),
            os.path.join(exe_dir, "poppler", "Library", "bin"),
            os.path.join(exe_dir, "poppler-25.07.0", "bin"),
            os.path.join(exe_dir, "poppler", "bin"),
        ]
        for c in relative_candidates:
            if os.path.isdir(c):
                return c
    except Exception:
        pass
    return ""


def guess_tesseract_path() -> str:
    """
    Try common Windows install locations including AppData.
    Returns empty string if not found.
    """
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
    """
    Try a few common poppler bin locations. Returns empty string if not found.
    """
    env = os.environ.get("POPPLER_BIN", "")
    if env and os.path.isdir(env):
        return env
    # Common custom tools folder
    base_candidates = [
        r"C:\\Tools",
        r"C:\\Program Files",
    ]
    for base in base_candidates:
        if not os.path.isdir(base):
            continue
        try:
            for name in os.listdir(base):
                if name.lower().startswith("poppler"):
                    bin_path = os.path.join(base, name, "Library", "bin")
                    if os.path.isdir(bin_path):
                        return bin_path
                    # Alternate packaging sometimes uses just \bin
                    bin_path2 = os.path.join(base, name, "bin")
                    if os.path.isdir(bin_path2):
                        return bin_path2
        except Exception:
            pass
    return ""


def build_layout() -> List[List[sg.Element]]:
    default_tess = guess_tesseract_path()
    default_poppler = bundled_poppler_path() or guess_poppler_bin()
    input_section = [
        [sg.Text("Input Folder (PDFs):", size=(20, 1)), sg.Input(key="-IN_FOLDER-"), sg.FolderBrowse("Browse")],
        [sg.Text("Output File (CSV/XLSX):", size=(20, 1)), sg.Input(key="-OUT_FILE-"), sg.SaveAs("Save As", file_types=(
            ("CSV", "*.csv"), ("Excel", "*.xlsx")), default_extension=".csv")],
        [sg.Text("Tesseract Path:", size=(20, 1)), sg.Input(key="-TESS_PATH-", default_text=default_tess), sg.FileBrowse("Browse")],
        [sg.Text("Poppler bin Folder:", size=(20, 1)), sg.Input(key="-POPPLER_PATH-", default_text=default_poppler, disabled=True), sg.Text("(Auto-detected)", size=(15, 1))],
    ]

    actions_section = [
        [sg.Button("Run Extraction", key="-RUN-", button_color=("white", "#0078D4")),
         sg.Button("Exit")]
    ]

    log_section = [
        [sg.Multiline(size=(100, 20), key="-LOG-", autoscroll=True, disabled=True)]
    ]

    layout = [
        [sg.Frame("Configuration", input_section, pad=(5, 5))],
        [sg.Frame("Actions", actions_section, pad=(5, 5))],
        [sg.Frame("Log", log_section, pad=(5, 5))],
    ]
    return layout


def log(window: sg.Window, message: str) -> None:
    window["-LOG-"].update(value=message + "\n", append=True)


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
            "Address": getattr(r, "address", "") or "",
            "Start Date": getattr(r, "start_date", "") or "",
            "End Date": getattr(r, "end_date", "") or "",
            "Notes": r.notes or "",
        }
        for r in results
    ]
    df = pd.DataFrame(rows, columns=["File Name", "License ID", "Date", "Reference ID", "Address", "Start Date", "End Date", "Notes"])

    if out_file.lower().endswith(".csv"):
        df.to_csv(out_file, index=False, encoding="utf-8")
    else:
        with pd.ExcelWriter(out_file, engine="openpyxl") as writer:  # type: ignore
            df.to_excel(writer, index=False, sheet_name="Results")


def main() -> None:
    # Splash screen while importing backends or first-run startup
    if hasattr(sg, "theme"):
        sg.theme("SystemDefault")
    splash_layout = [
        [sg.Text(SPLASH_TITLE, font=("Segoe UI", 20))],
        [sg.Image(filename=None, key="-SPLASH_IMG-")],
        [sg.Text("Loading, please wait...")],
        [sg.ProgressBar(max_value=100, orientation="h", size=(40, 20), key="-PB-")],
    ]
    splash = sg.Window("Starting...", splash_layout, no_titlebar=True, finalize=True, keep_on_top=True)
    try:
        # Optionally load an embedded/logo image in future via resource_path
        for i in range(0, 101, 10):
            splash["-PB-"].update(i)
            sg.sleep(50)
    finally:
        splash.close()

    layout = build_layout()
    window = sg.Window(APP_TITLE, layout, finalize=True, icon=resource_path("newicon.ico"))

    while True:
        event, values = window.read()
        if event in (sg.WINDOW_CLOSED, "Exit"):
            break

        if event == "-RUN-":
            in_folder = values.get("-IN_FOLDER-") or ""
            out_file = values.get("-OUT_FILE-") or ""
            tesseract_path = values.get("-TESS_PATH-") or None
            poppler_path = values.get("-POPPLER_PATH-") or None

            err = validate_paths(in_folder, out_file)
            if err:
                sg.popup_error(err)
                continue

            window["-LOG-"].update("")
            log(window, f"Scanning folder: {in_folder}")
            pdfs = collect_pdfs_in_folder(in_folder)

            if not pdfs:
                log(window, "No PDF files found.")
                continue

            results: List[ExtractionResult] = []
            for idx, pdf_path in enumerate(pdfs, start=1):
                log(window, f"[{idx}/{len(pdfs)}] Processing {pdf_path.name} ...")
                res = process_pdf_file(
                    pdf_path,
                    tesseract_cmd=tesseract_path,
                    poppler_path=poppler_path,
                    log=lambda m, fn=pdf_path.name: log(window, m),
                )
                results.append(res)
                log(window, f"Completed: {pdf_path.name}")

            try:
                export_results(results, out_file)
                log(window, f"Saved results to {out_file}")
                sg.popup_ok("Extraction completed successfully.")
            except Exception as exc:  # noqa: BLE001
                sg.popup_error(f"Failed to save results: {exc}")

    window.close()


if __name__ == "__main__":
    main()


