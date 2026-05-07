from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from backend.config import BIDDER_UPLOAD_DIR, CRITERIA_DIR, REPORT_DIR, TENDER_UPLOAD_DIR
from backend.database import init_db
from backend.models.schemas import (
    CriteriaExtractionRequest,
    EvaluationRequest,
    UploadResponse,
)
from backend.services.criteria_extractor import CriteriaExtractor
from backend.services.document_parser import DocumentParser
from backend.services.matcher import MatchingEngine
from backend.services.report_service import ReportService
from backend.utils.audit_logger import AuditLogger
from backend.utils.file_utils import latest_child_dir, read_json, save_upload_file, write_json

app = FastAPI(
    title="TenderMind AI",
    description="AI-based tender evaluation system with explainable, auditable verdicts.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

audit = AuditLogger()
criteria_extractor = CriteriaExtractor()
document_parser = DocumentParser()
matching_engine = MatchingEngine()
report_service = ReportService()


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/health")
def health():
    return {"status": "ok", "service": "TenderMind AI"}


@app.post("/upload-tender", response_model=UploadResponse)
async def upload_tender(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Tender upload must be a PDF.")

    tender_id = f"tender_{uuid4().hex[:10]}"
    target = TENDER_UPLOAD_DIR / tender_id / file.filename
    await save_upload_file(file, target)
    audit.log(
        event_type="upload",
        entity_type="tender",
        entity_id=tender_id,
        message="Tender PDF uploaded.",
        metadata={"filename": file.filename, "path": str(target)},
    )
    return UploadResponse(
        id=tender_id,
        filename=file.filename,
        path=str(target),
        message="Tender uploaded successfully.",
    )


@app.post("/upload-bidders", response_model=UploadResponse)
async def upload_bidders(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Bidder upload must be a ZIP file.")

    batch_id = f"batch_{uuid4().hex[:10]}"
    target = BIDDER_UPLOAD_DIR / batch_id / file.filename
    await save_upload_file(file, target)
    audit.log(
        event_type="upload",
        entity_type="bidder_batch",
        entity_id=batch_id,
        message="Bidder ZIP uploaded.",
        metadata={"filename": file.filename, "path": str(target)},
    )
    return UploadResponse(
        id=batch_id,
        filename=file.filename,
        path=str(target),
        message="Bidder ZIP uploaded successfully.",
    )


@app.post("/extract-criteria")
def extract_criteria(request: Optional[CriteriaExtractionRequest] = None):
    tender_id = request.tender_id if request else None
    tender_dir = resolve_entity_dir(TENDER_UPLOAD_DIR, tender_id, "tender")
    tender_path = first_file(tender_dir, ".pdf")

    criteria = criteria_extractor.extract(tender_path)
    output_path = CRITERIA_DIR / f"{tender_dir.name}.json"
    write_json(output_path, jsonable_encoder(criteria))

    audit.log(
        event_type="extraction",
        entity_type="criteria",
        entity_id=tender_dir.name,
        message="Eligibility criteria extracted from tender.",
        metadata={"criteria_count": len(criteria), "criteria_path": str(output_path)},
    )
    return {
        "tender_id": tender_dir.name,
        "criteria_count": len(criteria),
        "criteria": jsonable_encoder(criteria),
        "path": str(output_path),
    }


@app.post("/evaluate")
def evaluate(request: Optional[EvaluationRequest] = None):
    tender_id = request.tender_id if request else None
    batch_id = request.bidder_batch_id if request else None
    tender_dir = resolve_entity_dir(TENDER_UPLOAD_DIR, tender_id, "tender")
    batch_dir = resolve_entity_dir(BIDDER_UPLOAD_DIR, batch_id, "bidder batch")
    tender_id = tender_dir.name
    batch_id = batch_dir.name

    criteria_path = CRITERIA_DIR / f"{tender_id}.json"
    if criteria_path.exists():
        criteria_payload = read_json(criteria_path)
        from backend.models.schemas import Criterion

        criteria = [Criterion(**item) for item in criteria_payload]
    else:
        tender_path = first_file(tender_dir, ".pdf")
        criteria = criteria_extractor.extract(tender_path)
        write_json(criteria_path, jsonable_encoder(criteria))

    zip_path = first_file(batch_dir, ".zip")
    bidders = document_parser.parse_bidder_zip(zip_path, batch_id)
    result = matching_engine.evaluate(tender_id, batch_id, criteria, bidders)
    result = report_service.save(result)

    audit.log(
        event_type="evaluation",
        entity_type="evaluation",
        entity_id=result.evaluation_id,
        message="Bidder evaluation completed.",
        metadata={
            "tender_id": tender_id,
            "bidder_batch_id": batch_id,
            "bidders": len(bidders),
            "criteria": len(criteria),
            "report_json": result.report_json_path,
            "report_html": result.report_html_path,
        },
    )
    return JSONResponse(jsonable_encoder(result))


@app.get("/report")
def report(
    evaluation_id: Optional[str] = Query(default=None),
    format: str = Query(default="json", pattern="^(json|html)$"),
):
    report_path = resolve_report_path(evaluation_id, format)
    if format == "html":
        return FileResponse(report_path, media_type="text/html")
    return JSONResponse(read_json(report_path))


@app.get("/audit-logs")
def audit_logs(limit: int = Query(default=50, ge=1, le=500)):
    return {"logs": audit.latest(limit=limit)}


def resolve_entity_dir(root: Path, entity_id: Optional[str], label: str) -> Path:
    if entity_id:
        path = root / entity_id
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"Unknown {label} id: {entity_id}")
        return path
    latest = latest_child_dir(root)
    if latest is None:
        raise HTTPException(status_code=404, detail=f"No {label} uploads found.")
    return latest


def first_file(root: Path, suffix: str) -> Path:
    matches = sorted(path for path in root.glob(f"*{suffix}") if path.is_file())
    if not matches:
        raise HTTPException(status_code=404, detail=f"No {suffix} file found in {root}")
    return matches[0]


def resolve_report_path(evaluation_id: Optional[str], format: str) -> Path:
    suffix = ".html" if format == "html" else ".json"
    if evaluation_id:
        path = REPORT_DIR / f"{evaluation_id}{suffix}"
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"Unknown evaluation id: {evaluation_id}")
        return path
    matches = sorted(REPORT_DIR.glob(f"*{suffix}"), key=lambda path: path.stat().st_mtime)
    if not matches:
        raise HTTPException(status_code=404, detail="No reports found.")
    return matches[-1]

