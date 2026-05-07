from backend.models.schemas import Decision


class ConfidenceEngine:
    PASS_THRESHOLD = 0.85
    REVIEW_THRESHOLD = 0.72

    @classmethod
    def decision_from_similarity(cls, score: float) -> Decision:
        if score >= cls.PASS_THRESHOLD:
            return Decision.PASS
        if score >= cls.REVIEW_THRESHOLD:
            return Decision.NEEDS_REVIEW
        return Decision.FAIL

    @classmethod
    def decision_from_rule(
        cls,
        matched: bool,
        evidence_confidence: float,
        missing_evidence: bool = False,
    ) -> Decision:
        if missing_evidence:
            return Decision.NEEDS_REVIEW
        if evidence_confidence >= cls.PASS_THRESHOLD:
            return Decision.PASS if matched else Decision.FAIL
        return Decision.NEEDS_REVIEW

    @classmethod
    def is_flagged(cls, decision: Decision, confidence: float, missing_evidence: bool = False) -> bool:
        return (
            decision == Decision.NEEDS_REVIEW
            or missing_evidence
            or confidence < cls.PASS_THRESHOLD
        )

