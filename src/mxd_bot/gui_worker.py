from __future__ import annotations

import logging
import queue
import time
from copy import deepcopy
from typing import Any

from PySide6.QtCore import QThread, Signal

from mxd_bot.capture import WindowCapture, WindowNotFoundError
from mxd_bot.decision import DecisionEngine
from mxd_bot.detector import YoloDetector
from mxd_bot.input_controller import InputController
from mxd_bot.overlay import annotate_frame, bgr_to_rgb
from mxd_bot.player_locator import PlayerLocator

LOGGER = logging.getLogger(__name__)


class BotWorker(QThread):
    frame_ready = Signal(object)
    status_ready = Signal(dict)
    log_ready = Signal(str)
    failed = Signal(str)

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__()
        self._config = deepcopy(config)
        self._running = False
        self._paused = False
        self._stop_requested = False
        self._manual_keys: queue.SimpleQueue[str] = queue.SimpleQueue()

    def request_stop(self) -> None:
        self._stop_requested = True

    def set_paused(self, paused: bool) -> None:
        self._paused = paused

    def request_key(self, key_name: str) -> None:
        self._manual_keys.put(key_name)

    def run(self) -> None:
        config = self._config
        behavior = config["behavior"]
        profile_name = behavior["profile"]
        profile = config["profiles"][profile_name]
        monster_classes = set(config["model"]["monster_classes"])
        target_fps = float(config.get("ui", {}).get("target_fps", 30))
        frame_interval = 1.0 / max(1.0, target_fps)
        preview_fps = float(config.get("ui", {}).get("preview_fps", 15))
        preview_interval = 1.0 / max(1.0, preview_fps)

        detector: YoloDetector | None = None
        controller: InputController | None = None
        capture: WindowCapture | None = None

        try:
            self._emit_log("正在加载 YOLO 模型…")
            detector = YoloDetector(config["model"])
            player_locator = PlayerLocator(config["player"], config["model"]["player_class"])
            decision_engine = DecisionEngine(behavior, profile)
            controller = InputController(behavior, profile)
            capture = WindowCapture(
                config["window"]["title_contains"],
                config["window"].get("capture_region"),
            )
            self._emit_log(capture.describe())
            if capture.last_info is not None:
                controller.set_target_window(capture.last_info.hwnd)

            self._running = True
            self._emit_log(
                f"已启动：profile={profile_name}, dry_run={behavior['dry_run']}, "
                f"auto_attack={behavior.get('auto_attack_enabled', True)}, "
                f"target_fps={target_fps:.0f}, preview_fps={preview_fps:.0f}, "
                f"conf={config['model']['confidence']}"
            )

            last_frame_at = time.monotonic()
            fps = 0.0
            last_diag_at = 0.0
            last_preview_at = 0.0

            while not self._stop_requested:
                loop_started = time.monotonic()
                frame = capture.grab()
                detections = detector.detect(frame)
                player = player_locator.locate(frame, detections)
                monsters = [box for box in detections if box.class_name in monster_classes]
                decision = decision_engine.decide(player, monsters)

                now_mono = time.monotonic()
                if now_mono - last_diag_at >= 2.0:
                    last_diag_at = now_mono
                    top_conf = max((box.confidence for box in detections), default=0.0)
                    if player is None:
                        player_label = "否"
                    else:
                        score = f":{player.confidence:.2f}" if player.confidence > 0 else ""
                        player_label = f"是({player.source}{score})"
                    self._emit_log(
                        f"抓取={capture.last_method} | 检测={len(detections)} "
                        f"人={player_label} 怪={len(monsters)} "
                        f"最高分={top_conf:.3f} | 动作={decision.action.value}"
                    )

                if not self._paused:
                    while not self._manual_keys.empty():
                        controller.press_configured_key(self._manual_keys.get_nowait())
                    controller.execute(decision)
                    controller.cast_due_buffs()
                else:
                    controller.release_all()

                now = time.monotonic()
                elapsed = now - last_frame_at
                if elapsed > 0:
                    fps = fps * 0.9 + (1 / elapsed) * 0.1
                last_frame_at = now

                if now - last_preview_at >= preview_interval:
                    last_preview_at = now
                    annotated = annotate_frame(
                        frame,
                        detections,
                        player,
                        decision,
                        fps,
                        self._paused,
                    )
                    self.frame_ready.emit(bgr_to_rgb(annotated))
                self.status_ready.emit(
                    {
                        "fps": round(fps, 1),
                        "paused": self._paused,
                        "action": decision.action.value,
                        "monsters": len(monsters),
                        "has_player": player is not None,
                        "dry_run": bool(behavior["dry_run"]),
                        "auto_attack": bool(behavior.get("auto_attack_enabled", True)),
                        "input_suspended": controller.input_suspended,
                        "profile": profile_name,
                    }
                )

                sleep_for = frame_interval - (time.monotonic() - loop_started)
                if sleep_for > 0:
                    time.sleep(sleep_for)
        except WindowNotFoundError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            LOGGER.exception("GUI worker failed")
            self.failed.emit(str(exc))
        finally:
            if controller is not None:
                controller.release_all()
            if capture is not None:
                capture.close()
            self._running = False
            self._emit_log("已停止")

    def _emit_log(self, message: str) -> None:
        LOGGER.info(message)
        self.log_ready.emit(message)
