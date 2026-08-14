from mxd_bot.input_controller import InputController


class FakeUser32:
    def __init__(self, foreground_hwnd: int) -> None:
        self.foreground_hwnd = foreground_hwnd

    def GetForegroundWindow(self) -> int:
        return self.foreground_hwnd


def make_controller(target_hwnd: int, foreground_hwnd: int):
    controller = InputController.__new__(InputController)
    controller._target_hwnd = target_hwnd
    controller._background_suspended = False
    controller._user32 = FakeUser32(foreground_hwnd)
    released: list[bool] = []
    restored: list[bool] = []
    controller._release_direction = lambda: released.append(True)
    controller._restore_numlock_if_needed = lambda: restored.append(True)
    return controller, released, restored


def test_background_window_suspends_input_and_releases_keys() -> None:
    controller, released, restored = make_controller(
        target_hwnd=100,
        foreground_hwnd=200,
    )

    assert controller._allow_game_input() is False
    assert controller._background_suspended is True
    assert released == [True]
    assert restored == [True]


def test_returning_to_game_resumes_without_focusing_window() -> None:
    controller, released, restored = make_controller(
        target_hwnd=100,
        foreground_hwnd=100,
    )
    controller._background_suspended = True

    assert controller._allow_game_input() is True
    assert controller._background_suspended is False
    assert released == []
    assert restored == []
