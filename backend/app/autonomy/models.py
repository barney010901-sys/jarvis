"""Phase 4's autonomy scale — a DIFFERENT concept from Phase 3's
`app.policy.models.AutonomyLevel`, deliberately kept separate rather than
renumbering or replacing it (see docs/PHASE_4_AUDIT.md §17a):

- `AutonomyLevel` (Phase 3) governs one *action* going through
  `PolicyEngine.evaluate()` — wallet spend, a communication, etc.
- `AutonomyMode` (Phase 4, here) describes the posture of the continuous
  autonomous loop/engines as a whole (research, learning, monitoring...).

They compose: an engine running in AUTONOMOUS mode still has every
individual policy-gated action (wallet, communication, self-modification)
evaluated by the existing `PolicyEngine` exactly as before — this mode
does not bypass that gate. `HUMAN_GATED` exists as an available, non-
default mode for a user who wants it for a specific period/objective; the
user has explicitly said not to default the system to it (2026-09-02).
"""
from __future__ import annotations

from enum import IntEnum


class AutonomyMode(IntEnum):
    OBSERVE = 0
    ADVISE = 1
    ASSIST = 2
    AUTONOMOUS = 3
    SUPERVISED_AUTONOMY = 4
    HUMAN_GATED = 5


DEFAULT_AUTONOMY_MODE = AutonomyMode.AUTONOMOUS
