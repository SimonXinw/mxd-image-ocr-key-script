from __future__ import annotations

import ctypes
import logging
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from mxd_bot.capture import WindowCapture

LOGGER = logging.getLogger(__name__)
VK_F9 = 0x78


def save_capture_frame(frame: np.ndarray, output_dir: Path, count: int) -> Path:
    """把当前帧保存到采集目录，返回写入路径。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    milliseconds = int((time.time() % 1) * 1000)
    path = output_dir / f"{timestamp}_{milliseconds:03d}_{count:06d}.png"
    if not cv2.imwrite(str(path), frame):
        raise OSError(f"截图写入失败：{path}")
    return path


def collect_screenshots(config: dict[str, Any]) -> None:
    output_dir = Path(config["collection"]["output_dir"])
    interval = float(config["collection"]["interval_seconds"])
    capture = WindowCapture(
        config["window"]["title_contains"],
        config["window"].get("capture_region"),
    )

    LOGGER.info("3 秒后开始采集；F9 或 Ctrl+C 停止，输出目录：%s", output_dir)
    time.sleep(3)
    next_capture_at = 0.0
    count = 0

    try:
        while True:
            if ctypes.windll.user32.GetAsyncKeyState(VK_F9) & 1:
                break

            now = time.monotonic()
            frame = capture.grab()
            if now >= next_capture_at:
                save_capture_frame(frame, output_dir, count)
                count += 1
                next_capture_at = now + interval

            cv2.putText(
                frame,
                f"captured: {count} | F9 stop",
                (10, 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (0, 255, 0),
                2,
            )
            cv2.imshow("MXD Screenshot Collector", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        capture.close()
        cv2.destroyAllWindows()
        LOGGER.info("采集结束，共保存 %d 张截图", count)
