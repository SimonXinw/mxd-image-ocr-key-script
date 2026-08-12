from __future__ import annotations

import time
from typing import Any

from mxd_bot.types import ActionType, Box, Decision


class DecisionEngine:
    def __init__(self, behavior_config: dict[str, Any], profile_config: dict[str, Any]) -> None:
        self.attack_range = int(profile_config["attack_range_pixels"])
        self.vertical_tolerance = int(behavior_config["target_vertical_tolerance"])
        self.jump_above_pixels = int(behavior_config["jump_when_target_above_pixels"])
        self.patrol_switch_seconds = float(behavior_config["patrol_switch_seconds"])
        self._patrol_started_at = time.monotonic()
        self._patrol_right = True

    def decide(
        self,
        player: Box | None,
        monsters: list[Box],
        now: float | None = None,
    ) -> Decision:
        current_time = time.monotonic() if now is None else now
        if player is None:
            return Decision(ActionType.IDLE)

        target = self._select_target(player, monsters)
        if target is None:
            return Decision(self._patrol_action(current_time))

        player_x, player_y = player.center
        target_x, target_y = target.center
        horizontal_distance = target_x - player_x
        vertical_distance = target_y - player_y

        if (
            vertical_distance < -self.jump_above_pixels
            and abs(vertical_distance) <= self.vertical_tolerance
        ):
            action = (
                ActionType.JUMP_RIGHT
                if horizontal_distance >= 0
                else ActionType.JUMP_LEFT
            )
        elif (
            abs(horizontal_distance) <= self.attack_range
            and abs(vertical_distance) <= self.vertical_tolerance
        ):
            action = ActionType.ATTACK
        elif horizontal_distance < 0:
            action = ActionType.MOVE_LEFT
        else:
            action = ActionType.MOVE_RIGHT

        return Decision(action, target, horizontal_distance, vertical_distance)

    def _select_target(self, player: Box, monsters: list[Box]) -> Box | None:
        if not monsters:
            return None

        player_x, player_y = player.center
        reachable = [
            monster
            for monster in monsters
            if abs(monster.center[1] - player_y) <= self.vertical_tolerance
        ]
        if not reachable:
            return None

        return min(
            reachable,
            key=lambda monster: (
                abs(monster.center[0] - player_x)
                + 2 * abs(monster.center[1] - player_y)
            ),
        )

    def _patrol_action(self, now: float) -> ActionType:
        if now - self._patrol_started_at >= self.patrol_switch_seconds:
            self._patrol_started_at = now
            self._patrol_right = not self._patrol_right

        return ActionType.PATROL_RIGHT if self._patrol_right else ActionType.PATROL_LEFT
