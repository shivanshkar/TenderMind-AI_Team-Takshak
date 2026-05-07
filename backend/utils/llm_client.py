import os
import re
from typing import List

from backend.models.schemas import Criterion, DataType, Operator


class LLMClient:
    """
    Small abstraction around criteria extraction.

    The hackathon prototype defaults to a deterministic mock extractor so it
    runs without API keys. If an LLM provider is later plugged in, keep the
    Pydantic Criterion output contract unchanged.
    """

    def __init__(self) -> None:
        self.provider = "mock"
        if os.getenv("OPENAI_API_KEY"):
            self.provider = "openai_ready"

    def extract_criteria(self, tender_text: str) -> List[Criterion]:
        return self._mock_extract(tender_text)

    def _mock_extract(self, tender_text: str) -> List[Criterion]:
        text = normalize_text(tender_text)
        criteria: List[Criterion] = []

        experience = find_number(
            text,
            [
                r"minimum\s+(\d+(?:\.\d+)?)\s+years?\s+(?:of\s+)?experience",
                r"experience\s*[:\-]\s*(\d+(?:\.\d+)?)\s+years?",
            ],
        )
        if experience is not None:
            criteria.append(
                Criterion(
                    name="Minimum years of experience",
                    description=f"Bidder must have at least {experience:g} years of relevant experience.",
                    field_name="years_experience",
                    data_type=DataType.NUMBER,
                    operator=Operator.GTE,
                    threshold=experience,
                    unit="years",
                    evidence_keywords=["experience", "years"],
                    source_excerpt=excerpt_for(text, "experience"),
                )
            )

        turnover = find_money_lakhs(text)
        if turnover is not None:
            criteria.append(
                Criterion(
                    name="Average annual turnover",
                    description=f"Bidder must have average annual turnover of at least INR {turnover:g} lakh.",
                    field_name="annual_turnover_lakhs",
                    data_type=DataType.NUMBER,
                    operator=Operator.GTE,
                    threshold=turnover,
                    unit="INR lakh",
                    evidence_keywords=["turnover", "annual turnover"],
                    source_excerpt=excerpt_for(text, "turnover"),
                )
            )

        similar_projects = find_number(
            text,
            [
                r"at\s+least\s+(\d+)\s+similar\s+projects?",
                r"minimum\s+(\d+)\s+similar\s+projects?",
            ],
        )
        if similar_projects is not None:
            criteria.append(
                Criterion(
                    name="Similar project experience",
                    description=f"Bidder must have completed at least {int(similar_projects)} similar projects.",
                    field_name="similar_projects_count",
                    data_type=DataType.NUMBER,
                    operator=Operator.GTE,
                    threshold=similar_projects,
                    unit="projects",
                    evidence_keywords=["similar projects", "completed projects"],
                    source_excerpt=excerpt_for(text, "similar"),
                )
            )

        if "gst" in text:
            criteria.append(
                Criterion(
                    name="GST registration",
                    description="Bidder must hold a valid GST registration.",
                    field_name="gst_registration",
                    data_type=DataType.BOOLEAN,
                    operator=Operator.IS_TRUE,
                    threshold=True,
                    evidence_keywords=["gst", "gstin", "registration"],
                    source_excerpt=excerpt_for(text, "gst"),
                )
            )

        if "iso 9001" in text or "iso9001" in text:
            criteria.append(
                Criterion(
                    name="ISO 9001 certification",
                    description="Bidder should provide a valid ISO 9001 quality certification.",
                    field_name="iso_9001_certificate",
                    data_type=DataType.BOOLEAN,
                    operator=Operator.IS_TRUE,
                    threshold=True,
                    evidence_keywords=["iso 9001", "quality certification"],
                    source_excerpt=excerpt_for(text, "iso"),
                )
            )

        if "blacklist" in text or "black listed" in text:
            criteria.append(
                Criterion(
                    name="No blacklisting declaration",
                    description="Bidder must not be currently blacklisted by any government department.",
                    field_name="blacklisted_status",
                    data_type=DataType.BOOLEAN,
                    operator=Operator.IS_FALSE,
                    threshold=False,
                    evidence_keywords=["blacklisted", "debarred"],
                    source_excerpt=excerpt_for(text, "blacklist"),
                )
            )

        if "positive net worth" in text or "net worth" in text:
            criteria.append(
                Criterion(
                    name="Positive net worth",
                    description="Bidder must have positive net worth as per the latest audited financials.",
                    field_name="net_worth_positive",
                    data_type=DataType.BOOLEAN,
                    operator=Operator.IS_TRUE,
                    threshold=True,
                    evidence_keywords=["net worth", "audited financials"],
                    source_excerpt=excerpt_for(text, "net worth"),
                )
            )

        iso_valid_until = find_date_after_phrase(text, ["iso 9001 certificate valid until", "iso certificate valid until"])
        if iso_valid_until is not None:
            criteria.append(
                Criterion(
                    name="ISO certificate validity date",
                    description=f"ISO 9001 certificate must be valid on or after {iso_valid_until}.",
                    field_name="iso_certificate_valid_until",
                    data_type=DataType.DATE,
                    operator=Operator.DATE_ON_OR_AFTER,
                    threshold=iso_valid_until,
                    mandatory=True,
                    evidence_keywords=["iso 9001", "valid until", "certificate"],
                    source_excerpt=excerpt_for(text, "iso 9001 certificate valid until"),
                )
            )

        bid_security_date = find_date_after_phrase(text, ["bid security valid until", "emd valid until"])
        if bid_security_date is not None:
            criteria.append(
                Criterion(
                    name="Bid security validity",
                    description=f"Bid security or EMD must be valid on or after {bid_security_date}.",
                    field_name="bid_security_valid_until",
                    data_type=DataType.DATE,
                    operator=Operator.DATE_ON_OR_AFTER,
                    threshold=bid_security_date,
                    mandatory=True,
                    evidence_keywords=["bid security", "emd", "valid until"],
                    source_excerpt=excerpt_for(text, "bid security"),
                )
            )

        if "data residency" in text or "host data in india" in text:
            criteria.append(
                Criterion(
                    name="India data residency",
                    description="Bidder must commit to hosting and processing tender data within India.",
                    field_name="data_residency_india",
                    data_type=DataType.BOOLEAN,
                    operator=Operator.IS_TRUE,
                    threshold=True,
                    mandatory=True,
                    evidence_keywords=["data residency", "india", "hosting"],
                    source_excerpt=excerpt_for(text, "data residency"),
                )
            )

        if "technical proposal must describe" in text or "cloud-native ai analytics platform" in text:
            criteria.append(
                Criterion(
                    name="Technical solution alignment",
                    description=(
                        "Technical proposal must describe a cloud-native AI analytics platform "
                        "with API integration, role-based access control, and audit reporting."
                    ),
                    field_name="technical_solution_description",
                    data_type=DataType.TEXT,
                    operator=Operator.SEMANTIC,
                    threshold="cloud-native AI analytics platform API integration role-based access control audit reporting",
                    mandatory=True,
                    evidence_keywords=[
                        "cloud-native",
                        "AI analytics",
                        "API integration",
                        "role-based access control",
                        "audit reporting",
                    ],
                    source_excerpt=excerpt_for(text, "technical proposal"),
                )
            )

        if "optional" in text and "local language" in text:
            criteria.append(
                Criterion(
                    name="Local language support",
                    description="Optional: bidder may provide Hindi or regional language support for officer-facing workflows.",
                    field_name="local_language_support",
                    data_type=DataType.BOOLEAN,
                    operator=Operator.IS_TRUE,
                    threshold=True,
                    mandatory=False,
                    weight=0.35,
                    evidence_keywords=["local language", "hindi", "regional language"],
                    source_excerpt=excerpt_for(text, "local language"),
                )
            )

        if not criteria:
            criteria = default_criteria()

        return criteria


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower()).strip()


