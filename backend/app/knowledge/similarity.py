"""Text similarity for knowledge deduplication (2G) — deliberately NOT an
embeddings API call. See docs/DECISIONS.md ("Knowledge similarity without
an embeddings API"): calling an embeddings endpoint for every candidate
would itself be an "avoidable Claude/API request" per 2E's cost hierarchy.
`difflib.SequenceMatcher` is stdlib, free, and good enough to catch
near-duplicate titles/content; pgvector remains the documented upgrade
path (see memory/README.md) if semantic dedup is needed later.
"""
from __future__ import annotations

from difflib import SequenceMatcher

from app.knowledge.models import KnowledgeRecord


def text_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def find_most_similar(
    title: str, content: str, candidates: list[KnowledgeRecord]
) -> tuple[KnowledgeRecord, float] | None:
    """Best-matching candidate by max(title similarity, content similarity),
    or None if `candidates` is empty."""
    best: tuple[KnowledgeRecord, float] | None = None
    for candidate in candidates:
        score = max(text_similarity(title, candidate.title), text_similarity(content, candidate.content))
        if best is None or score > best[1]:
            best = (candidate, score)
    return best
