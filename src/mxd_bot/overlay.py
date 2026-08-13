from __future__ import annotations

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
        # 人物由最终定位结果统一绘制，怪物保留 YOLO 原始检测框。
        if box.class_name == "player":
            continue

        track_label = f" #{box.track_id}" if box.track_id is not None else ""
        _draw_box(
            canvas,
            box,
            (0, 0, 255),
            f"YOLO mob{track_label} {box.confidence:.2f}",
        )

    if player is not None:
        player_color, source_label = _player_style(player.source)
        score_label = f" {player.confidence:.2f}" if player.confidence > 0 else ""
        _draw_box(canvas, player, player_color, f"{source_label} player{score_label}")
        player_x, player_y = player.center
        cv2.circle(canvas, (player_x, player_y), 4, player_color, -1)
        cv2.drawMarker(
            canvas,
            (player_x, player_y),
            player_color,
            markerType=cv2.MARKER_CROSS,
            markerSize=18,
            thickness=1,
        )

    if decision.target is not None:
        target = decision.target
        cv2.rectangle(
            canvas,
            (target.left - 2, target.top - 2),
            (target.right + 2, target.bottom + 2),
            (255, 128, 0),
            2,
        )

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

    _draw_legend(canvas)
    return canvas


def _player_style(source: str) -> tuple[tuple[int, int, int], str]:
    if source == "template":
        return (0, 255, 0), "TEMPLATE"
    if source == "yolo":
        return (0, 255, 255), "YOLO"
    return (160, 160, 160), "CENTER"


def _draw_legend(canvas: np.ndarray) -> None:
    legend = (
        ("TEMPLATE", (0, 255, 0)),
        ("YOLO PLAYER", (0, 255, 255)),
        ("CENTER FALLBACK", (160, 160, 160)),
        ("YOLO MOB", (0, 0, 255)),
        ("TARGET", (255, 128, 0)),
    )
    x = max(10, canvas.shape[1] - 190)
    y = max(20, canvas.shape[0] - len(legend) * 20 - 10)
    for label, color in legend:
        cv2.rectangle(canvas, (x, y - 10), (x + 12, y + 2), color, -1)
        cv2.putText(
            canvas,
            label,
            (x + 18, y + 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            color,
            1,
        )
        y += 20


def _draw_box(canvas: np.ndarray, box: Box, color: tuple[int, int, int], label: str) -> None:
    left = max(0, box.left)
    top = max(0, box.top)
    right = max(left + 1, box.right)
    bottom = max(top + 1, box.bottom)
    cv2.rectangle(canvas, (left, top), (right, bottom), color, 2)
    cv2.putText(
        canvas,
        label,
        (left, max(15, top - 5)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.45,
        color,
        1,
    )


def bgr_to_rgb(frame: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
