"""Permission modes: Think, Edit, Act."""

from enum import Enum


class Mode(Enum):
    """Defines how much freedom the AI backend has."""

    THINK = "think"  # Read, analyze, plan — no edits, no commands
    EDIT = "edit"  # Modify files in controlled scope — no commands
    ACT = "act"  # Run commands, workflows — highest power, most controlled

    @property
    def can_read(self) -> bool:
        return True

    @property
    def can_edit(self) -> bool:
        return self in (Mode.EDIT, Mode.ACT)

    @property
    def can_execute(self) -> bool:
        return self == Mode.ACT