def find_number(text: str, patterns) -> float | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return float(match.group(1))
    return None


def find_money_lakhs(text: str) -> float | None:
    patterns = [
        r"turnover(?:\s+of)?\s+(?:at\s+least|minimum|>=|not\s+less\s+than)?\s*(?:inr|rs\.?)?\s*(\d+(?:\.\d+)?)\s*(crore|cr|lakh|lakhs|lac|lacs)",
        r"(?:inr|rs\.?)\s*(\d+(?:\.\d+)?)\s*(crore|cr|lakh|lakhs|lac|lacs)\s+(?:average\s+)?annual\s+turnover",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            amount = float(match.group(1))
            unit = match.group(2).lower()
            return amount * 100 if unit in {"crore", "cr"} else amount
    return None


def find_date_after_phrase(text: str, phrases: List[str]) -> str | None:
    for phrase in phrases:
        pattern = rf"{re.escape(phrase)}\s*[:\-]?\s*(\d{{4}}-\d{{2}}-\d{{2}}|\d{{2}}-\d{{2}}-\d{{4}}|\d{{2}}/\d{{2}}/\d{{4}})"
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return normalize_date(match.group(1))
    return None


def normalize_date(value: str) -> str:
    value = value.strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}$", value):
        return value
    if re.match(r"^\d{2}[-/]\d{2}[-/]\d{4}$", value):
        day, month, year = re.split(r"[-/]", value)
        return f"{year}-{month}-{day}"
    return value


def excerpt_for(text: str, keyword: str, radius: int = 120) -> str | None:
    idx = text.find(keyword.lower())
    if idx == -1:
        return None
    start = max(0, idx - radius)
    end = min(len(text), idx + radius)
    return text[start:end].strip()


def default_criteria() -> List[Criterion]:
    return [
        Criterion(
            name="Minimum years of experience",
            description="Bidder must have at least 3 years of relevant experience.",
            field_name="years_experience",
            data_type=DataType.NUMBER,
            operator=Operator.GTE,
            threshold=3,
            unit="years",
            evidence_keywords=["experience", "years"],
        ),
        Criterion(
            name="Average annual turnover",
            description="Bidder must have average annual turnover of at least INR 50 lakh.",
            field_name="annual_turnover_lakhs",
            data_type=DataType.NUMBER,
            operator=Operator.GTE,
            threshold=50,
            unit="INR lakh",
            evidence_keywords=["turnover"],
        ),
        Criterion(
            name="GST registration",
            description="Bidder must hold a valid GST registration.",
            field_name="gst_registration",
            data_type=DataType.BOOLEAN,
            operator=Operator.IS_TRUE,
            threshold=True,
            evidence_keywords=["gst", "gstin"],
        ),
    ]
