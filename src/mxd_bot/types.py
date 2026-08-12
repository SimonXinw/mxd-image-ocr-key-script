from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class Box:
    class_name: str
    confidence: float
    left: int
    top: int
    right: int
    bottom: int

    @property
    def center(self) -> tuple[int, int]:
        return ((self.left + self.right) // 2, (self.top + self.bottom) // 2)


class ActionType(str, Enum):
    IDLE = "idle"
    MOVE_LEFT = "move_left"
    MOVE_RIGHT = "move_right"
    ATTACK = "attack"
    JUMP_LEFT = "jump_left"
    JUMP_RIGHT = "jump_right"
    PATROL_LEFT = "patrol_left"
    PATROL_RIGHT = "patrol_right"


@dataclass(frozen=True)
class Decision:
    action: ActionType
    target: Box | None = None
    horizontal_distance: int | None = None
    vertical_distance: int | None = None
