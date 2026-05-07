import re
import shutil
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from xml.etree import ElementTree

from backend.config import BIDDER_UPLOAD_DIR
from backend.models.schemas import Bidder, DocumentExtraction, ExtractedField
from backend.utils.file_utils import iter_supported_files, safe_extract_zip, slugify


SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".txt", ".docx"}


class DocumentParser:
    def parse_bidder_zip(self, zip_path: Path, batch_id: str) -> List[Bidder]:
        extract_root = BIDDER_UPLOAD_DIR / batch_id / "extracted"
        if extract_root.exists():
            shutil.rmtree(extract_root)
        safe_extract_zip(zip_path, extract_root)

        grouped = self._group_bidder_files(extract_root)
        bidders: List[Bidder] = []
        for bidder_name, files in grouped.items():
            documents: List[DocumentExtraction] = []
            for file_path in files:
                text, parser_name, confidence = self.extract_text_from_path(file_path)
                documents.append(
                    DocumentExtraction(
                        file_name=file_path.name,
                        parser=parser_name,
                        text=text,
                        confidence=confidence,
                    )
                )
            fields = self.extract_fields(documents)
            bidders.append(
                Bidder(
                    id=f"bidder_{slugify(bidder_name)}",
                    name=bidder_name.replace("_", " ").strip(),
                    documents=documents,
                    fields=fields,
                )
            )
        return bidders

    def extract_text_from_path(self, path: Path) -> Tuple[str, str, float]:
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            return self._extract_pdf_text(path)
        if suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}:
            return self._extract_image_text(path)
        if suffix == ".txt":
            return path.read_text(encoding="utf-8", errors="ignore"), "plain_text", 0.88
        if suffix == ".docx":
            return self._extract_docx_text(path)
        return "", "unsupported", 0.0

    def extract_fields(self, documents: List[DocumentExtraction]) -> Dict[str, ExtractedField]:
        fields: Dict[str, ExtractedField] = {}
        for name, extractor in FIELD_EXTRACTORS.items():
            candidate = None
            for doc in documents:
                candidate = extractor(doc)
                if candidate:
                    break
            if candidate:
                fields[name] = candidate
        return fields

    def _extract_pdf_text(self, path: Path) -> Tuple[str, str, float]:
        text = ""
        try:
            import pdfplumber

            with pdfplumber.open(str(path)) as pdf:
                text = "\n".join(page.extract_text() or "" for page in pdf.pages)
            if len(text.strip()) > 40:
                return text, "pdfplumber", 0.93
        except Exception:
            pass

        try:
            import fitz

            with fitz.open(str(path)) as doc:
                text = "\n".join(page.get_text("text") for page in doc)
            if len(text.strip()) > 40:
                return text, "pymupdf", 0.9
        except Exception:
            pass

        ocr_text = self._ocr_pdf(path)
        if ocr_text.strip():
            return ocr_text, "pytesseract_ocr_pdf", 0.72
        return text, "pdf_text_failed", 0.25

    def _extract_image_text(self, path: Path) -> Tuple[str, str, float]:
        try:
            import cv2
            import pytesseract

            image = cv2.imread(str(path))
            if image is None:
                return "", "opencv_read_failed", 0.0
            processed = preprocess_for_ocr(image)
            text = pytesseract.image_to_string(processed)
            return text, "pytesseract_ocr_image", 0.74 if text.strip() else 0.2
        except Exception:
            return "", "pytesseract_unavailable", 0.0

    def _extract_docx_text(self, path: Path) -> Tuple[str, str, float]:
        try:
            with zipfile.ZipFile(path) as archive:
                xml = archive.read("word/document.xml")
            root = ElementTree.fromstring(xml)
            namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
            texts = [node.text or "" for node in root.findall(".//w:t", namespace)]
            text = "\n".join(part for part in texts if part.strip())
            return text, "docx_xml", 0.9 if text.strip() else 0.25
        except Exception:
            return "", "docx_parse_failed", 0.0

    def _ocr_pdf(self, path: Path) -> str:
        try:
            import cv2
            import fitz
            import numpy as np
            import pytesseract

            output = []
            with fitz.open(str(path)) as doc:
                for page in doc:
                    pix = page.get_pixmap(dpi=180)
                    image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                        pix.height,
                        pix.width,
                        pix.n,
                    )
                    if pix.n == 4:
                        image = cv2.cvtColor(image, cv2.COLOR_RGBA2RGB)
                    processed = preprocess_for_ocr(image)
                    output.append(pytesseract.image_to_string(processed))
            return "\n".join(output)
        except Exception:
            return ""

    def _group_bidder_files(self, root: Path) -> Dict[str, List[Path]]:
        grouped: Dict[str, List[Path]] = {}
        for path in iter_supported_files(root, SUPPORTED_EXTENSIONS):
            relative = path.relative_to(root)
            if len(relative.parts) > 1:
                bidder_name = relative.parts[0]
            else:
                bidder_name = infer_bidder_name(path.stem)
            grouped.setdefault(bidder_name, []).append(path)
        return grouped


def preprocess_for_ocr(image):
    import cv2

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    gray = cv2.medianBlur(gray, 3)
    return cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]


