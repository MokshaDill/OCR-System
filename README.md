# OCR PDF Extractor (Windows Desktop)

A simple Windows desktop app to OCR scanned PDFs and extract key fields (License ID, Date, Reference ID), then export results to CSV or Excel.

## Features
- Select input folder of scanned PDFs
- Configure Tesseract executable path and Poppler path (for PDF rendering)
- OCR each page (Tesseract via pytesseract)
- Extract fields using regex (easily customizable in `ocr_utils.py`)
- Export to `.csv` or `.xlsx`
- Simple PySimpleGUI UI
- Build standalone `.exe` with PyInstaller

## Prerequisites (Windows)
1. Python 3.10 (recommended) or 3.11
2. Tesseract OCR
   - Download installer from: `https://github.com/UB-Mannheim/tesseract/wiki`
   - Typical path: `C:\\Program Files\\Tesseract-OCR\\tesseract.exe`
3. Poppler for Windows (for `pdf2image`)
   - Download prebuilt binaries: `https://github.com/oschwartz10612/poppler-windows/releases/`
   - Extract and note the `bin` folder path (e.g., `C:\\Tools\\poppler-24.08.0\\Library\\bin` or `...\\poppler-xx\\bin`)
4. Microsoft Visual C++ Redistributable may be required for OpenCV.

## Setup (Development)
```bash
# From project root
python -m venv .venv
.venv\\Scripts\\activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Run (Development)
```bash
python main.py
```

In the app:
- Select Input Folder: folder with `.pdf` files
- Select Output File: choose `.csv` or `.xlsx`
- Tesseract Path: browse to `tesseract.exe`
- Poppler bin Folder: select Poppler's `bin` directory
- Click "Run Extraction"

## Build Standalone .exe
```bash
pip install pyinstaller==6.6.0
pyinstaller --onefile --windowed --name main --add-data "README.md;." main.py
```
The executable will appear in `dist/main.exe`.
If using PySimpleGUI v4, `--windowed` hides the console. For debugging, omit `--windowed`.

If your app needs to load additional data files at runtime when frozen, see the `resource_path()` function in `main.py`.

## Customizing Extraction Rules
Edit patterns in `ocr_utils.py` under `DEFAULT_PATTERNS`:
- `license_id`: list of regex strings
- `date`: list of regex strings
- `reference_id`: list of regex strings

Each list is compiled with `re.IGNORECASE`. The first matching group is returned; if none, the full match is returned.

## Troubleshooting
- Tesseract not found: In the app, set the full path to `tesseract.exe`.
- Poppler missing: Set Poppler `bin` folder path in the app.
- PDFs are images but OCR is poor: Adjust DPI in `convert_pdf_to_images()` or tweak `preprocess_image()` in `ocr_utils.py`.
- Slow processing: Reduce DPI (e.g., 200) or disable adaptive thresholding.
- Excel export error: Ensure `openpyxl` is installed (already pinned).
- Build fails on numpy/opencv: Use Python 3.10/3.11 and the pinned versions in `requirements.txt`.

## Project Structure
```
.
├─ main.py              # GUI + workflow
├─ ocr_utils.py         # OCR, PDF, regex utilities
├─ requirements.txt     # Dependencies
└─ README.md            # This file
```

## License
MIT


