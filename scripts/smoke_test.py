from pathlib import Path
import sys

from fastapi.encoders import jsonable_encoder

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.config import BIDDER_UPLOAD_DIR, CRITERIA_DIR, TENDER_UPLOAD_DIR
from backend.services.criteria_extractor import CriteriaExtractor
from backend.services.document_parser import DocumentParser
from backend.services.matcher import MatchingEngine
from backend.services.report_service import ReportService
from backend.utils.file_utils import write_json


SAMPLE_DIR = ROOT / "data" / "sample"


def main() -> None:
    tender_id = "tender_sample"
    batch_id = "batch_sample"
    tender_path = SAMPLE_DIR / "sample_tender_ai_services.pdf"
    bidder_zip = SAMPLE_DIR / "sample_bidders.zip"

    if not tender_path.exists() or not bidder_zip.exists():
        raise SystemExit("Run scripts/generate_sample_data.py first.")

    target_tender_dir = TENDER_UPLOAD_DIR / tender_id
    target_batch_dir = BIDDER_UPLOAD_DIR / batch_id
    target_tender_dir.mkdir(parents=True, exist_ok=True)
    target_batch_dir.mkdir(parents=True, exist_ok=True)
    (target_tender_dir / tender_path.name).write_bytes(tender_path.read_bytes())
    (target_batch_dir / bidder_zip.name).write_bytes(bidder_zip.read_bytes())

    criteria = CriteriaExtractor().extract(tender_path)
    write_json(CRITERIA_DIR / f"{tender_id}.json", jsonable_encoder(criteria))
    bidders = DocumentParser().parse_bidder_zip(bidder_zip, batch_id)
    result = MatchingEngine().evaluate(tender_id, batch_id, criteria, bidders)
    result = ReportService().save(result)

    print(f"Criteria extracted: {len(criteria)}")
    print(f"Bidders parsed: {len(bidders)}")
    print(f"Evaluations: {len(result.evaluations)}")
    print(f"JSON report: {result.report_json_path}")
    print(f"HTML report: {result.report_html_path}")
    for bidder, summary in result.summary.items():
        print(f"{bidder}: {summary}")


if __name__ == "__main__":
    main()
