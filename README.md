# TenderMind AI

AI-based tender evaluation system for government procurement workflows.

TenderMind AI extracts eligibility criteria from tender PDFs, parses bidder ZIP uploads, evaluates bidder evidence against criteria, flags ambiguous cases for human review, and produces auditable JSON and HTML reports.

## What It Does

- Extracts eligibility criteria into a Pydantic JSON schema.
- Parses typed PDFs, scanned PDFs, images, and text files.
- Uses `pdfplumber` / PyMuPDF for PDF text and `pytesseract` + OpenCV preprocessing for OCR fallback.
- Applies deterministic rules for numeric, date, boolean, and mandatory checks.
- Uses sentence-transformers MiniLM for semantic similarity when installed, with a deterministic fallback for quick demos.
- Outputs PASS / FAIL / NEEDS_REVIEW with confidence, evidence source, rule, and reasoning.
- Logs upload, extraction, and evaluation events to SQLite.

## Folder Structure

```text
backend/
  main.py
  config.py
  database.py
  models/
    schemas.py
  services/
    criteria_extractor.py
    document_parser.py
    matcher.py
    rule_engine.py
    confidence_engine.py
    report_service.py
  utils/
    audit_logger.py
    file_utils.py
    llm_client.py
frontend/
  streamlit_app.py
data/
  sample/
  uploads/
  criteria/
  reports/
scripts/
  generate_sample_data.py
  smoke_test.py
```

## Setup

Python 3.10+ is recommended.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-lite.txt
```

For full semantic model support:

```powershell
python -m pip install -r requirements.txt
```

`requirements-lite.txt` is optimized for a fast hackathon run. The app still works without an API key or downloaded embedding model.

OCR note: `pytesseract` is the Python wrapper. For real scanned documents, install the Tesseract binary and ensure `tesseract` is on PATH. Typed PDFs work without it.

## Generate Sample Data

```powershell
python scripts/generate_sample_data.py
```

This creates:

- `data/sample/sample_tender_ai_services.pdf`
- `data/sample/sample_bidders.zip`

The ZIP contains three bidders with mixed evidence quality so the demo shows PASS, FAIL, and NEEDS_REVIEW cases.

## Run Backend

```powershell
uvicorn backend.main:app --reload --port 8000
```

API docs:

- http://localhost:8000/docs
- http://localhost:8000/health

Endpoints:

- `POST /upload-tender`
- `POST /upload-bidders`
- `POST /extract-criteria`
- `POST /evaluate`
- `GET /report`
- `GET /audit-logs`

## Run Frontend

In a second terminal:

```powershell
streamlit run frontend/streamlit_app.py
```

Open the Streamlit URL shown in the terminal.

## Example Workflow

1. Generate sample data.
2. Start the FastAPI backend.
3. Start the Streamlit frontend.
4. Upload `data/sample/sample_tender_ai_services.pdf`.
5. Upload `data/sample/sample_bidders.zip`.
6. Click `Extract Criteria`.
7. Click `Evaluate`.
8. Review the color-coded matrix, scoring summary, and flagged cases.
9. Open the generated HTML report from the frontend or call:

```powershell
curl "http://localhost:8000/report?format=html" -o report.html
```

## Smoke Test

```powershell
python scripts/generate_sample_data.py
python scripts/smoke_test.py
```

Expected result:

- Criteria extracted from the tender PDF.
- Three bidders parsed from the ZIP.
- JSON and HTML reports written to `data/reports/`.
- Audit logs stored in `data/tendermind.db`.

## Design Principles

- No silent rejection: missing or unclear evidence becomes `NEEDS_REVIEW`.
- Every verdict includes criterion, extracted value, source document, rule applied, confidence, and reasoning.
- The AI layer is replaceable: `backend/utils/llm_client.py` can be wired to OpenAI, Claude, or another provider while preserving the `Criterion` schema.
- The prototype is local-first and demo-friendly: no API key is required.
