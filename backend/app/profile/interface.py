from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Any

from app.profile.models import Goal, Interest, Preference, Project, ProfileFact, Workflow


class ProfileStore(ABC):
    # --- profile facts ---
    @abstractmethod
    async def get_fact(self, key: str) -> ProfileFact | None: ...

    @abstractmethod
    async def set_fact(self, key: str, value: Any) -> ProfileFact: ...

    # --- preferences ---
    @abstractmethod
    async def get_preference(self, key: str) -> Preference | None: ...

    @abstractmethod
    async def set_preference(self, key: str, value: Any) -> Preference: ...

    @abstractmethod
    async def list_preferences(self) -> list[Preference]: ...

    # --- projects ---
    @abstractmethod
    async def upsert_project(
        self, slug: str, name: str, goals: list[str] | None = None, technologies: list[str] | None = None
    ) -> Project: ...

    @abstractmethod
    async def get_project(self, slug: str) -> Project | None: ...

    @abstractmethod
    async def list_projects(self, status: str | None = None) -> list[Project]: ...

    @abstractmethod
    async def touch_project(self, slug: str) -> None:
        """Update last_active_at — called whenever the user works on this
        project, so 2K's "automatically prioritize project-relevant
        context" can rank by recency."""

    # --- goals ---
    @abstractmethod
    async def create_goal(
        self, project_slug: str | None, title: str, description: str = "", target_date: date | None = None
    ) -> Goal: ...

    @abstractmethod
    async def list_goals(self, project_slug: str | None = None, status: str | None = None) -> list[Goal]: ...

    @abstractmethod
    async def update_goal_status(self, goal_id: str, status: str) -> None: ...

    # --- interests ---
    @abstractmethod
    async def get_interest(self, topic: str, project_slug: str | None) -> Interest | None: ...

    @abstractmethod
    async def upsert_interest(self, topic: str, project_slug: str | None, score: float, signal_count: int) -> Interest: ...

    @abstractmethod
    async def top_interests(self, project_slug: str | None = None, limit: int = 10) -> list[Interest]: ...

    # --- workflows ---
    @abstractmethod
    async def upsert_workflow(self, name: str, steps: list[str], project_slug: str | None) -> tuple[Workflow, bool]:
        """Returns (workflow, created). `created` is False when an existing
        row's evidence_count was incremented instead."""

    @abstractmethod
    async def set_workflow_confirmed(self, workflow_id: str, confirmed: bool) -> None: ...

    @abstractmethod
    async def list_workflows(self, project_slug: str | None = None, confirmed_only: bool = False) -> list[Workflow]: ...
