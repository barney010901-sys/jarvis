"""Deterministic opportunity ranking (section 49):

    score = (expected_value * probability * speed * scalability
             * user_advantage * long_term_value)
            - (legal_risk + financial_risk + reputational_risk + execution_risk) * raw_value

Risk factors are fractions in [0, 1] applied against the raw value they'd
put at stake, not flat subtractions — a 0.1 legal_risk on a $10,000
opportunity matters more than the same 0.1 on a $100 one. This is one
reasonable interpretation of section 49's formula, not the only possible
one; tune the risk weighting here if real usage suggests otherwise.
"""
from __future__ import annotations

from app.business.models import Opportunity


def score_opportunity(o: Opportunity) -> float:
    raw_value = o.expected_value * o.probability * o.speed * o.scalability * o.user_advantage * o.long_term_value
    risk_fraction = o.legal_risk + o.financial_risk + o.reputational_risk + o.execution_risk
    return raw_value - (risk_fraction * raw_value)
