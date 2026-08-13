from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from mxd_bot.device import resolve_device
from mxd_bot.types import Box


class YoloDetector:
    def __init__(self, model_config: dict[str, Any]) -> None:
        weights = Path(model_config["weights"])
        if not weights.exists():
            raise FileNotFoundError(
                f"找不到模型权重：{weights}。请先训练，再把 best.pt 复制到该位置。"
            )

        from ultralytics import YOLO

        self.model = YOLO(str(weights))
        self.confidence = float(model_config["confidence"])
        self.image_size = int(model_config["image_size"])
        self.device = resolve_device(model_config.get("device", "auto"))
        self.tracking_enabled = bool(model_config.get("tracking_enabled", True))
        self.tracker = str(model_config.get("tracker", "bytetrack.yaml"))

    def detect(self, frame: np.ndarray) -> list[Box]:
        predict_options = {
            "source": frame,
            "conf": self.confidence,
            "imgsz": self.image_size,
            "device": self.device,
            "verbose": False,
        }
        if self.tracking_enabled:
            results = self.model.track(
                **predict_options,
                persist=True,
                tracker=self.tracker,
            )
        else:
            results = self.model.predict(**predict_options)
        result = results[0]
        names = result.names
        detections: list[Box] = []

        for raw_box in result.boxes:
            class_id = int(raw_box.cls.item())
            left, top, right, bottom = raw_box.xyxy[0].tolist()
            track_id = (
                int(raw_box.id.item())
                if raw_box.id is not None
                else None
            )
            detections.append(
                Box(
                    class_name=str(names[class_id]),
                    confidence=float(raw_box.conf.item()),
                    left=round(left),
                    top=round(top),
                    right=round(right),
                    bottom=round(bottom),
                    source="yolo",
                    track_id=track_id,
                )
            )

        return detections
