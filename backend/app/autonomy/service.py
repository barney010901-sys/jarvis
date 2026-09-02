"""AutonomyModeService: get/set the Phase 4 autonomy posture. Reuses the
existing `preferences` table (via `ProfileStore`) exactly the way Phase
3's `PolicyEngine.autonomy_level()` does — no new table needed for this.
"""
from __future__ import annotations

from app.autonomy.models import DEFAULT_AUTONOMY_MODE, AutonomyMode
from app.profile.interface import ProfileStore

_AUTONOMY_MODE_PREFERENCE_KEY = "autonomy_mode"


class AutonomyModeService:
    def __init__(self, profile_store: ProfileStore) -> None:
        self._profile = profile_store

    async def get_mode(self) -> AutonomyMode:
        pref = await self._profile.get_preference(_AUTONOMY_MODE_PREFERENCE_KEY)
        if pref is None:
            return DEFAULT_AUTONOMY_MODE
        try:
            return AutonomyMode(int(pref.value))
        except (TypeError, ValueError):
            return DEFAULT_AUTONOMY_MODE

    async def set_mode(self, mode: AutonomyMode) -> None:
        await self._profile.set_preference(_AUTONOMY_MODE_PREFERENCE_KEY, int(mode))
