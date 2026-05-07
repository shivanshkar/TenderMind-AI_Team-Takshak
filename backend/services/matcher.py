import math
import re
from difflib import SequenceMatcher
from typing import Dict, List, Optional
from uuid import uuid4

from backend.models.schemas import (
    Bidder,
    Criterion,
    CriterionEvaluation,
    Decision,
    EvaluationResult,
    ExtractedField,
    Operator,
)
from backend.services.confidence_engine import ConfidenceEngine
from backend.services.rule_engine import RuleEngine


class SemanticMatcher:
    def __init__(self) -> None:
        self.model = None
        try:
            from sentence_transformers import SentenceTransformer

            self.model = SentenceTransformer("all-MiniLM-L6-v2")
        except Exception:
            self.model = None

    def similarity(self, left: str, right: str) -> float:
        left = left or ""
        right = right or ""
        if not left.strip() or not right.strip():
            return 0.0
        if self.model:
            embeddings = self.model.encode([left, right], normalize_embeddings=True)
            return float(sum(a * b for a, b in zip(embeddings[0], embeddings[1])))
        return fallback_similarity(left, right)


class MatchingEngine:
    def __init__(self) -> None:
        self.rule_engine = RuleEngine()
        self.semantic_matcher = SemanticMatcher()

    def evaluate(
        self,
        tender_id: str,
        bidder_batch_id: str,
        criteria: List[Criterion],
        bidders: List[Bidder],
    ) -> EvaluationResult:
        evaluations: List[CriterionEvaluation] = []
        for bidder in bidders:
            for criterion in criteria:
                field = bidder.fields.get(criterion.field_name)
                if criterion.operator == Operator.SEMANTIC:
                    evaluations.append(self._evaluate_semantic(bidder, criterion, field))
                else:
                    evaluations.append(self._evaluate_rule(bidder, criterion, field))

        matrix = build_matrix(bidders, criteria, evaluations)
        summary = build_summary(bidders, evaluations, criteria)
        return EvaluationResult(
            evaluation_id=f"eval_{uuid4().hex[:10]}",
            tender_id=tender_id,
            bidder_batch_id=bidder_batch_id,
            criteria=criteria,
            bidders=bidders,
            evaluations=evaluations,
            matrix=matrix,
            summary=summary,
        )

    def _evaluate_rule(
        self,
        bidder: Bidder,
        criterion: Criterion,
        field: Optional[ExtractedField],
    ) -> CriterionEvaluation:
        outcome = self.rule_engine.evaluate(criterion, field)
        missing = field is None or field.normalized_value is None
        confidence = min(field.confidence if field else 0.0, outcome.confidence)
        decision = ConfidenceEngine.decision_from_rule(outcome.matched, confidence, missing)
        flagged = ConfidenceEngine.is_flagged(decision, confidence, missing)
        extracted_value = field.normalized_value if field else None
        source_document = field.source_document if field else None
        reasoning = outcome.reasoning
        if decision == Decision.NEEDS_REVIEW:
            reasoning += " Ambiguity is flagged for human validation."
        return CriterionEvaluation(
            bidder_id=bidder.id,
            bidder_name=bidder.name,
            criterion_id=criterion.id,
            criterion_name=criterion.name,
            decision=decision,
            confidence=round(confidence, 3),
            extracted_value=extracted_value,
            source_document=source_document,
            rule_applied=outcome.rule_applied,
            reasoning=reasoning,
            flagged=flagged,
        )

    def _evaluate_semantic(
        self,
        bidder: Bidder,
        criterion: Criterion,
        field: Optional[ExtractedField],
    ) -> CriterionEvaluation:
        if field is None:
            return CriterionEvaluation(
                bidder_id=bidder.id,
                bidder_name=bidder.name,
                criterion_id=criterion.id,
                criterion_name=criterion.name,
                decision=Decision.NEEDS_REVIEW,
                confidence=0.0,
                extracted_value=None,
                source_document=None,
                rule_applied="semantic similarity >= 0.85 pass, 0.72-0.85 review, <0.72 fail",
                reasoning="No evidence text found for semantic comparison. Human review is required.",
                flagged=True,
            )
        evidence = " ".join(
            value
            for value in [field.raw_value, field.source_excerpt]
            if value
        )
        target = " ".join([criterion.description, " ".join(criterion.evidence_keywords)])
        score = self.semantic_matcher.similarity(target, evidence)
        decision = ConfidenceEngine.decision_from_similarity(score)
        return CriterionEvaluation(
            bidder_id=bidder.id,
            bidder_name=bidder.name,
            criterion_id=criterion.id,
            criterion_name=criterion.name,
            decision=decision,
            confidence=round(score, 3),
            extracted_value=field.normalized_value,
            source_document=field.source_document,
            rule_applied="semantic similarity >= 0.85 pass, 0.72-0.85 review, <0.72 fail",
            reasoning=(
                f"Semantic score is {score:.3f}. "
                f"Evidence {'matches' if decision == Decision.PASS else 'does not conclusively match'} the criterion."
            ),
            flagged=decision == Decision.NEEDS_REVIEW,
        )


