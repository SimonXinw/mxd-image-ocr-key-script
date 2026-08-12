from __future__ import annotations

import logging
import time
from typing import Any

from mxd_bot.types import ActionType, Decision

LOGGER = logging.getLogger(__name__)


class InputController:
    def __init__(self, behavior_config: dict[str, Any], profile_config: dict[str, Any]) -> None:
        self.dry_run = bool(behavior_config["dry_run"])
        self.move_pulse = float(behavior_config["move_pulse_seconds"])
        self.patrol_pulse = float(behavior_config["patrol_pulse_seconds"])
        self.jump_cooldown = float(behavior_config["jump_cooldown_seconds"])
        self.attack_key = str(profile_config["attack_key"])
        self.jump_key = str(profile_config["jump_key"])
        self.attack_cooldown = float(profile_config["attack_cooldown_seconds"])
        self.buffs = list(profile_config.get("buffs", []))
        self._last_attack_at = 0.0
        self._last_jump_at = 0.0
        self._last_buff_at: dict[str, float] = {}
        self._last_dry_action: ActionType | None = None

        if not self.dry_run:
            import pydirectinput

            pydirectinput.PAUSE = 0
            pydirectinput.FAILSAFE = True
            self._keyboard = pydirectinput
        else:
            self._keyboard = None

    def execute(self, decision: Decision) -> None:
        now = time.monotonic()
        action = decision.action

        if self.dry_run:
            if action != self._last_dry_action:
                LOGGER.info(
                    "[演练] action=%s dx=%s dy=%s",
                    action.value,
                    decision.horizontal_distance,
                    decision.vertical_distance,
                )
                self._last_dry_action = action
            return

        if action == ActionType.ATTACK:
            if now - self._last_attack_at >= self.attack_cooldown:
                self._press(self.attack_key)
                self._last_attack_at = now
        elif action in {ActionType.MOVE_LEFT, ActionType.MOVE_RIGHT}:
            key = "left" if action == ActionType.MOVE_LEFT else "right"
            self._hold(key, self.move_pulse)
        elif action in {ActionType.PATROL_LEFT, ActionType.PATROL_RIGHT}:
            key = "left" if action == ActionType.PATROL_LEFT else "right"
            self._hold(key, self.patrol_pulse)
        elif action in {ActionType.JUMP_LEFT, ActionType.JUMP_RIGHT}:
            if now - self._last_jump_at >= self.jump_cooldown:
                direction = "left" if action == ActionType.JUMP_LEFT else "right"
                self._jump(direction)
                self._last_jump_at = now

    def cast_due_buffs(self) -> None:
        now = time.monotonic()
        for buff in self.buffs:
            key = str(buff["key"])
            interval = float(buff["interval_seconds"])
            last_cast = self._last_buff_at.get(key, now)
            self._last_buff_at.setdefault(key, now)

            if now - last_cast >= interval:
                if self.dry_run:
                    LOGGER.info("[演练] buff=%s", key)
                else:
                    self._press(key)
                self._last_buff_at[key] = now

    def release_all(self) -> None:
        if self._keyboard is None:
            return

        for key in ("left", "right", self.jump_key, self.attack_key):
            self._keyboard.keyUp(key)

    def _press(self, key: str) -> None:
        assert self._keyboard is not None
        self._keyboard.press(key)

    def _hold(self, key: str, duration: float) -> None:
        assert self._keyboard is not None
        self._keyboard.keyDown(key)
        try:
            time.sleep(duration)
        finally:
            self._keyboard.keyUp(key)

    def _jump(self, direction: str) -> None:
        assert self._keyboard is not None
        self._keyboard.keyDown(direction)
        try:
            time.sleep(0.03)
            self._keyboard.press(self.jump_key)
        finally:
            self._keyboard.keyUp(direction)
