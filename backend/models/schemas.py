from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

from pydantic import BaseModel, Field


class Decision(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class DataType(str, Enum):
    NUMBER = "number"
    TEXT = "text"
    DATE = "date"
    BOOLEAN = "boolean"


class Operator(str, Enum):
    GTE = ">="
    LTE = "<="
    GT = ">"
    LT = "<"
    EQ = "=="
    BETWEEN = "between"
    CONTAINS = "contains"
    DATE_BEFORE = "date_before"
    DATE_AFTER = "date_after"
    DATE_ON_OR_BEFORE = "date_on_or_before"
    DATE_ON_OR_AFTER = "date_on_or_after"
    IS_TRUE = "is_true"
    IS_FALSE = "is_false"
    SEMANTIC = "semantic"


Threshold = Optional[Union[str, float, int, bool, List[Union[str, float, int]]]]


class Criterion(BaseModel):
    id: str = Field(default_factory=lambda: f"criterion_{uuid4().hex[:10]}")
    name: str
    description: str
    field_name: str
    data_type: DataType
    operator: Operator
    threshold: Threshold = None
    unit: Optional[str] = None
    mandatory: bool = True
    weight: float = 1.0
    evidence_keywords: List[str] = Field(default_factory=list)
    source_excerpt: Optional[str] = None


class ExtractedField(BaseModel):
    name: str
    raw_value: Optional[str] = None
    normalized_value: Optional[Any] = None
    confidence: float = Field(ge=0.0, le=1.0)
    source_document: Optional[str] = None
    source_excerpt: Optional[str] = None


class DocumentExtraction(BaseModel):
    file_name: str
    parser: str
    text: str
    confidence: float = Field(ge=0.0, le=1.0)


class Bidder(BaseModel):
    id: str = Field(default_factory=lambda: f"bidder_{uuid4().hex[:10]}")
    name: str
    documents: List[DocumentExtraction] = Field(default_factory=list)
    fields: Dict[str, ExtractedField] = Field(default_factory=dict)


class CriterionEvaluation(BaseModel):
    bidder_id: str
    bidder_name: str
    criterion_id: str
    criterion_name: str
    decision: Decision
    confidence: float = Field(ge=0.0, le=1.0)
    extracted_value: Optional[Any] = None
    source_document: Optional[str] = None
    rule_applied: str
    reasoning: str
    flagged: bool = False


class EvaluationResult(BaseModel):
    evaluation_id: str
    tender_id: str
    bidder_batch_id: str
    criteria: List[Criterion]
    bidders: List[Bidder]
    evaluations: List[CriterionEvaluation]
    matrix: List[Dict[str, Any]]
    summary: Dict[str, Any]
    report_json_path: Optional[str] = None
    report_html_path: Optional[str] = None


class UploadResponse(BaseModel):
    id: str
    filename: str
    path: str
    message: str


class CriteriaExtractionRequest(BaseModel):
    tender_id: Optional[str] = None


class EvaluationRequest(BaseModel):
    tender_id: Optional[str] = None
    bidder_batch_id: Optional[str] = None

