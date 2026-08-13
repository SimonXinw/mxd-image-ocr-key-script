from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
from typing import Any

import mss
import numpy as np


class WindowNotFoundError(RuntimeError):
    pass


@dataclass(frozen=True)
class WindowInfo:
    hwnd: int
    title: str
    left: int
    top: int
    width: int
    height: int


class WindowCapture:
    """按窗口标题匹配 HWND，优先 mss 截客户区屏幕区域（黑盒视觉，不注入内存）。"""

    PW_RENDERFULLCONTENT = 2

    def __init__(self, title_contains: str, capture_region: list[int] | None = None) -> None:
        self.title_contains = title_contains.casefold()
        self.capture_region = capture_region
        self._mss = mss.mss()
        self._user32 = ctypes.windll.user32
        self._gdi32 = ctypes.windll.gdi32
        self._last_info: WindowInfo | None = None
        self._last_method = "mss"

        self._user32.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
        self._user32.PrintWindow.restype = wintypes.BOOL
        self._user32.GetDC.argtypes = [wintypes.HWND]
        self._user32.GetDC.restype = wintypes.HDC
        self._user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
        self._user32.ReleaseDC.restype = ctypes.c_int
        self._gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
        self._gdi32.CreateCompatibleDC.restype = wintypes.HDC
        self._gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
        self._gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
        self._gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
        self._gdi32.SelectObject.restype = wintypes.HGDIOBJ
        self._gdi32.BitBlt.argtypes = [
            wintypes.HDC,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.HDC,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.DWORD,
        ]
        self._gdi32.BitBlt.restype = wintypes.BOOL
        self._gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
        self._gdi32.DeleteObject.restype = wintypes.BOOL
        self._gdi32.DeleteDC.argtypes = [wintypes.HDC]
        self._gdi32.DeleteDC.restype = wintypes.BOOL
        self._gdi32.GetDIBits.argtypes = [
            wintypes.HDC,
            wintypes.HBITMAP,
            wintypes.UINT,
            wintypes.UINT,
            ctypes.c_void_p,
            ctypes.c_void_p,
            wintypes.UINT,
        ]
        self._gdi32.GetDIBits.restype = ctypes.c_int

    @property
    def last_info(self) -> WindowInfo | None:
        return self._last_info

    @property
    def last_method(self) -> str:
        return self._last_method

    def describe(self) -> str:
        info = self.resolve_window()
        return (
            f"窗口={info.title!r} hwnd={info.hwnd:#x} "
            f"客户区={info.width}x{info.height}@{info.left},{info.top}"
        )

    def grab(self) -> np.ndarray:
        info = self.resolve_window()
        full_frame = self._grab_client(info)
        return self._crop_region(full_frame, info)

    def resolve_window(self) -> WindowInfo:
        hwnd, title = self._find_hwnd()
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

        info = WindowInfo(
            hwnd=hwnd,
            title=title,
            left=origin.x,
            top=origin.y,
            width=width,
            height=height,
        )
        self._last_info = info
        return info

    def _grab_client(self, info: WindowInfo) -> np.ndarray:
        # 默认 mss：只截屏幕上的游戏客户区，行为更接近普通截屏。
        frame = self._grab_mss(info)
        if frame is not None:
            self._last_method = "mss"
            return frame

        frame = self._grab_printwindow(info)
        if frame is not None:
            self._last_method = "printwindow"
            return frame

        frame = self._grab_bitblt(info)
        if frame is not None:
            self._last_method = "bitblt"
            return frame

        raise RuntimeError("无法抓取游戏窗口画面（mss / PrintWindow / BitBlt 均失败）")

    def _grab_mss(self, info: WindowInfo) -> np.ndarray | None:
        try:
            screenshot = self._mss.grab(
                {
                    "left": info.left,
                    "top": info.top,
                    "width": info.width,
                    "height": info.height,
                }
            )
            frame = np.asarray(screenshot, dtype=np.uint8)[:, :, :3].copy()
            if frame.size == 0 or float(frame.mean()) < 1.0:
                return None
            return frame
        except Exception:
            return None

    def _grab_printwindow(self, info: WindowInfo) -> np.ndarray | None:
        return self._grab_gdi(info, use_printwindow=True)

    def _grab_bitblt(self, info: WindowInfo) -> np.ndarray | None:
        return self._grab_gdi(info, use_printwindow=False)

    def _grab_gdi(self, info: WindowInfo, use_printwindow: bool) -> np.ndarray | None:
        hwnd = info.hwnd
        width = info.width
        height = info.height
        window_dc = self._user32.GetDC(hwnd)
        if not window_dc:
            return None

        memory_dc = self._gdi32.CreateCompatibleDC(window_dc)
        bitmap = self._gdi32.CreateCompatibleBitmap(window_dc, width, height)
        old_bitmap = self._gdi32.SelectObject(memory_dc, bitmap)

        try:
            if use_printwindow:
                ok = bool(
                    self._user32.PrintWindow(hwnd, memory_dc, self.PW_RENDERFULLCONTENT)
                )
            else:
                src_copy = 0x00CC0020
                ok = bool(
                    self._gdi32.BitBlt(memory_dc, 0, 0, width, height, window_dc, 0, 0, src_copy)
                )

            if not ok:
                return None

            frame = self._bitmap_to_bgr(memory_dc, bitmap, width, height)
            if frame is None:
                return None

            # 全黑通常表示 PrintWindow/BitBlt 对该客户端无效
            if float(frame.mean()) < 1.0:
                return None
            return frame
        finally:
            self._gdi32.SelectObject(memory_dc, old_bitmap)
            self._gdi32.DeleteObject(bitmap)
            self._gdi32.DeleteDC(memory_dc)
            self._user32.ReleaseDC(hwnd, window_dc)

    def _bitmap_to_bgr(
        self,
        memory_dc: int,
        bitmap: int,
        width: int,
        height: int,
    ) -> np.ndarray | None:
        class BitmapInfoHeader(ctypes.Structure):
            _fields_ = [
                ("biSize", wintypes.DWORD),
                ("biWidth", wintypes.LONG),
                ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD),
                ("biBitCount", wintypes.WORD),
                ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD),
                ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG),
                ("biClrUsed", wintypes.DWORD),
                ("biClrImportant", wintypes.DWORD),
            ]

        header = BitmapInfoHeader()
        header.biSize = ctypes.sizeof(BitmapInfoHeader)
        header.biWidth = width
        header.biHeight = -height  # top-down
        header.biPlanes = 1
        header.biBitCount = 32
        header.biCompression = 0

        buffer = (ctypes.c_ubyte * (width * height * 4))()
        copied = self._gdi32.GetDIBits(
            memory_dc,
            bitmap,
            0,
            height,
            ctypes.byref(buffer),
            ctypes.byref(header),
            0,
        )
        if copied == 0:
            return None

        bgra = np.frombuffer(buffer, dtype=np.uint8).reshape((height, width, 4))
        return bgra[:, :, :3].copy()

    def _crop_region(self, frame: np.ndarray, info: WindowInfo) -> np.ndarray:
        if self.capture_region is None:
            return frame

        left, top, width, height = (int(value) for value in self.capture_region)
        if width <= 0 or height <= 0:
            raise ValueError("window.capture_region 的 width 和 height 必须大于 0")
        if left < 0 or top < 0:
            raise ValueError("window.capture_region 的 left 和 top 不能小于 0")
        if left + width > info.width or top + height > info.height:
            raise ValueError("window.capture_region 超出了游戏客户区")

        return frame[top : top + height, left : left + width].copy()

    def _find_hwnd(self) -> tuple[int, str]:
        matches: list[tuple[int, str]] = []
        enum_callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

        def enum_callback(hwnd: int, _: int) -> bool:
            if not self._user32.IsWindowVisible(hwnd):
                return True

            title_length = self._user32.GetWindowTextLengthW(hwnd)
            title_buffer = ctypes.create_unicode_buffer(title_length + 1)
            self._user32.GetWindowTextW(hwnd, title_buffer, title_length + 1)
            title = title_buffer.value

            if self.title_contains in title.casefold():
                matches.append((hwnd, title))
                return False
            return True

        callback = enum_callback_type(enum_callback)
        self._user32.EnumWindows(callback, 0)
        if not matches:
            raise WindowNotFoundError(f"找不到标题包含 {self.title_contains!r} 的可见窗口")

        return matches[0]

    def close(self) -> None:
        self._mss.close()

    def __enter__(self) -> WindowCapture:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
