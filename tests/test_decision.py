import unittest

from mxd_bot.decision import DecisionEngine
from mxd_bot.types import ActionType, Box


BEHAVIOR = {
    "target_vertical_tolerance": 110,
    "jump_when_target_above_pixels": 45,
    "patrol_switch_seconds": 2.5,
}
PROFILE = {"attack_range_pixels": 150}


def make_box(class_name: str, center_x: int, center_y: int) -> Box:
    return Box(
        class_name=class_name,
        confidence=0.9,
        left=center_x - 10,
        top=center_y - 10,
        right=center_x + 10,
        bottom=center_y + 10,
    )


class DecisionEngineTest(unittest.TestCase):
    def test_idle_when_player_is_missing(self) -> None:
        engine = DecisionEngine(BEHAVIOR, PROFILE)

        decision = engine.decide(None, [make_box("mob", 200, 100)])

        self.assertEqual(decision.action, ActionType.IDLE)

    def test_attacks_nearby_monster(self) -> None:
        engine = DecisionEngine(BEHAVIOR, PROFILE)
        player = make_box("player", 100, 100)

        decision = engine.decide(player, [make_box("mob", 220, 105)])

        self.assertEqual(decision.action, ActionType.ATTACK)
        self.assertEqual(decision.horizontal_distance, 120)

    def test_moves_toward_distant_monster(self) -> None:
        engine = DecisionEngine(BEHAVIOR, PROFILE)
        player = make_box("player", 300, 100)

        decision = engine.decide(player, [make_box("mob", 50, 100)])

        self.assertEqual(decision.action, ActionType.MOVE_LEFT)

    def test_jumps_toward_monster_on_higher_platform(self) -> None:
        engine = DecisionEngine(BEHAVIOR, PROFILE)
        player = make_box("player", 100, 150)

        decision = engine.decide(player, [make_box("mob", 220, 90)])

        self.assertEqual(decision.action, ActionType.JUMP_RIGHT)

    def test_ignores_monster_outside_vertical_tolerance(self) -> None:
        engine = DecisionEngine(BEHAVIOR, PROFILE)
        player = make_box("player", 100, 300)

        decision = engine.decide(player, [make_box("mob", 120, 50)])

        self.assertEqual(decision.action, ActionType.PATROL_RIGHT)


if __name__ == "__main__":
    unittest.main()