def infer_bidder_name(stem: str) -> str:
    parts = re.split(r"[_\-]", stem)
    return "_".join(parts[:2]) if len(parts) > 1 else stem


def normalized_text(document: DocumentExtraction) -> str:
    return re.sub(r"\s+", " ", document.text).strip()


def confidence(document: DocumentExtraction, exact_label: bool = True) -> float:
    boost = 0.04 if exact_label else -0.05
    return max(0.0, min(0.98, document.confidence + boost))


def excerpt(text: str, match_start: int, match_end: int, radius: int = 90) -> str:
    start = max(0, match_start - radius)
    end = min(len(text), match_end + radius)
    return text[start:end].strip()


def make_field(
    document: DocumentExtraction,
    name: str,
    raw_value: str,
    normalized_value,
    start: int,
    end: int,
    exact_label: bool = True,
) -> ExtractedField:
    text = normalized_text(document)
    return ExtractedField(
        name=name,
        raw_value=raw_value,
        normalized_value=normalized_value,
        confidence=confidence(document, exact_label),
        source_document=document.file_name,
        source_excerpt=excerpt(text, start, end),
    )


def find_first(document: DocumentExtraction, patterns: List[str]) -> Optional[re.Match]:
    text = normalized_text(document)
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match
    return None


def money_to_lakhs(amount: float, unit: str) -> float:
    unit = unit.lower()
    return amount * 100 if unit in {"crore", "cr"} else amount


def truthy_from_text(value: str) -> Optional[bool]:
    text = value.strip().lower()
    positive = {"yes", "valid", "available", "registered", "certified", "positive", "true", "compliant", "india", "within india"}
    negative = {"no", "not available", "not registered", "not certified", "negative", "false", "nil", "outside india"}
    if text in positive:
        return True
    if text in negative:
        return False
    if "not blacklisted" in text or "not debarred" in text:
        return False
    if "blacklisted" in text or "debarred" in text:
        return True
    return None


def extract_years(document: DocumentExtraction) -> Optional[ExtractedField]:
    patterns = [
        r"(?:years?\s+of\s+experience|experience)\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(?:years?)?",
        r"(\d+(?:\.\d+)?)\s*\+?\s+years?\s+(?:of\s+)?(?:relevant\s+)?experience",
    ]
    match = find_first(document, patterns)
    if not match:
        return None
    value = match.group(1)
    return make_field(document, "years_experience", value, float(value), match.start(), match.end())


def extract_turnover(document: DocumentExtraction) -> Optional[ExtractedField]:
    patterns = [
        r"(?:average\s+annual\s+)?turnover\s*[:\-]?\s*(?:inr|rs\.?)?\s*(\d+(?:\.\d+)?)\s*(crore|cr|lakh|lakhs|lac|lacs)",
        r"(?:inr|rs\.?)\s*(\d+(?:\.\d+)?)\s*(crore|cr|lakh|lakhs|lac|lacs)\s+(?:average\s+annual\s+)?turnover",
    ]
    match = find_first(document, patterns)
    if not match:
        return None
    amount = float(match.group(1))
    unit = match.group(2)
    lakhs = money_to_lakhs(amount, unit)
    return make_field(
        document,
        "annual_turnover_lakhs",
        f"{amount:g} {unit}",
        lakhs,
        match.start(),
        match.end(),
    )


def extract_projects(document: DocumentExtraction) -> Optional[ExtractedField]:
    patterns = [
        r"(?:similar\s+projects?|completed\s+projects?)\s*[:\-]?\s*(\d+)",
        r"(\d+)\s+(?:similar\s+)?projects?\s+completed",
    ]
    match = find_first(document, patterns)
    if not match:
        return None
    value = match.group(1)
    return make_field(document, "similar_projects_count", value, int(value), match.start(), match.end())


def extract_gst(document: DocumentExtraction) -> Optional[ExtractedField]:
    patterns = [
        r"(gst(?:in| registration)?)\s*[:\-]?\s*([a-z0-9]{15}|yes|valid|available|registered|no|not registered)",
    ]
    match = find_first(document, patterns)
    if not match:
        return None
    raw = match.group(2)
    value = truthy_from_text(raw)
    if value is None:
        value = bool(re.match(r"^[a-z0-9]{15}$", raw, flags=re.IGNORECASE))
    return make_field(document, "gst_registration", raw, value, match.start(), match.end())


def extract_iso(document: DocumentExtraction) -> Optional[ExtractedField]:
    patterns = [
        r"(iso\s*9001(?:\s+certificate|\s+certification)?)\s*[:\-]?\s*(yes|valid|available|certified|no|not certified|not available)",
        r"(valid\s+iso\s*9001)",
    ]
    match = find_first(document, patterns)
    if not match:
        return None
    raw = match.group(match.lastindex or 1)
    value = truthy_from_text(raw)
    if value is None:
        value = True
    return make_field(document, "iso_9001_certificate", raw, value, match.start(), match.end())


