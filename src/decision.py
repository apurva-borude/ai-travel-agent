"""The final decision object + a builder to assemble it step by step.

The agent collects bits and pieces as it runs (tool outputs, deductions, policy
refs...). A builder fits nicely here - we keep appending to it during the run
and call .build() once at the very end to get the structured output.
"""

from dataclasses import dataclass, field
from typing import List


VALID_DECISIONS = ["Approve", "Partially Approve", "Reject", "Manual Review"]


@dataclass
class Decision:
    claim_id: str
    decision: str
    approved_amount: float
    deducted_amount: float
    currency: str
    missing_documents: List[str]
    policy_references: List[str]
    confidence: float
    explanation: str
    audit_trail: List[dict] = field(default_factory=list)

    def to_dict(self):
        return {
            "claim_id": self.claim_id,
            "decision": self.decision,
            "approved_amount": self.approved_amount,
            "deducted_amount": self.deducted_amount,
            "currency": self.currency,
            "missing_documents": self.missing_documents,
            "policy_references": self.policy_references,
            "confidence": self.confidence,
            "explanation": self.explanation,
            "audit_trail": self.audit_trail,
        }


class DecisionBuilder:
    def __init__(self, claim_id, currency="USD"):
        self._claim_id = claim_id
        self._currency = currency
        self._decision = "Manual Review"   # safe default if nothing sets it
        self._approved = 0.0
        self._deducted = 0.0
        self._missing = []
        self._refs = []
        self._confidence = 0.5
        self._explanation = ""
        self._audit = []

    def decision(self, value):
        if value not in VALID_DECISIONS:
            # don't blow up the whole run on a bad label, just be safe
            value = "Manual Review"
        self._decision = value
        return self

    def amounts(self, approved, deducted):
        self._approved = round(float(approved), 2)
        self._deducted = round(float(deducted), 2)
        return self

    def confidence(self, value):
        # keep it in 0..1 (model gave me 1.7 once lol)
        self._confidence = max(0.0, min(1.0, float(value)))
        return self

    def explanation(self, text):
        self._explanation = text
        return self

    def add_missing(self, doc):
        if doc and doc not in self._missing:
            self._missing.append(doc)
        return self

    def add_policy_ref(self, ref):
        if ref and ref not in self._refs:
            self._refs.append(ref)
        return self

    def log(self, step, tool=None, detail=None):
        """Append an audit-trail entry. This is what gives us the trace of
        what the agent looked at before deciding."""
        self._audit.append({
            "step": step,
            "tool": tool,
            "detail": detail,
        })
        return self

    def build(self) -> Decision:
        return Decision(
            claim_id=self._claim_id,
            decision=self._decision,
            approved_amount=self._approved,
            deducted_amount=self._deducted,
            currency=self._currency,
            missing_documents=self._missing,
            policy_references=self._refs,
            confidence=self._confidence,
            explanation=self._explanation,
            audit_trail=self._audit,
        )
