"""Real, unauthenticated GitHub repository search (section 20) — no token
required, subject to GitHub's low unauthenticated rate limit (10 req/min).

This session's own outbound proxy blocks generic (non repo-scoped) GitHub
API access (confirmed: `GET api.github.com/search/repositories` returns
403 "GitHub access is not enabled for this session" here) — so this code
is real and correct for an unrestricted deployment, but its live network
call is NOT_TESTED in this sandbox. See docs/PHASE_3.md.
"""
from __future__ import annotations

import httpx

GITHUB_SEARCH_URL = "https://api.github.com/search/repositories"


class GitHubSearchError(Exception):
    pass


class GitHubSearchClient:
    def __init__(self, timeout: float = 10.0) -> None:
        self._timeout = timeout

    async def search_repositories(self, query: str, limit: int = 5) -> list[dict]:
        params = {"q": query, "per_page": min(max(limit, 1), 20), "sort": "stars", "order": "desc"}
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "jarvis-capability-discovery"}
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(GITHUB_SEARCH_URL, params=params, headers=headers)
        except httpx.HTTPError as exc:
            raise GitHubSearchError(f"GitHub search request failed: {exc}") from exc

        if response.status_code != 200:
            raise GitHubSearchError(f"GitHub search returned {response.status_code}: {response.text[:200]}")

        data = response.json()
        return [
            {
                "name": item["full_name"],
                "url": item["html_url"],
                "description": item.get("description") or "",
                "stars": item.get("stargazers_count", 0),
                "language": item.get("language"),
                "license": (item.get("license") or {}).get("spdx_id"),
                "archived": item.get("archived", False),
                "updated_at": item.get("updated_at"),
            }
            for item in data.get("items", [])[:limit]
        ]
