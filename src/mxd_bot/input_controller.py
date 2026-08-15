from __future__ import annotations

import ctypes
import logging
import sys
import time
from ctypes import wintypes
from typing import Any

from mxd_bot.types import ActionType, Decision

LOGGER = logging.getLogger(__name__)


class AdminRequiredError(RuntimeError):
    """脚本不是管理员，Windows 会静默丢弃发给游戏的按键。"""


def ensure_running_as_admin() -> None:
    """非管理员时直接报错。按键丢弃由 Windows UIPI 完成，用户态无法绕过。"""
    try:
        is_admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
    except OSError:
        is_admin = False

    if is_admin:
        return

    raise AdminRequiredError(
        "本脚本必须以管理员身份运行，否则 Windows 会静默丢弃发给游戏的按键"
        "（表现为焦点在游戏上、日志一切正常、角色却完全不动）。"
        "请以管理员身份打开 PowerShell 后重新执行："
        f"{sys.executable} -m mxd_bot --config config.yaml run"
    )

MOVE_KEYS = {"left", "right", "up", "down", "a", "d", "w", "s"}
ARROW_KEYS = {"left", "right", "up", "down"}

# 硬件扫描码（DirectInput 游戏更认这个）
SCAN_CODES: dict[str, int] = {
    "esc": 0x01,
    "1": 0x02,
    "2": 0x03,
    "3": 0x04,
    "4": 0x05,
    "5": 0x06,
    "6": 0x07,
    "7": 0x08,
    "8": 0x09,
    "9": 0x0A,
    "0": 0x0B,
    "q": 0x10,
    "w": 0x11,
    "e": 0x12,
    "r": 0x13,
    "t": 0x14,
    "y": 0x15,
    "u": 0x16,
    "i": 0x17,
    "o": 0x18,
    "p": 0x19,
    "a": 0x1E,
    "s": 0x1F,
    "d": 0x20,
    "f": 0x21,
    "g": 0x22,
    "h": 0x23,
    "j": 0x24,
    "k": 0x25,
    "l": 0x26,
    "z": 0x2C,
    "x": 0x2D,
    "c": 0x2E,
    "v": 0x2F,
    "b": 0x30,
    "n": 0x31,
    "m": 0x32,
    "space": 0x39,
    "f1": 0x3B,
    "f2": 0x3C,
    "f3": 0x3D,
    "f4": 0x3E,
    "f5": 0x3F,
    "f6": 0x40,
    "f7": 0x41,
    "f8": 0x42,
    "f9": 0x43,
    "f10": 0x44,
    "f11": 0x57,
    "f12": 0x58,
    "ctrl": 0x1D,
    "alt": 0x38,
    "shift": 0x2A,
    "up": 0x48,
    "left": 0x4B,
    "right": 0x4D,
    "down": 0x50,
}

KEYEVENTF_SCANCODE = 0x0008
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_EXTENDEDKEY = 0x0001
INPUT_KEYBOARD = 1
VK_NUMLOCK = 0x90
SW_RESTORE = 9
FOCUS_SETTLE_SECONDS = 0.1


