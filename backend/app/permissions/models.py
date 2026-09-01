from enum import Enum


class PermissionLevel(str, Enum):
    """Every tool declares one of these. See docs/ARCHITECTURE.md ("Security model")."""

    SAFE = "safe"
    SENSITIVE = "sensitive"
