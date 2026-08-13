from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np

from mxd_bot.types import Box


class PlayerLocator:
    def __init__(self, player_config: dict[str, Any], player_class: str) -> None:
        self.mode = str(player_config["locator"])
        self.player_class = player_class
        self.threshold = float(player_config["template_threshold"])
        self.offset_x, self.offset_y = (
            int(value) for value in player_config["template_center_offset"]
        )
        self.fallback_to_frame_center = bool(player_config.get("fallback_to_frame_center", True))
        self.template: np.ndarray | None = None

        template_path = Path(player_config["name_template"])
        if self.mode in {"template", "hybrid"} and template_path.exists():
            self.template = self._load_template(template_path)
        elif self.mode == "template":
            raise FileNotFoundError(f"template 模式需要名字模板：{template_path}")

    def locate(self, frame: np.ndarray, detections: list[Box]) -> Box | None:
        if self.mode in {"template", "hybrid"} and self.template is not None:
            template_player = self._locate_by_template(frame)
            if template_player is not None:
                return template_player

        if self.mode in {"yolo", "hybrid"}:
            players = [box for box in detections if box.class_name == self.player_class]
            if players:
                return max(players, key=lambda box: box.confidence)

        if self.fallback_to_frame_center:
            return self._frame_center_player(frame)

        return None

    def _frame_center_player(self, frame: np.ndarray) -> Box:
        height, width = frame.shape[:2]
        center_x = width // 2
        center_y = height // 2
        return Box(
            class_name=self.player_class,
            confidence=0.0,
            left=center_x - 20,
            top=center_y - 35,
            right=center_x + 20,
            bottom=center_y + 35,
            source="center",
        )

    @staticmethod
    def _load_template(template_path: Path) -> np.ndarray:
        raw = cv2.imread(str(template_path), cv2.IMREAD_UNCHANGED)
        if raw is None:
            raise ValueError(f"无法读取名字模板：{template_path}")

        if raw.ndim == 2:
            gray = raw
        elif raw.ndim == 3 and raw.shape[2] == 4:
            # 带透明通道的截图：先铺到不透明底再转灰，避免 RGBA 导致 shape 拆包失败
            bgr = raw[:, :, :3]
            alpha = raw[:, :, 3:4].astype(np.float32) / 255.0
            background = np.full_like(bgr, 32, dtype=np.float32)
            composed = bgr.astype(np.float32) * alpha + background * (1.0 - alpha)
            gray = cv2.cvtColor(composed.astype(np.uint8), cv2.COLOR_BGR2GRAY)
        elif raw.ndim == 3:
            gray = cv2.cvtColor(raw[:, :, :3], cv2.COLOR_BGR2GRAY)
        else:
            raise ValueError(f"名字模板尺寸异常：{template_path} shape={raw.shape}")

        if gray.size == 0:
            raise ValueError(f"名字模板是空图：{template_path}")

        return gray

    def _locate_by_template(self, frame: np.ndarray) -> Box | None:
        assert self.template is not None
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        template_height, template_width = self.template.shape[:2]
        if gray.shape[0] < template_height or gray.shape[1] < template_width:
            return None

        scores = cv2.matchTemplate(gray, self.template, cv2.TM_CCOEFF_NORMED)
        _, score, _, top_left = cv2.minMaxLoc(scores)
        if score < self.threshold:
            return None

        name_center_x = top_left[0] + template_width // 2
        name_center_y = top_left[1] + template_height // 2
        player_center_x = name_center_x + self.offset_x
        player_center_y = name_center_y + self.offset_y

        return Box(
            class_name=self.player_class,
            confidence=float(score),
            left=player_center_x - 20,
            top=player_center_y - 35,
            right=player_center_x + 20,
            bottom=player_center_y + 35,
            source="template",
        )
