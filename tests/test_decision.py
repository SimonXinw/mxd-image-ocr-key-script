import unittest

from mxd_bot.decision import DecisionEngine
from mxd_bot.types import ActionType, Box

BEHAVIOR = {
    "target_vertical_tolerance": 110,
    "jump_when_target_above_pixels": 45,
    "patrol_switch_seconds": 2.5,
    "max_chase_horizontal_pixels": 420,
    "target_match_radius_pixels": 120,
    "target_lost_grace_seconds": 0.7,
    "attack_release_margin_pixels": 40,
    "target_acquire_frames": 2,
    "action_confirm_frames": 2,
}
PROFILE = {"attack_range_pixels": 150}

# 锁定新目标要 target_acquire_frames 帧；非攻击动作还要再攒 action_confirm_frames 帧。
FRAMES_TO_LOCK = 2
FRAMES_TO_MOVE = 3


def make_box(class_name: str, center_x: int, center_y: int) -> Box:
    return Box(
        class_name=class_name,
        confidence=0.9,
        left=center_x - 10,
        top=center_y - 10,
        right=center_x + 10,
        bottom=center_y + 10,
    )


def make_grounded_box(
    class_name: str,
    center_x: int,
    bottom: int,
    height: int,
) -> Box:
    """构造不同高度但脚底位置可控的检测框。"""
    return Box(
        class_name=class_name,
        confidence=0.9,
        left=center_x - 10,
        top=bottom - height,
        right=center_x + 10,
        bottom=bottom,
    )


def feed(engine, player, monsters, frames):
    """连续喂同一画面若干帧，返回最后一帧的决策。"""
    decision = engine.decide(player, monsters)

    for _ in range(frames - 1):
        decision = engine.decide(player, monsters)

    return decision


class DecisionEngineTest(unittest.TestCase):
    def test_idle_when_player_is_missing(self) -> None:
        engine = DecisionEngine(BEHAVIOR, PROFILE)

        decision = engine.decide(None, [make_box("mob", 200, 100)])

        self.assertEqual(decision.action, ActionType.IDLE)

    def test_attacks_nearby_monster(self) -> None:
        engine = DecisionEngine(BEHAVIOR, PROFILE)
        player = make_box("player", 100, 100)

        decision = feed(engine, player, [make_box("mob", 220, 105)], FRAMES_TO_LOCK)

        self.assertEqual(decision.action, ActionType.ATTACK)
        self.assertEqual(decision.horizontal_distance, 120)

    def test_moves_toward_distant_monster(self) -> None:
        engine = DecisionEngine(BEHAVIOR, PROFILE)
        player = make_box("player", 300, 100)

        decision = feed(engine, player, [make_box("mob", 50, 100)], FRAMES_TO_MOVE)

        self.assertEqual(decision.action, ActionType.MOVE_LEFT)

    def test_jumps_toward_monster_on_higher_platform(self) -> None:
        engine = DecisionEngine(BEHAVIOR, PROFILE)
        player = make_box("player", 100, 150)

        decision = feed(engine, player, [make_box("mob", 300, 90)], FRAMES_TO_MOVE)

        self.assertEqual(decision.action, ActionType.JUMP_RIGHT)

    def test_attacks_same_platform_monster_with_different_height(self) -> None:
        """同一脚底高度不能因怪物框更高而被误判为上层。"""
        engine = DecisionEngine(BEHAVIOR, PROFILE)
        player = make_grounded_box("player", 100, bottom=200, height=70)
        tall_monster = make_grounded_box("mob", 220, bottom=200, height=340)

        decision = feed(engine, player, [tall_monster], FRAMES_TO_LOCK)

        self.assertEqual(decision.action, ActionType.ATTACK)
        self.assertEqual(decision.vertical_distance, 0)

    def test_jumps_by_ground_height_with_different_box_heights(self) -> None:
        """是否在上层按脚底高度判断，不受角色和怪物框高度影响。"""
        engine = DecisionEngine(BEHAVIOR, PROFILE)
        player = make_grounded_box("player", 100, bottom=200, height=70)
        tall_monster = make_grounded_box("mob", 300, bottom=130, height=220)

        decision = feed(engine, player, [tall_monster], FRAMES_TO_MOVE)

        self.assertEqual(decision.action, ActionType.JUMP_RIGHT)
        self.assertEqual(decision.vertical_distance, -70)

    def test_idles_when_monster_outside_vertical_tolerance(self) -> None:
        """有怪但够不着时站着不动，不要退回巡逻乱跑。"""
        engine = DecisionEngine(BEHAVIOR, PROFILE)
        player = make_box("player", 100, 300)

        decision = feed(engine, player, [make_box("mob", 120, 50)], FRAMES_TO_MOVE)

        self.assertEqual(decision.action, ActionType.IDLE)

    def test_idles_when_monster_beyond_chase_limit(self) -> None:
        engine = DecisionEngine(BEHAVIOR, PROFILE)
        player = make_box("player", 100, 100)

        decision = feed(engine, player, [make_box("mob", 600, 100)], FRAMES_TO_MOVE)

        self.assertEqual(decision.action, ActionType.IDLE)

    def test_patrols_when_no_monster(self) -> None:
        engine = DecisionEngine(BEHAVIOR, PROFILE)
        player = make_box("player", 100, 100)

        decision = feed(engine, player, [], FRAMES_TO_MOVE)

        self.assertEqual(decision.action, ActionType.PATROL_RIGHT)

    def test_keeps_attacking_inside_release_margin(self) -> None:
        """已在攻击时目标略微退出攻击距离，靠迟滞继续打，不要来回走停。"""
        engine = DecisionEngine(BEHAVIOR, PROFILE)
        player = make_box("player", 100, 100)
        feed(engine, player, [make_box("mob", 220, 105)], FRAMES_TO_LOCK)

        # dx=170，超过 attack_range 150 但仍在 150+40 的迟滞范围内
        decision = feed(engine, player, [make_box("mob", 270, 105)], FRAMES_TO_MOVE)

        self.assertEqual(decision.action, ActionType.ATTACK)

    def test_chases_after_target_leaves_release_margin(self) -> None:
        engine = DecisionEngine(BEHAVIOR, PROFILE)
        player = make_box("player", 100, 100)
        feed(engine, player, [make_box("mob", 220, 105)], FRAMES_TO_LOCK)

        # dx=200，已超出 150+40
        decision = feed(engine, player, [make_box("mob", 300, 105)], FRAMES_TO_MOVE)

        self.assertEqual(decision.action, ActionType.MOVE_RIGHT)

    def test_ignores_single_frame_flicker(self) -> None:
        """一闪而过的远处误检不应该把人物拉走。"""
        engine = DecisionEngine(BEHAVIOR, PROFILE)
        player = make_box("player", 300, 100)

        decision = engine.decide(player, [make_box("mob", 50, 100)])

        self.assertEqual(decision.action, ActionType.IDLE)


if __name__ == "__main__":
    unittest.main()
