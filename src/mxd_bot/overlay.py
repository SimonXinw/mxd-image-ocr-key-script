from __future__ import annotations

from typing import Any

import cv2
import numpy as np

from mxd_bot.types import Box, Decision


def annotate_frame(
    frame: np.ndarray,
    detections: list[Box],
    player: Box | None,
    decision: Decision,
    fps: float,
    paused: bool,
) -> np.ndarray:
    canvas = frame.copy()

    for box in detections:
        color = (0, 255, 255) if box.class_name == "player" else (0, 0, 255)
        cv2.rectangle(canvas, (box.left, box.top), (box.right, box.bottom), color, 2)
        cv2.putText(
            canvas,
            f"{box.class_name} {box.confidence:.2f}",
            (box.left, max(15, box.top - 5)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            color,
            1,
        )

    if player is not None:
        player_x, player_y = player.center
        cv2.circle(canvas, (player_x, player_y), 5, (0, 255, 0), -1)

    status = "PAUSED" if paused else decision.action.value
    cv2.putText(
        canvas,
        f"{status} | FPS {fps:.1f}",
        (10, 25),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (0, 255, 0),
        2,
    )
    return canvas


def bgr_to_rgb(frame: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