def fallback_similarity(left: str, right: str) -> float:
    left_tokens = set(tokenize(left))
    right_tokens = set(tokenize(right))
    if not left_tokens or not right_tokens:
        return 0.0
    overlap = len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
    coverage = len(left_tokens & right_tokens) / len(left_tokens)
    sequence = SequenceMatcher(None, left.lower(), right.lower()).ratio()
    if coverage >= 0.8:
        return 0.9
    if coverage >= 0.68:
        return 0.86
    baseline = (0.65 * overlap) + (0.35 * sequence)
    keyword_coverage = (0.9 * coverage) + (0.05 * sequence)
    return min(0.95, max(baseline, keyword_coverage))


def tokenize(value: str) -> List[str]:
    return [token for token in re.findall(r"[a-z0-9]+", value.lower()) if len(token) > 2]


def build_matrix(
    bidders: List[Bidder],
    criteria: List[Criterion],
    evaluations: List[CriterionEvaluation],
) -> List[Dict[str, str]]:
    by_pair = {(item.bidder_id, item.criterion_id): item for item in evaluations}
    rows = []
    for bidder in bidders:
        row: Dict[str, str] = {"Bidder": bidder.name}
        for criterion in criteria:
            evaluation = by_pair[(bidder.id, criterion.id)]
            row[criterion.name] = evaluation.decision.value
        rows.append(row)
    return rows


def build_summary(
    bidders: List[Bidder],
    evaluations: List[CriterionEvaluation],
    criteria: List[Criterion],
) -> Dict[str, Dict[str, float | int | str]]:
    summary: Dict[str, Dict[str, float | int | str]] = {}
    total_weight = sum(criterion.weight for criterion in criteria) or 1.0
    weights = {criterion.id: criterion.weight for criterion in criteria}
    mandatory = {criterion.id: criterion.mandatory for criterion in criteria}
    for bidder in bidders:
        items = [item for item in evaluations if item.bidder_id == bidder.id]
        pass_count = sum(1 for item in items if item.decision == Decision.PASS)
        fail_count = sum(1 for item in items if item.decision == Decision.FAIL)
        review_count = sum(1 for item in items if item.decision == Decision.NEEDS_REVIEW)
        mandatory_fail_count = sum(
            1 for item in items if item.decision == Decision.FAIL and mandatory.get(item.criterion_id, True)
        )
        mandatory_review_count = sum(
            1 for item in items if item.decision == Decision.NEEDS_REVIEW and mandatory.get(item.criterion_id, True)
        )
        weighted_score = 0.0
        for item in items:
            if item.decision == Decision.PASS:
                weighted_score += weights.get(item.criterion_id, 1.0)
            elif item.decision == Decision.NEEDS_REVIEW:
                weighted_score += weights.get(item.criterion_id, 1.0) * 0.5
        score = round((weighted_score / total_weight) * 100, 2)
        if mandatory_fail_count:
            recommendation = "NOT_QUALIFIED"
        elif mandatory_review_count:
            recommendation = "REVIEW_REQUIRED"
        else:
            recommendation = "QUALIFIED"
        summary[bidder.name] = {
            "pass": pass_count,
            "fail": fail_count,
            "needs_review": review_count,
            "mandatory_fail": mandatory_fail_count,
            "mandatory_needs_review": mandatory_review_count,
            "score_percent": score if math.isfinite(score) else 0.0,
            "recommendation": recommendation,
        }
    return summary
