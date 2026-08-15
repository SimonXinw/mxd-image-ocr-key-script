from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class VitalsReading:
    hp_ratio: float
    mp_ratio: float
    hp_box: tuple[int, int, int, int]
    mp_box: tuple[int, int, int, int]


class VitalsMonitor:
    """用固定 ROI 颜色比例读取血蓝条，低于阈值则按药。"""

    def __init__(self, vitals_config: dict[str, Any] | None) -> None:
        config = vitals_config or {}
        self.enabled = bool(config.get("enabled", False))
        self.show_overlay = bool(config.get("show_overlay", True))
        self.hp_threshold = float(config.get("hp_threshold", 0.40))
        self.mp_threshold = float(config.get("mp_threshold", 0.30))
        self.cooldown_seconds = float(config.get("cooldown_seconds", 1.0))
        self.hp_roi = _as_ratio4(config.get("hp_roi"))
        self.mp_roi = _as_ratio4(config.get("mp_roi"))
        self._last_hp_at = 0.0
        self._last_mp_at = 0.0
        self._last_log_at = 0.0

    def read(self, frame: np.ndarray) -> VitalsReading | None:
        if not self.enabled:
            return None
        if self.hp_roi is None or self.mp_roi is None:
            LOGGER.warning("vitals 已启用但未配置 hp_roi / mp_roi")
            return None

        height, width = frame.shape[:2]
        hp_box = _ratio_to_box(self.hp_roi, width, height)
        mp_box = _ratio_to_box(self.mp_roi, width, height)
        return VitalsReading(
            hp_ratio=bar_fill_ratio(frame, hp_box, "hp"),
            mp_ratio=bar_fill_ratio(frame, mp_box, "mp"),
            hp_box=hp_box,
            mp_box=mp_box,
        )

    def tick(self, frame: np.ndarray, controller: Any) -> VitalsReading | None:
        reading = self.read(frame)
        if reading is None:
            return None

        now = time.monotonic()
        if now - self._last_log_at >= 2.0:
            self._last_log_at = now
            LOGGER.info(
                "血蓝 HP=%.0f%% MP=%.0f%%（阈值 HP<%.0f%% / MP<%.0f%%）",
                reading.hp_ratio * 100,
                reading.mp_ratio * 100,
                self.hp_threshold * 100,
                self.mp_threshold * 100,
            )

        if reading.hp_ratio < self.hp_threshold and now - self._last_hp_at >= self.cooldown_seconds:
            self._use_potion(controller, "hp_potion", reading.hp_ratio)
            self._last_hp_at = now

        if reading.mp_ratio < self.mp_threshold and now - self._last_mp_at >= self.cooldown_seconds:
            self._use_potion(controller, "mp_potion", reading.mp_ratio)
            self._last_mp_at = now

        return reading

    @staticmethod
    def _use_potion(controller: Any, key_name: str, ratio: float) -> None:
        LOGGER.info("准备喝药 %s ratio=%.2f", key_name, ratio)
        controller.use_consumable(key_name)


def bar_fill_ratio(
    frame: np.ndarray,
    box: tuple[int, int, int, int],
    kind: str,
) -> float:
    """统计 ROI 内有色列占比；框必须覆盖整条轨道（含空段）。"""
    left, top, right, bottom = box
    height, width = frame.shape[:2]
    left = max(0, min(left, width - 1))
    right = max(left, min(right, width - 1))
    top = max(0, min(top, height - 1))
    bottom = max(top, min(bottom, height - 1))
    roi = frame[top : bottom + 1, left : right + 1]
    if roi.size == 0:
        return 0.0

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    if kind == "hp":
        mask = cv2.bitwise_or(
            cv2.inRange(hsv, (0, 60, 60), (12, 255, 255)),
            cv2.inRange(hsv, (160, 60, 60), (180, 255, 255)),
        )
    else:
        mask = cv2.inRange(hsv, (90, 60, 60), (135, 255, 255))

    col_height = mask.shape[0]
    filled = (mask > 0).sum(axis=0) > (col_height * 0.35)
    if filled.size == 0:
        return 0.0
    return float(filled.mean())


def _as_ratio4(raw: object) -> tuple[float, float, float, float] | None:
    if raw is None:
        return None
    values = list(raw)
    if len(values) != 4:
        raise ValueError("vitals ROI 必须是 [left, top, width, height] 四个相对比例")
    left, top, width, height = (float(values[0]), float(values[1]), float(values[2]), float(values[3]))
    return left, top, width, height


def _ratio_to_box(
    ratio: tuple[float, float, float, float],
    frame_width: int,
    frame_height: int,
) -> tuple[int, int, int, int]:
    left_r, top_r, width_r, height_r = ratio
    left = round(frame_width * left_r)
    top = round(frame_height * top_r)
    right = round(frame_width * (left_r + width_r)) - 1
    bottom = round(frame_height * (top_r + height_r)) - 1
    return left, top, max(left, right), max(top, bottom)