class KeyBdInput(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class HardwareInput(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class MouseInput(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class InputUnion(ctypes.Union):
    _fields_ = [  # noqa: RUF012 - ctypes 要求 _fields_ 是类级可变列表
        ("ki", KeyBdInput),
        ("mi", MouseInput),
        ("hi", HardwareInput),
    ]


class Input(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("ii", InputUnion)]


class InputController:
    def __init__(self, behavior_config: dict[str, Any], profile_config: dict[str, Any]) -> None:
        self.dry_run = bool(behavior_config["dry_run"])
        self.move_pulse = float(behavior_config["move_pulse_seconds"])
        self.patrol_pulse = float(behavior_config["patrol_pulse_seconds"])
        self.jump_cooldown = float(behavior_config["jump_cooldown_seconds"])
        self.attack_key = self._normalize_key(profile_config["attack_key"])
        self.jump_key = self._normalize_key(profile_config["jump_key"])
        self.left_key = self._normalize_key(profile_config.get("left_key", "left"))
        self.right_key = self._normalize_key(profile_config.get("right_key", "right"))
        self.up_key = self._normalize_key(profile_config.get("up_key", "up"))
        self.down_key = self._normalize_key(profile_config.get("down_key", "down"))
        self.hp_potion_key = self._normalize_key(profile_config.get("hp_potion_key", "1"))
        self.mp_potion_key = self._normalize_key(profile_config.get("mp_potion_key", "2"))
        self.attack_cooldown = float(profile_config["attack_cooldown_seconds"])
        self.buffs = list(profile_config.get("buffs", []))
        self._last_attack_at = 0.0
        self._last_jump_at = 0.0
        self._last_buff_at: dict[str, float] = {}
        self._last_dry_action: ActionType | None = None
        self._target_hwnd: int | None = None
        self._held_direction: str | None = None
        self._numlock_forced_off = False
        self._was_foreground = True
        self._user32 = ctypes.windll.user32
        self._extra = ctypes.c_ulong(0)
        self._ready = not self.dry_run

    @staticmethod
    def _normalize_key(raw_key: object) -> str:
        key = str(raw_key).strip().lower()
        aliases = {
            "control": "ctrl",
            "ctl": "ctrl",
            "leftarrow": "left",
            "rightarrow": "right",
            "uparrow": "up",
            "downarrow": "down",
            "arrowleft": "left",
            "arrowright": "right",
            "arrowup": "up",
            "arrowdown": "down",
            "←": "left",
            "→": "right",
            "↑": "up",
            "↓": "down",
        }
        return aliases.get(key, key)

    def set_target_window(self, hwnd: int) -> None:
        self._target_hwnd = hwnd

    def focus_game_window_once(self) -> None:
        """启动时把游戏切到前台一次；之后运行期间不再抢焦点。"""
        if self._target_hwnd is None:
            return

        hwnd = int(self._target_hwnd)
        if int(self._user32.GetForegroundWindow()) != hwnd:
            self._user32.ShowWindow(hwnd, SW_RESTORE)
            self._user32.SetForegroundWindow(hwnd)
            time.sleep(FOCUS_SETTLE_SECONDS)
            LOGGER.info("已把游戏窗口切到前台（仅启动时一次）")

        self._was_foreground = int(self._user32.GetForegroundWindow()) == hwnd
        self._held_direction = None

    @property
    def input_suspended(self) -> bool:
        """兼容旧 GUI 状态字段；始终为 False。"""
        return False

    def describe_focus(self) -> str:
        """诊断：游戏窗口是否前台、当前前台窗口是谁。"""
        if self._target_hwnd is None:
            return "焦点=未知(未绑定游戏 hwnd)"

        target = int(self._target_hwnd)
        foreground = int(self._user32.GetForegroundWindow())
        if foreground == target:
            return f"焦点=游戏前台 hwnd={target:#x}"

        title = self._window_title(foreground) or "(无标题)"
        return (
            f"焦点=不在游戏 游戏hwnd={target:#x} "
            f"前台hwnd={foreground:#x} 前台标题={title!r}"
        )

    def _window_title(self, hwnd: int) -> str:
        if not hwnd:
            return ""
        length = int(self._user32.GetWindowTextLengthW(hwnd))
        buffer = ctypes.create_unicode_buffer(length + 1)
        self._user32.GetWindowTextW(hwnd, buffer, length + 1)
        return buffer.value

    def execute(self, decision: Decision) -> None:
        now = time.monotonic()
        action = decision.action

        if self.dry_run:
            if action != self._last_dry_action:
                LOGGER.info(
                    "[演练] action=%s dx=%s dy=%s | %s",
                    action.value,
                    decision.horizontal_distance,
                    decision.vertical_distance,
                    self.describe_focus(),
                )
                self._last_dry_action = action
            return

        if action != self._last_dry_action:
            LOGGER.info(
                "[真实] action=%s dx=%s dy=%s | %s",
                action.value,
                decision.horizontal_distance,
                decision.vertical_distance,
                self.describe_focus(),
            )
            self._last_dry_action = action

        if action == ActionType.ATTACK:
            self._release_direction()
            if now - self._last_attack_at >= self.attack_cooldown:
                self._press(self.attack_key)
                self._last_attack_at = now
        elif action in {ActionType.MOVE_LEFT, ActionType.MOVE_RIGHT}:
            key = self.left_key if action == ActionType.MOVE_LEFT else self.right_key
            self._hold_direction(key)
        elif action in {ActionType.PATROL_LEFT, ActionType.PATROL_RIGHT}:
            key = self.left_key if action == ActionType.PATROL_LEFT else self.right_key
            self._hold_direction(key)
        elif action in {ActionType.JUMP_LEFT, ActionType.JUMP_RIGHT}:
            self._release_direction()
            if now - self._last_jump_at >= self.jump_cooldown:
                direction = self.left_key if action == ActionType.JUMP_LEFT else self.right_key
                self._jump(direction)
                self._last_jump_at = now
        else:
            self._release_direction()

    def press_configured_key(self, key_name: str) -> None:
        keys = {
            "attack": self.attack_key,
            "jump": self.jump_key,
            "left": self.left_key,
            "right": self.right_key,
            "up": self.up_key,
            "down": self.down_key,
            "hp_potion": self.hp_potion_key,
            "mp_potion": self.mp_potion_key,
        }
        key = keys.get(key_name)
        if key is None:
            LOGGER.warning("未知手动按键动作：%s", key_name)
            return

        self._ready = True
        if key in MOVE_KEYS:
            self._hold(key, max(0.12, self.move_pulse))
        else:
            self._press(key)
        LOGGER.info("[手动测试] 已发送=%s key=%s | %s", key_name, key, self.describe_focus())

    def cast_due_buffs(self) -> None:
        now = time.monotonic()
        for buff in self.buffs:
            key = self._normalize_key(buff["key"])
            interval = float(buff["interval_seconds"])
            last_cast = self._last_buff_at.get(key, now)
            self._last_buff_at.setdefault(key, now)

            if now - last_cast >= interval:
                if self.dry_run:
                    LOGGER.info("[演练] buff=%s", key)
                else:
                    self._press(key)
                self._last_buff_at[key] = now

    def release_all(self) -> None:
        if not self._ready and self.dry_run:
            return
        self._release_direction()
        for key in (
            self.left_key,
            self.right_key,
            self.up_key,
            self.down_key,
            self.jump_key,
            self.attack_key,
        ):
            self._key_up(key)
        self._restore_numlock_if_needed()

    def _hold_direction(self, key: str) -> None:
        """保持方向键按下，直到决策改成攻击、跳跃、停止或另一方向。"""
        self._prepare_game_input()

        if self._held_direction == key:
            return

        self._release_direction()
        self._ensure_numlock_off_for_arrows(key)
        self._key_down(key)
        self._held_direction = key
        LOGGER.info("持续移动开始 key=%s", key)

    def _release_direction(self) -> None:
        if self._held_direction is None:
            return

        key = self._held_direction
        self._key_up(key)
        self._held_direction = None
        LOGGER.info("持续移动结束 key=%s", key)

    def _press(self, key: str) -> None:
        self._prepare_game_input()
        self._ensure_numlock_off_for_arrows(key)
        self._key_down(key)
        time.sleep(0.03)
        self._key_up(key)

    def _hold(self, key: str, duration: float) -> None:
        self._prepare_game_input()
        self._ensure_numlock_off_for_arrows(key)
        self._key_down(key)
        try:
            time.sleep(duration)
        finally:
            self._key_up(key)

    def _jump(self, direction: str) -> None:
        self._prepare_game_input()
        self._ensure_numlock_off_for_arrows(direction)
        self._key_down(direction)
        try:
            time.sleep(0.03)
            self._key_down(self.jump_key)
            time.sleep(0.03)
            self._key_up(self.jump_key)
        finally:
            self._key_up(direction)

    def _prepare_game_input(self) -> None:
        """跟踪前台变化；切回游戏且正在长按移动时，重发一次方向键。"""
        if self._target_hwnd is None:
            return

        is_foreground = int(self._user32.GetForegroundWindow()) == int(self._target_hwnd)
        if is_foreground == self._was_foreground:
            return

        self._was_foreground = is_foreground
        if is_foreground:
            # 移动是长按：切走后游戏丢了 keydown，切回时如果还在移动就重按一次。
            if self._held_direction is not None:
                self._key_down(self._held_direction)
                LOGGER.info("游戏回到前台，重新按下移动键 key=%s", self._held_direction)
        else:
            LOGGER.warning("游戏已切到后台 | %s", self.describe_focus())

    def _ensure_numlock_off_for_arrows(self, key: str) -> None:
        """NumLock 开着时模拟方向键会变成小键盘数字；本次运行内只关一次。"""
        if key not in ARROW_KEYS:
            return
        if self._numlock_forced_off:
            return
        if not self._numlock_on():
            return
        LOGGER.warning("检测到 NumLock 开启，本轮运行内关闭（避免方向键变成数字键）")
        self._set_numlock(False)
        self._numlock_forced_off = True
        time.sleep(0.02)

    def _restore_numlock_if_needed(self) -> None:
        if not self._numlock_forced_off:
            return
        self._set_numlock(True)
        self._numlock_forced_off = False

    def _numlock_on(self) -> bool:
        return bool(self._user32.GetKeyState(VK_NUMLOCK) & 1)

    def _set_numlock(self, enabled: bool) -> None:
        if self._numlock_on() == enabled:
            return
        self._send_vk(VK_NUMLOCK, key_up=False)
        self._send_vk(VK_NUMLOCK, key_up=True)

    def _key_down(self, key: str) -> None:
        scan = SCAN_CODES.get(key)
        if scan is None:
            raise ValueError(f"不支持的按键：{key}")
        flags = KEYEVENTF_SCANCODE
        if key in ARROW_KEYS:
            flags |= KEYEVENTF_EXTENDEDKEY
        self._send_scan(scan, flags)

    def _key_up(self, key: str) -> None:
        scan = SCAN_CODES.get(key)
        if scan is None:
            return
        flags = KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP
        if key in ARROW_KEYS:
            flags |= KEYEVENTF_EXTENDEDKEY
        self._send_scan(scan, flags)

    def _send_scan(self, scan: int, flags: int) -> None:
        extra = ctypes.pointer(self._extra)
        union = InputUnion()
        union.ki = KeyBdInput(0, scan, flags, 0, extra)
        event = Input(INPUT_KEYBOARD, union)
        sent = self._user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(Input))
        if sent != 1:
            LOGGER.warning("SendInput 失败 scan=%s flags=%s", hex(scan), flags)

    def _send_vk(self, vk: int, key_up: bool) -> None:
        extra = ctypes.pointer(self._extra)
        flags = KEYEVENTF_KEYUP if key_up else 0
        union = InputUnion()
        union.ki = KeyBdInput(vk, 0, flags, 0, extra)
        event = Input(INPUT_KEYBOARD, union)
        self._user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(Input))
