from pathlib import Path
from typing import List

from backend.models.schemas import Criterion
from backend.services.document_parser import DocumentParser
from backend.utils.llm_client import LLMClient


class CriteriaExtractor:
    def __init__(self) -> None:
        self.document_parser = DocumentParser()
        self.llm_client = LLMClient()

    def extract(self, tender_path: Path) -> List[Criterion]:
        text, _, _ = self.document_parser.extract_text_from_path(tender_path)
        return self.extract_from_text(text)

    def extract_from_text(self, tender_text: str) -> List[Criterion]:
        return self.llm_client.extract_criteria(tender_text)

