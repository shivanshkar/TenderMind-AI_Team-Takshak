from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
REPORT_DIR = DATA_DIR / "reports"
CRITERIA_DIR = DATA_DIR / "criteria"
SAMPLE_DIR = DATA_DIR / "sample"
DB_PATH = DATA_DIR / "tendermind.db"

TENDER_UPLOAD_DIR = UPLOAD_DIR / "tenders"
BIDDER_UPLOAD_DIR = UPLOAD_DIR / "bidder_batches"

for path in [
    DATA_DIR,
    UPLOAD_DIR,
    REPORT_DIR,
    CRITERIA_DIR,
    SAMPLE_DIR,
    TENDER_UPLOAD_DIR,
    BIDDER_UPLOAD_DIR,
]:
    path.mkdir(parents=True, exist_ok=True)

