from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from backend.models.schemas import Criterion, ExtractedField, Operator


@dataclass
class RuleOutcome:
    matched: bool
    confidence: float
    rule_applied: str
    reasoning: str


class RuleEngine:
    def evaluate(self, criterion: Criterion, field: Optional[ExtractedField]) -> RuleOutcome:
        if field is None or field.normalized_value is None:
            return RuleOutcome(
                matched=False,
                confidence=0.0,
                rule_applied=f"{criterion.field_name} {criterion.operator.value} {criterion.threshold}",
                reasoning="No reliable extracted evidence was found. Human review is required before rejection.",
            )

        value = field.normalized_value
        op = criterion.operator
        threshold = criterion.threshold
        rule = f"{criterion.field_name} {op.value} {threshold}"

        try:
            if op in {Operator.GTE, Operator.LTE, Operator.GT, Operator.LT, Operator.EQ, Operator.BETWEEN}:
                return self._numeric(op, value, threshold, field.confidence, rule)
            if op in {
                Operator.DATE_BEFORE,
                Operator.DATE_AFTER,
                Operator.DATE_ON_OR_BEFORE,
                Operator.DATE_ON_OR_AFTER,
            }:
                return self._date(op, value, threshold, field.confidence, rule)
            if op in {Operator.IS_TRUE, Operator.IS_FALSE}:
                return self._boolean(op, value, field.confidence, rule)
            if op == Operator.CONTAINS:
                matched = str(threshold).lower() in str(value).lower()
                return RuleOutcome(
                    matched=matched,
                    confidence=field.confidence,
                    rule_applied=rule,
                    reasoning=f"Extracted text {'contains' if matched else 'does not contain'} required phrase.",
                )
        except (TypeError, ValueError) as exc:
            return RuleOutcome(
                matched=False,
                confidence=min(field.confidence, 0.65),
                rule_applied=rule,
                reasoning=f"Could not apply rule safely: {exc}. Human review is required.",
            )

        return RuleOutcome(
            matched=False,
            confidence=min(field.confidence, 0.65),
            rule_applied=rule,
            reasoning="Unsupported rule type for deterministic evaluation. Human review is required.",
        )

    def _numeric(self, op: Operator, value: Any, threshold: Any, confidence: float, rule: str) -> RuleOutcome:
        actual = float(value)
        if op == Operator.BETWEEN:
            low, high = threshold or [None, None]
            matched = float(low) <= actual <= float(high)
            reasoning = f"Extracted numeric value {actual:g} is {'inside' if matched else 'outside'} range {low}-{high}."
            return RuleOutcome(matched, confidence, rule, reasoning)

        expected = float(threshold)
        checks = {
            Operator.GTE: actual >= expected,
            Operator.LTE: actual <= expected,
            Operator.GT: actual > expected,
            Operator.LT: actual < expected,
            Operator.EQ: actual == expected,
        }
        matched = checks[op]
        reasoning = (
            f"Extracted numeric value {actual:g} "
            f"{'satisfies' if matched else 'does not satisfy'} rule {op.value} {expected:g}."
        )
        return RuleOutcome(matched, confidence, rule, reasoning)

    def _date(self, op: Operator, value: Any, threshold: Any, confidence: float, rule: str) -> RuleOutcome:
        actual = parse_date(value)
        expected = parse_date(threshold)
        checks = {
            Operator.DATE_BEFORE: actual < expected,
            Operator.DATE_AFTER: actual > expected,
            Operator.DATE_ON_OR_BEFORE: actual <= expected,
            Operator.DATE_ON_OR_AFTER: actual >= expected,
        }
        matched = checks[op]
        reasoning = (
            f"Extracted date {actual.date().isoformat()} "
            f"{'satisfies' if matched else 'does not satisfy'} rule against {expected.date().isoformat()}."
        )
        return RuleOutcome(matched, confidence, rule, reasoning)

    def _boolean(self, op: Operator, value: Any, confidence: float, rule: str) -> RuleOutcome:
        actual = coerce_bool(value)
        expected = op == Operator.IS_TRUE
        matched = actual is expected
        reasoning = (
            f"Extracted boolean value is {actual}; "
            f"required value is {expected}."
        )
        return RuleOutcome(matched, confidence, rule, reasoning)


def coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    value_text = str(value).strip().lower()
    if value_text in {"true", "yes", "y", "valid", "available", "registered", "positive", "certified"}:
        return True
    if value_text in {"false", "no", "n", "invalid", "not available", "negative", "not certified"}:
        return False
    raise ValueError(f"Cannot coerce {value!r} to boolean")


def parse_date(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    value_text = str(value).strip()
    formats = [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%d %b %Y",
        "%d %B %Y",
        "%b %d %Y",
        "%B %d %Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(value_text, fmt)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date {value!r}")