def extract_blacklisted(document: DocumentExtraction) -> Optional[ExtractedField]:
    patterns = [
        r"(blacklisted|debarred)\s*[:\-]?\s*(yes|no|not blacklisted|not debarred|nil)",
        r"(not\s+(?:blacklisted|debarred))",
    ]
    match = find_first(document, patterns)
    if not match:
        return None
    raw = match.group(match.lastindex or 1)
    value = truthy_from_text(raw)
    if value is None:
        value = False if "not" in raw.lower() or "nil" in raw.lower() else True
    return make_field(document, "blacklisted_status", raw, value, match.start(), match.end())


def extract_net_worth(document: DocumentExtraction) -> Optional[ExtractedField]:
    patterns = [
        r"net\s+worth\s*[:\-]?\s*(positive|negative|yes|no)",
        r"(positive\s+net\s+worth)",
    ]
    match = find_first(document, patterns)
    if not match:
        return None
    raw = match.group(match.lastindex or 1)
    value = truthy_from_text(raw)
    if value is None:
        value = "positive" in raw.lower()
    return make_field(document, "net_worth_positive", raw, value, match.start(), match.end())


def extract_iso_valid_until(document: DocumentExtraction) -> Optional[ExtractedField]:
    match = find_first(
        document,
        [
            r"iso\s*9001(?:\s+certificate|\s+certification)?\s+valid\s+until\s*[:\-]?\s*(\d{4}-\d{2}-\d{2}|\d{2}[-/]\d{2}[-/]\d{4})",
            r"iso\s+validity\s*[:\-]?\s*(\d{4}-\d{2}-\d{2}|\d{2}[-/]\d{2}[-/]\d{4})",
        ],
    )
    if not match:
        return None
    raw = match.group(1)
    return make_field(document, "iso_certificate_valid_until", raw, normalize_date(raw), match.start(), match.end())


def extract_bid_security_valid_until(document: DocumentExtraction) -> Optional[ExtractedField]:
    match = find_first(
        document,
        [
            r"(?:bid\s+security|emd)\s+valid\s+until\s*[:\-]?\s*(\d{4}-\d{2}-\d{2}|\d{2}[-/]\d{2}[-/]\d{4})",
            r"validity\s+of\s+(?:bid\s+security|emd)\s*[:\-]?\s*(\d{4}-\d{2}-\d{2}|\d{2}[-/]\d{2}[-/]\d{4})",
        ],
    )
    if not match:
        return None
    raw = match.group(1)
    return make_field(document, "bid_security_valid_until", raw, normalize_date(raw), match.start(), match.end())


def extract_data_residency(document: DocumentExtraction) -> Optional[ExtractedField]:
    match = find_first(
        document,
        [
            r"data\s+residency\s*[:\-]?\s*(india|yes|compliant|within india|no|outside india)",
            r"(?:host|hosting|process|processing)\s+(?:all\s+)?(?:tender\s+)?data\s+(?:within|in)\s+india",
        ],
    )
    if not match:
        return None
    raw = match.group(match.lastindex) if match.lastindex else match.group(0)
    value = truthy_from_text(raw)
    if value is None:
        value = "india" in raw.lower() and "outside" not in raw.lower()
    return make_field(document, "data_residency_india", raw, value, match.start(), match.end())


def extract_local_language_support(document: DocumentExtraction) -> Optional[ExtractedField]:
    match = find_first(
        document,
        [
            r"local\s+language\s+support\s*[:\-]?\s*(yes|available|hindi|regional language|no|not available)",
            r"(?:hindi|regional language)\s+support\s*[:\-]?\s*(yes|available|no|not available)?",
        ],
    )
    if not match:
        return None
    raw = match.group(match.lastindex or 0) or match.group(0)
    value = truthy_from_text(raw)
    if value is None:
        value = any(term in raw.lower() for term in ["hindi", "regional", "available", "yes"])
    return make_field(document, "local_language_support", raw, value, match.start(), match.end())


def extract_technical_solution_description(document: DocumentExtraction) -> Optional[ExtractedField]:
    text = normalized_text(document)
    match = re.search(
        r"(?:technical\s+(?:proposal|solution|approach)\s*[:\-]\s*)(.{40,600})",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    raw = match.group(1).strip()
    return make_field(
        document,
        "technical_solution_description",
        raw,
        raw,
        match.start(1),
        match.end(1),
        exact_label=True,
    )


def normalize_date(value: str) -> str:
    value = value.strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}$", value):
        return value
    if re.match(r"^\d{2}[-/]\d{2}[-/]\d{4}$", value):
        day, month, year = re.split(r"[-/]", value)
        return f"{year}-{month}-{day}"
    return value


FIELD_EXTRACTORS = {
    "years_experience": extract_years,
    "annual_turnover_lakhs": extract_turnover,
    "similar_projects_count": extract_projects,
    "gst_registration": extract_gst,
    "iso_9001_certificate": extract_iso,
    "blacklisted_status": extract_blacklisted,
    "net_worth_positive": extract_net_worth,
    "iso_certificate_valid_until": extract_iso_valid_until,
    "bid_security_valid_until": extract_bid_security_valid_until,
    "data_residency_india": extract_data_residency,
    "technical_solution_description": extract_technical_solution_description,
    "local_language_support": extract_local_language_support,
}
