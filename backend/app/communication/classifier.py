"""Heuristic keyword classification (section 31/37) — deliberately not an
LLM call, for the same reason `CorrectionDetector` isn't: classifying
every incoming message via Claude would itself be an avoidable request
(2E), and the categories/intents this needs to distinguish are narrow
enough that keyword matching is a reasonable, fast, free first pass.
Known limitation: differently-worded messages can be misclassified as
UNKNOWN — which is the safe direction (section 31: UNKNOWN_REQUEST -> ASK).
"""
from __future__ import annotations

from app.communication.models import Category

_CATEGORY_KEYWORDS: dict[Category, tuple[str, ...]] = {
    Category.CLIENT: ("project", "invoice", "deliverable", "quote", "proposal"),
    Category.BUSINESS: ("contract", "partnership", "vendor", "supplier"),
    Category.IMPORTANT: ("urgent", "asap", "deadline", "emergency"),
    Category.LOW_PRIORITY: ("newsletter", "unsubscribe", "fyi", "no action needed"),
}

# Intents from section 31's example policy table.
AUTO_INTENTS = ("routine_reply", "meeting_confirmation", "standard_follow_up")
ASK_INTENTS = ("new_price", "contract", "major_commitment", "sensitive_topic", "unknown_request")

_INTENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "meeting_confirmation": ("confirm the meeting", "see you at", "calendar invite", "schedule a call"),
    "standard_follow_up": ("following up", "checking in", "any update", "just circling back"),
    "routine_reply": ("thanks", "thank you", "got it", "sounds good", "noted", "will do"),
    "new_price": ("price", "quote", "cost", "invoice", "how much"),
    "contract": ("contract", "agreement", "sign", "terms and conditions"),
    "major_commitment": ("guarantee", "promise", "commit to", "deadline extension"),
    "sensitive_topic": ("lawsuit", "legal action", "complaint", "refund dispute", "angry", "furious"),
}


def classify_category(text: str) -> Category:
    lowered = text.lower()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        if any(k in lowered for k in keywords):
            return category
    return Category.UNKNOWN


def classify_intent(text: str) -> str:
    lowered = text.lower()
    # ASK-worthy intents are checked first: "thanks for the contract" should
    # still surface as a contract-adjacent message, not a routine reply.
    for intent in ASK_INTENTS[:-1]:  # exclude the unknown_request fallback
        if any(k in lowered for k in _INTENT_KEYWORDS.get(intent, ())):
            return intent
    for intent in AUTO_INTENTS:
        if any(k in lowered for k in _INTENT_KEYWORDS.get(intent, ())):
            return intent
    return "unknown_request"


def risk_for_intent(intent: str) -> tuple[str, bool]:
    """(risk, reversible) fed into a PolicyRequest — AUTO_INTENTS are low
    risk (so the default autonomy level auto-approves them); everything
    else is medium risk (so it's asked unless a pre-approval policy or a
    higher autonomy level says otherwise)."""
    if intent in AUTO_INTENTS:
        return "low", True
    return "medium", True
