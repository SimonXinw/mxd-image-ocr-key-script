from __future__ import annotations

import time
from typing import Any

from mxd_bot.types import ActionType, Box, Decision


class DecisionEngine:
    def __init__(self, behavior_config: dict[str, Any], profile_config: dict[str, Any]) -> None:
        self.attack_range = int(profile_config["attack_range_pixels"])
        self.auto_attack_enabled = bool(
            behavior_config.get("auto_attack_enabled", True)
        )
        self.vertical_tolerance = int(behavior_config["target_vertical_tolerance"])
        self.jump_above_pixels = int(behavior_config["jump_when_target_above_pixels"])
        self.patrol_switch_seconds = float(behavior_config["patrol_switch_seconds"])
        self.target_match_radius = int(
            behavior_config.get("target_match_radius_pixels", 180)
        )
        self.target_lost_grace = float(
            behavior_config.get("target_lost_grace_seconds", 0.4)
        )
        self.attack_release_margin = int(
            behavior_config.get("attack_release_margin_pixels", 35)
        )
        self.action_confirm_frames = int(
            behavior_config.get("action_confirm_frames", 3)
        )
        self.max_chase_horizontal = int(
            behavior_config.get("max_chase_horizontal_pixels", 420)
        )
        self.target_acquire_frames = int(
            behavior_config.get("target_acquire_frames", 2)
        )
        self._patrol_started_at = time.monotonic()
        self._patrol_right = True
        self._locked_target: Box | None = None
        self._locked_track_id: int | None = None
        self._last_target_seen_at = 0.0
        self._candidate_target: Box | None = None
        self._candidate_frames = 0
        self._is_attacking = False
        self._stable_action = ActionType.IDLE
        self._pending_action: ActionType | None = None
        self._pending_action_frames = 0

    def decide(
        self,
        player: Box | None,
        monsters: list[Box],
        now: float | None = None,
    ) -> Decision:
        current_time = time.monotonic() if now is None else now
        if player is None:
            action = self._stabilize_action(ActionType.IDLE)
            return Decision(action)

        target = self._select_target(player, monsters, current_time)
        if target is None:
            # 有怪但不在同一可达高度：站着别乱巡逻
            if monsters:
                action = self._stabilize_action(ActionType.IDLE)
                return Decision(action)
            action = self._stabilize_action(self._patrol_action(current_time))
            return Decision(action)

        player_x, player_y = player.center
        target_x, target_y = target.center
        horizontal_distance = target_x - player_x
        vertical_distance = target_y - player_y
        abs_dx = abs(horizontal_distance)
        abs_dy = abs(vertical_distance)

        attack_limit = (
            self.attack_range + self.attack_release_margin
            if self._is_attacking
            else self.attack_range
        )

        # 已经够近时优先攻击，不要先跳；跳只用于明显在上方且还够不到的怪
        in_attack_band = abs_dx <= attack_limit and abs_dy <= self.vertical_tolerance
        need_jump = (
            vertical_distance < -self.jump_above_pixels
            and abs_dy <= self.vertical_tolerance
            and abs_dx > self.attack_range
        )

        if in_attack_band:
            raw_action = ActionType.ATTACK if self.auto_attack_enabled else ActionType.IDLE
        elif need_jump:
            raw_action = (
                ActionType.JUMP_RIGHT
                if horizontal_distance >= 0
                else ActionType.JUMP_LEFT
            )
        elif horizontal_distance < 0:
            raw_action = ActionType.MOVE_LEFT
        else:
            raw_action = ActionType.MOVE_RIGHT

        action = self._stabilize_action(raw_action)
        self._is_attacking = action == ActionType.ATTACK
        return Decision(action, target, horizontal_distance, vertical_distance)

    def _stabilize_action(self, raw_action: ActionType) -> ActionType:
        """攻击立即响应；离开巡逻也立即响应；其余动作需连续确认。"""
        if raw_action == ActionType.ATTACK:
            self._stable_action = raw_action
            self._pending_action = None
            self._pending_action_frames = 0
            return raw_action

        # 发现目标后不要继续沿用巡逻动作
        if self._stable_action in {
            ActionType.PATROL_LEFT,
            ActionType.PATROL_RIGHT,
        } and raw_action in {
            ActionType.MOVE_LEFT,
            ActionType.MOVE_RIGHT,
            ActionType.JUMP_LEFT,
            ActionType.JUMP_RIGHT,
            ActionType.IDLE,
        }:
            self._stable_action = raw_action
            self._pending_action = None
            self._pending_action_frames = 0
            return raw_action

        if raw_action == self._stable_action:
            self._pending_action = None
            self._pending_action_frames = 0
            return self._stable_action

        if raw_action != self._pending_action:
            self._pending_action = raw_action
            self._pending_action_frames = 1
        else:
            self._pending_action_frames += 1

        if self._pending_action_frames >= max(1, self.action_confirm_frames):
            self._stable_action = raw_action
            self._pending_action = None
            self._pending_action_frames = 0

        return self._stable_action

    def _select_target(
        self,
        player: Box,
        monsters: list[Box],
        now: float,
    ) -> Box | None:
        player_x, player_y = player.center
        reachable = [
            monster
            for monster in monsters
            if abs(monster.center[1] - player_y) <= self.vertical_tolerance
            and abs(monster.center[0] - player_x) <= self.max_chase_horizontal
        ]

        if self._locked_target is not None:
            matched = self._match_locked_target(reachable)
            if matched is not None:
                self._locked_target = matched
                self._locked_track_id = matched.track_id
                self._last_target_seen_at = now
                return matched
            if now - self._last_target_seen_at <= self.target_lost_grace:
                return self._locked_target
            self._clear_locked_target()

        if not reachable:
            self._candidate_target = None
            self._candidate_frames = 0
            return None

        nearest = min(
            reachable,
            key=lambda monster: (
                abs(monster.center[0] - player_x)
                + 2 * abs(monster.center[1] - player_y)
            ),
        )

        if self._is_same_candidate(nearest):
            self._candidate_frames += 1
        else:
            self._candidate_frames = 1
        self._candidate_target = nearest

        # 新目标必须连续检测到几帧才锁定，过滤闪一下的远方误检。
        if self._candidate_frames < max(1, self.target_acquire_frames):
            return None

        self._locked_target = nearest
        self._locked_track_id = nearest.track_id
        self._last_target_seen_at = now
        self._candidate_target = None
        self._candidate_frames = 0
        return nearest

    def _match_locked_target(self, monsters: list[Box]) -> Box | None:
        if not monsters or self._locked_target is None:
            return None

        if self._locked_track_id is not None:
            for monster in monsters:
                if monster.track_id == self._locked_track_id:
                    return monster
            # 旧目标有 ID 时，不能把另一个有 ID 的怪当成它。
            candidates = [monster for monster in monsters if monster.track_id is None]
        else:
            candidates = monsters

        if not candidates:
            return None

        locked_x, locked_y = self._locked_target.center
        matched = min(
            candidates,
            key=lambda monster: (
                abs(monster.center[0] - locked_x)
                + abs(monster.center[1] - locked_y)
            ),
        )
        distance = (
            abs(matched.center[0] - locked_x)
            + abs(matched.center[1] - locked_y)
        )
        return matched if distance <= self.target_match_radius else None

    def _is_same_candidate(self, target: Box) -> bool:
        if self._candidate_target is None:
            return False
        if target.track_id is not None and self._candidate_target.track_id is not None:
            return target.track_id == self._candidate_target.track_id

        old_x, old_y = self._candidate_target.center
        return (
            abs(target.center[0] - old_x) + abs(target.center[1] - old_y)
            <= self.target_match_radius
        )

    def _clear_locked_target(self) -> None:
        self._locked_target = None
        self._locked_track_id = None
        self._candidate_target = None
        self._candidate_frames = 0

    def _patrol_action(self, now: float) -> ActionType:
        if now - self._patrol_started_at >= self.patrol_switch_seconds:
            self._patrol_started_at = now
            self._patrol_right = not self._patrol_right

        return ActionType.PATROL_RIGHT if self._patrol_right else ActionType.PATROL_LEFT
