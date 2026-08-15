from pathlib import Path

import cv2
import numpy as np

from mxd_bot.vitals import VitalsMonitor, bar_fill_ratio


def test_vitals_roi_maps_to_calibration_boxes() -> None:
    monitor = VitalsMonitor(
        {
            "enabled": True,
            "hp_roi": [0.1709, 0.9757, 0.0840, 0.0156],
            "mp_roi": [0.2559, 0.9757, 0.0830, 0.0156],
        }
    )
    frame = np.zeros((576, 1024, 3), dtype=np.uint8)
    # 填满标定框，保证 read 成功。
    frame[562:571, 175:261] = (0, 0, 220)
    frame[562:571, 262:347] = (220, 120, 0)
    reading = monitor.read(frame)
    assert reading is not None
    assert reading.hp_box == (175, 562, 260, 570)
    assert reading.mp_box == (262, 562, 346, 570)


def test_bar_fill_ratio_on_synthetic_half_bar() -> None:
    frame = np.zeros((20, 100, 3), dtype=np.uint8)
    frame[:, :50] = (0, 0, 220)
    frame[:, 50:] = (40, 40, 40)
    assert 0.45 <= bar_fill_ratio(frame, (0, 5, 99, 14), "hp") <= 0.55


def test_vitals_monitor_disabled_returns_none() -> None:
    monitor = VitalsMonitor({"enabled": False})
    frame = np.zeros((576, 1024, 3), dtype=np.uint8)
    assert monitor.read(frame) is None


def test_vitals_monitor_reads_full_reference_image() -> None:
    path = Path("assets/vitals_full_sample.png")
    if not path.exists():
        path = Path("captures/_full_vitals.png")
    if not path.exists():
        return

    frame = cv2.imread(str(path))
    assert frame is not None
    monitor = VitalsMonitor(
        {
            "enabled": True,
            "hp_roi": [0.1709, 0.9757, 0.0840, 0.0156],
            "mp_roi": [0.2559, 0.9757, 0.0830, 0.0156],
        }
    )
    reading = monitor.read(frame)
    assert reading is not None
    assert reading.hp_ratio >= 0.90
    assert reading.mp_ratio >= 0.90
