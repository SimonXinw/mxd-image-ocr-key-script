import ctypes

import pytest

from mxd_bot.input_controller import (
    SW_RESTORE,
    AdminRequiredError,
    InputController,
    ensure_running_as_admin,
)
from mxd_bot.types import ActionType, Decision


class FakeUser32:
    def __init__(self, foreground_hwnd: int) -> None:
        self.foreground_hwnd = foreground_hwnd
        self.show_calls: list[tuple[int, int]] = []
        self.focus_calls: list[int] = []

    def GetForegroundWindow(self) -> int:
        return self.foreground_hwnd

    def ShowWindow(self, hwnd: int, command: int) -> bool:
        self.show_calls.append((hwnd, command))
        return True

    def SetForegroundWindow(self, hwnd: int) -> bool:
        self.focus_calls.append(hwnd)
        self.foreground_hwnd = hwnd
        return True

    def GetWindowTextLengthW(self, hwnd: int) -> int:
        return 0

    def GetWindowTextW(self, hwnd: int, buffer: object, length: int) -> int:
        return 0


def make_controller(target_hwnd: int, foreground_hwnd: int):
    controller = InputController.__new__(InputController)
    controller._target_hwnd = target_hwnd
    controller._held_direction = None
    controller._was_foreground = True
    controller._user32 = FakeUser32(foreground_hwnd)
    return controller


class FakeShell32:
    def __init__(self, is_admin: bool) -> None:
        self.is_admin = is_admin

    def IsUserAnAdmin(self) -> int:
        return 1 if self.is_admin else 0


def test_dry_run_does_not_send_keys() -> None:
    controller = InputController.__new__(InputController)
    controller.dry_run = True
    controller._last_dry_action = None
    controller._target_hwnd = None
    pressed: list[str] = []
    controller._press = lambda key: pressed.append(key)
    controller._hold_direction = lambda key: pressed.append(key)
    controller._release_direction = lambda: None

    controller.execute(Decision(ActionType.ATTACK))

    assert pressed == []


def test_non_admin_startup_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ctypes, "windll", type("W", (), {"shell32": FakeShell32(False)}))

    with pytest.raises(AdminRequiredError):
        ensure_running_as_admin()


def test_admin_startup_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ctypes, "windll", type("W", (), {"shell32": FakeShell32(True)}))

    ensure_running_as_admin()


def test_startup_focus_brings_game_to_front_once() -> None:
    controller = make_controller(target_hwnd=100, foreground_hwnd=200)

    controller.focus_game_window_once()

    assert controller._user32.focus_calls == [100]
    assert controller._user32.show_calls == [(100, SW_RESTORE)]


def test_startup_focus_skipped_when_already_foreground() -> None:
    controller = make_controller(target_hwnd=100, foreground_hwnd=100)

    controller.focus_game_window_once()

    assert controller._user32.focus_calls == []
    assert controller._user32.show_calls == []


def test_sending_keys_never_steals_focus() -> None:
    """运行期间游戏在后台也不抢焦点。"""
    controller = make_controller(target_hwnd=100, foreground_hwnd=200)

    controller._prepare_game_input()

    assert controller._user32.focus_calls == []
    assert controller._user32.show_calls == []
    assert controller._was_foreground is False


def test_focus_return_represses_held_direction() -> None:
    """切回游戏且正在长按移动时，重发一次方向键。"""
    controller = make_controller(target_hwnd=100, foreground_hwnd=200)
    controller._held_direction = "left"
    downs: list[str] = []
    controller._key_down = lambda key: downs.append(key)

    controller._prepare_game_input()
    assert downs == []

    controller._user32.foreground_hwnd = 100
    controller._prepare_game_input()

    assert downs == ["left"]
    assert controller._held_direction == "left"


def test_focus_return_without_move_does_not_press() -> None:
    controller = make_controller(target_hwnd=100, foreground_hwnd=200)
    downs: list[str] = []
    controller._key_down = lambda key: downs.append(key)

    controller._prepare_game_input()
    controller._user32.foreground_hwnd = 100
    controller._prepare_game_input()

    assert downs == []
