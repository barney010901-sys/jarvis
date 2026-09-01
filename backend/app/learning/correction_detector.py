"""User correction detection (2I) — deliberately a small heuristic regex
matcher, not NLU. Known limitation: it only catches a few explicit
phrasing patterns ("use X instead of Y", "koristi X umesto Y", "don't use
X, use Y"); anything phrased differently is missed rather than
mis-detected. See docs/PHASE_2.md ("known limitations") — improving this
to real intent detection is future work, not a Phase 2 claim.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_TERM = r"[\w.+#/-]+"

_PATTERNS = [
    # "use X instead of Y" / "koristi X umesto Y"
    re.compile(rf"\b(?:use|koristi)\s+(?P<new>{_TERM})\s+(?:instead of|umesto)\s+(?P<old>{_TERM})", re.IGNORECASE),
    # "don't use X, use Y" / "ne koristi X, koristi Y"
    re.compile(
        rf"(?:don'?t use|ne koristi)\s+(?P<old>{_TERM})\s*,?\s*(?:use|koristi)\s+(?P<new>{_TERM})", re.IGNORECASE
    ),
]


@dataclass
class CorrectionCandidate:
    old_term: str
    new_term: str
    raw_text: str
    confidence: float = 0.6


class CorrectionDetector:
    def detect(self, text: str) -> CorrectionCandidate | None:
        for pattern in _PATTERNS:
            match = pattern.search(text)
            if match:
                return CorrectionCandidate(old_term=match.group("old"), new_term=match.group("new"), raw_text=text)
        return None
