from __future__ import annotations

import ctypes
import logging
import time
from typing import Any

import cv2

from mxd_bot.capture import WindowCapture
from mxd_bot.decision import DecisionEngine
from mxd_bot.detector import YoloDetector
from mxd_bot.input_controller import InputController
from mxd_bot.player_locator import PlayerLocator
from mxd_bot.types import Box, Decision

LOGGER = logging.getLogger(__name__)
VK_F8 = 0x77
VK_F9 = 0x78


def run_bot(config: dict[str, Any]) -> None:
    behavior = config["behavior"]
    profile_name = behavior["profile"]
    profile = config["profiles"][profile_name]
    monster_classes = set(config["model"]["monster_classes"])

    detector = YoloDetector(config["model"])
    player_locator = PlayerLocator(config["player"], config["model"]["player_class"])
    decision_engine = DecisionEngine(behavior, profile)
    controller = InputController(behavior, profile)
    capture = WindowCapture(
        config["window"]["title_contains"],
        config["window"].get("capture_region"),
    )

    LOGGER.info(
        "职业=%s，dry_run=%s；F8 暂停/继续，F9 或 Ctrl+C 退出",
        profile_name,
        behavior["dry_run"],
    )
    _countdown(float(behavior["startup_delay_seconds"]))
    paused = False
    last_frame_at = time.monotonic()
    fps = 0.0

    try:
        while True:
            if _key_pressed(VK_F9):
                LOGGER.info("收到 F9，正在停止")
                break

            if _key_pressed(VK_F8):
                paused = not paused
                controller.release_all()
                LOGGER.info("状态：%s", "已暂停" if paused else "运行中")

            frame = capture.grab()
            detections = detector.detect(frame)
            player = player_locator.locate(frame, detections)
            monsters = [box for box in detections if box.class_name in monster_classes]
            decision = decision_engine.decide(player, monsters)

            if not paused:
                controller.execute(decision)
                controller.cast_due_buffs()

            now = time.monotonic()
            elapsed = now - last_frame_at
            if elapsed > 0:
                fps = fps * 0.9 + (1 / elapsed) * 0.1
            last_frame_at = now

            if behavior["debug_window"]:
                _show_debug(frame, detections, player, decision, fps, paused)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            time.sleep(float(behavior["loop_interval_seconds"]))
    finally:
        controller.release_all()
        capture.close()
        cv2.destroyAllWindows()


def _show_debug(
    frame: Any,
    detections: list[Box],
    player: Box | None,
    decision: Decision,
    fps: float,
    paused: bool,
) -> None:
    for box in detections:
        color = (0, 255, 255) if box.class_name == "player" else (0, 0, 255)
        cv2.rectangle(frame, (box.left, box.top), (box.right, box.bottom), color, 2)
        cv2.putText(
            frame,
            f"{box.class_name} {box.confidence:.2f}",
            (box.left, max(15, box.top - 5)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            color,
            1,
        )

    if player is not None:
        player_x, player_y = player.center
        cv2.circle(frame, (player_x, player_y), 5, (0, 255, 0), -1)

    status = "PAUSED" if paused else decision.action.value
    cv2.putText(
        frame,
        f"{status} | FPS {fps:.1f} | F8 pause | F9 stop",
        (10, 25),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (0, 255, 0),
        2,
    )
    cv2.imshow("MXD Vision Debug", frame)


def _key_pressed(virtual_key: int) -> bool:
    return bool(ctypes.windll.user32.GetAsyncKeyState(virtual_key) & 1)


def _countdown(seconds: float) -> None:
    deadline = time.monotonic() + seconds
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        LOGGER.info("%.1f 秒后开始，请切换到游戏窗口", remaining)
        time.sleep(min(1.0, remaining))
