from __future__ import annotations

import ctypes
from ctypes import wintypes
from typing import Any

import mss
import numpy as np


class WindowNotFoundError(RuntimeError):
    pass


class WindowCapture:
    def __init__(self, title_contains: str, capture_region: list[int] | None = None) -> None:
        self.title_contains = title_contains.casefold()
        self.capture_region = capture_region
        self._mss = mss.mss()
        self._user32 = ctypes.windll.user32

    def grab(self) -> np.ndarray:
        region = self._resolve_region()
        screenshot = self._mss.grab(region)
        return np.asarray(screenshot, dtype=np.uint8)[:, :, :3].copy()

    def _resolve_region(self) -> dict[str, int]:
        client_region = self._find_client_region()

        if self.capture_region is None:
            return client_region

        left, top, width, height = (int(value) for value in self.capture_region)
        if width <= 0 or height <= 0:
            raise ValueError("window.capture_region 的 width 和 height 必须大于 0")
        if left < 0 or top < 0:
            raise ValueError("window.capture_region 的 left 和 top 不能小于 0")
        if left + width > client_region["width"] or top + height > client_region["height"]:
            raise ValueError("window.capture_region 超出了游戏客户区")

        return {
            "left": client_region["left"] + left,
            "top": client_region["top"] + top,
            "width": width,
            "height": height,
        }

    def _find_client_region(self) -> dict[str, int]:
        matches: list[int] = []
        enum_callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

        def enum_callback(hwnd: int, _: int) -> bool:
            if not self._user32.IsWindowVisible(hwnd):
                return True

            title_length = self._user32.GetWindowTextLengthW(hwnd)
            title_buffer = ctypes.create_unicode_buffer(title_length + 1)
            self._user32.GetWindowTextW(hwnd, title_buffer, title_length + 1)

            if self.title_contains in title_buffer.value.casefold():
                matches.append(hwnd)
                return False
            return True

        callback = enum_callback_type(enum_callback)
        self._user32.EnumWindows(callback, 0)
        if not matches:
            raise WindowNotFoundError(f"找不到标题包含 {self.title_contains!r} 的可见窗口")

        hwnd = matches[0]
        rect = wintypes.RECT()
        if not self._user32.GetClientRect(hwnd, ctypes.byref(rect)):
            raise RuntimeError("读取游戏客户区尺寸失败")

        origin = wintypes.POINT(0, 0)
        if not self._user32.ClientToScreen(hwnd, ctypes.byref(origin)):
            raise RuntimeError("读取游戏客户区坐标失败")

        width = rect.right - rect.left
        height = rect.bottom - rect.top
        if width <= 0 or height <= 0:
            raise RuntimeError("游戏窗口已最小化或客户区尺寸无效")

        return {"left": origin.x, "top": origin.y, "width": width, "height": height}

    def close(self) -> None:
        self._mss.close()

    def __enter__(self) -> WindowCapture:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
