from __future__ import annotations

from copy import deepcopy
from typing import Any

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap, QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from mxd_bot.gui_worker import BotWorker


class MainWindow(QMainWindow):
    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__()
        self._base_config = deepcopy(config)
        self._worker: BotWorker | None = None

        self.setWindowTitle("MXD Vision Monitor")
        self.resize(1280, 720)

        root = QWidget()
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(6)

        root_layout.addWidget(self._build_top_bar())

        middle = QSplitter(Qt.Orientation.Horizontal)
        middle.addWidget(self._build_side_panel())
        middle.addWidget(self._build_preview())
        middle.setStretchFactor(0, 0)
        middle.setStretchFactor(1, 1)
        middle.setSizes([280, 1000])
        root_layout.addWidget(middle, stretch=1)

        root_layout.addWidget(self._build_log_bar())

        self.profile_box.currentTextChanged.connect(self._load_profile_settings)
        self._load_profile_settings(self.profile_box.currentText())
        self._append_log("GUI 已就绪。先开游戏窗口，再点开始。")

    def _build_top_bar(self) -> QWidget:
        bar = QGroupBox()
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        self.start_button = QPushButton("开始")
        self.pause_button = QPushButton("暂停")
        self.stop_button = QPushButton("停止")
        self.stop_button.setEnabled(False)
        self.pause_button.setEnabled(False)
        for button in (self.start_button, self.pause_button, self.stop_button):
            button.setFixedHeight(28)
            button.setMaximumWidth(72)

        self.start_button.clicked.connect(self._on_start)
        self.stop_button.clicked.connect(self._on_stop)
        self.pause_button.clicked.connect(self._on_pause)

        self.profile_box = QComboBox()
        self.profile_box.addItems(sorted(self._base_config["profiles"].keys()))
        current_profile = self._base_config["behavior"].get("profile", "warrior")
        index = self.profile_box.findText(current_profile)
        if index >= 0:
            self.profile_box.setCurrentIndex(index)
        self.profile_box.setMaximumWidth(110)

        self.dry_run_box = QCheckBox("仅预览")
        self.dry_run_box.setChecked(bool(self._base_config["behavior"].get("dry_run", True)))
        self.dry_run_box.setToolTip("勾选后不发送任何自动按键，只看预览和日志")

        self.auto_attack_box = QCheckBox("自动攻击")
        self.auto_attack_box.setChecked(
            bool(self._base_config["behavior"].get("auto_attack_enabled", True))
        )

        self.fps_box = QSpinBox()
        self.fps_box.setRange(10, 60)
        self.fps_box.setValue(int(self._base_config.get("ui", {}).get("target_fps", 30)))
        self.fps_box.setMaximumWidth(70)

        self.preview_fps_box = QSpinBox()
        self.preview_fps_box.setRange(5, 60)
        self.preview_fps_box.setValue(
            int(self._base_config.get("ui", {}).get("preview_fps", 15))
        )
        self.preview_fps_box.setMaximumWidth(70)

        self.fps_label = QLabel("-")
        self.action_label = QLabel("-")
        self.player_label = QLabel("-")
        self.monster_label = QLabel("-")
        self.mode_label = QLabel("-")

        layout.addWidget(self.start_button)
        layout.addWidget(self.pause_button)
        layout.addWidget(self.stop_button)
        layout.addWidget(QLabel("职业"))
        layout.addWidget(self.profile_box)
        layout.addWidget(self.dry_run_box)
        layout.addWidget(self.auto_attack_box)
        layout.addWidget(QLabel("识别FPS"))
        layout.addWidget(self.fps_box)
        layout.addWidget(QLabel("预览FPS"))
        layout.addWidget(self.preview_fps_box)
        layout.addStretch(1)
        layout.addWidget(QLabel("FPS"))
        layout.addWidget(self.fps_label)
        layout.addWidget(QLabel("动作"))
        layout.addWidget(self.action_label)
        layout.addWidget(QLabel("人"))
        layout.addWidget(self.player_label)
        layout.addWidget(QLabel("怪"))
        layout.addWidget(self.monster_label)
        layout.addWidget(self.mode_label)
        return bar

    def _build_side_panel(self) -> QWidget:
        panel = QWidget()
        panel.setMinimumWidth(250)
        panel.setMaximumWidth(300)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        keys = QGroupBox("按键")
        keys_form = QFormLayout(keys)
        keys_form.setContentsMargins(8, 6, 8, 6)
        keys_form.setHorizontalSpacing(8)
        keys_form.setVerticalSpacing(4)
        self.attack_key_edit = self._key_selector()
        self.jump_key_edit = self._key_selector()
        self.left_key_edit = self._key_selector()
        self.right_key_edit = self._key_selector()
        self.up_key_edit = self._key_selector()
        self.down_key_edit = self._key_selector()
        self.hp_potion_key_edit = self._key_selector()
        self.mp_potion_key_edit = self._key_selector()
        keys_form.addRow("攻击", self.attack_key_edit)
        keys_form.addRow("跳跃", self.jump_key_edit)
        keys_form.addRow("左", self.left_key_edit)
        keys_form.addRow("右", self.right_key_edit)
        keys_form.addRow("上", self.up_key_edit)
        keys_form.addRow("下", self.down_key_edit)
        keys_form.addRow("HP", self.hp_potion_key_edit)
        keys_form.addRow("MP", self.mp_potion_key_edit)
        layout.addWidget(keys)

        tests = QGroupBox("手动测试")
        tests_layout = QGridLayout(tests)
        tests_layout.setContentsMargins(6, 6, 6, 6)
        tests_layout.setHorizontalSpacing(4)
        tests_layout.setVerticalSpacing(4)
        self.attack_test_button = self._test_button("攻击", "attack")
        self.jump_test_button = self._test_button("跳跃", "jump")
        self.left_test_button = self._test_button("←", "left")
        self.right_test_button = self._test_button("→", "right")
        self.up_test_button = self._test_button("↑", "up")
        self.down_test_button = self._test_button("↓", "down")
        self.hp_test_button = self._test_button("HP", "hp_potion")
        self.mp_test_button = self._test_button("MP", "mp_potion")
        tests_layout.addWidget(self.attack_test_button, 0, 0)
        tests_layout.addWidget(self.jump_test_button, 0, 1)
        tests_layout.addWidget(self.hp_test_button, 0, 2)
        tests_layout.addWidget(self.mp_test_button, 0, 3)
        tests_layout.addWidget(self.left_test_button, 1, 0)
        tests_layout.addWidget(self.up_test_button, 1, 1)
        tests_layout.addWidget(self.down_test_button, 1, 2)
        tests_layout.addWidget(self.right_test_button, 1, 3)
        layout.addWidget(tests)

        tip = QLabel("手动测试会切到游戏并真实发键；仅预览只影响自动按键。")
        tip.setWordWrap(True)
        tip.setStyleSheet("color:#666; font-size:11px;")
        layout.addWidget(tip)
        layout.addStretch(1)
        return panel

    def _build_preview(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        self.preview_label = QLabel("尚未开始")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet("background:#111; color:#ddd;")
        self.preview_label.setMinimumSize(480, 270)
        layout.addWidget(self.preview_label)
        return panel

    def _build_log_bar(self) -> QWidget:
        box = QGroupBox("日志")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(6, 4, 6, 4)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFixedHeight(110)
        layout.addWidget(self.log_view)
        return box

    @staticmethod
    def _key_selector() -> QComboBox:
        field = QComboBox()
        field.setEditable(True)
        field.addItems(
            [
                "ctrl",
                "alt",
                "shift",
                "space",
                "left",
                "right",
                "up",
                "down",
                *[str(number) for number in range(10)],
                *[f"f{number}" for number in range(1, 13)],
                *[chr(letter) for letter in range(ord("a"), ord("z") + 1)],
            ]
        )
        field.setMaximumWidth(96)
        field.setFixedHeight(24)
        return field

    def _test_button(self, label: str, key_name: str) -> QPushButton:
        button = QPushButton(label)
        button.setFixedHeight(26)
        button.clicked.connect(
            lambda _checked=False, name=key_name: self._on_test_key(name)
        )
        return button

    def _load_profile_settings(self, profile_name: str) -> None:
        profile = self._base_config["profiles"].get(profile_name, {})
        fields = {
            self.attack_key_edit: profile.get("attack_key", "ctrl"),
            self.jump_key_edit: profile.get("jump_key", "alt"),
            self.left_key_edit: profile.get("left_key", "left"),
            self.right_key_edit: profile.get("right_key", "right"),
            self.up_key_edit: profile.get("up_key", "up"),
            self.down_key_edit: profile.get("down_key", "down"),
            self.hp_potion_key_edit: profile.get("hp_potion_key", "1"),
            self.mp_potion_key_edit: profile.get("mp_potion_key", "2"),
        }
        for field, value in fields.items():
            field.setCurrentText(str(value))

    def _build_runtime_config(self) -> dict[str, Any]:
        config = deepcopy(self._base_config)
        profile_name = self.profile_box.currentText()
        config["behavior"]["profile"] = profile_name
        config["behavior"]["dry_run"] = self.dry_run_box.isChecked()
        config["behavior"]["auto_attack_enabled"] = self.auto_attack_box.isChecked()
        config["behavior"]["debug_window"] = False
        config["behavior"]["startup_delay_seconds"] = 0
        profile = config["profiles"][profile_name]
        profile.update(
            {
                "attack_key": self.attack_key_edit.currentText().strip() or "ctrl",
                "jump_key": self.jump_key_edit.currentText().strip() or "alt",
                "left_key": self.left_key_edit.currentText().strip() or "left",
                "right_key": self.right_key_edit.currentText().strip() or "right",
                "up_key": self.up_key_edit.currentText().strip() or "up",
                "down_key": self.down_key_edit.currentText().strip() or "down",
                "hp_potion_key": self.hp_potion_key_edit.currentText().strip() or "1",
                "mp_potion_key": self.mp_potion_key_edit.currentText().strip() or "2",
            }
        )
        config.setdefault("ui", {})
        config["ui"]["target_fps"] = int(self.fps_box.value())
        config["ui"]["preview_fps"] = int(self.preview_fps_box.value())
        return config

    def _on_start(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return

        config = self._build_runtime_config()
        if config["behavior"]["profile"] not in config["profiles"]:
            QMessageBox.warning(self, "配置错误", "未知职业配置")
            return

        self._worker = BotWorker(config)
        self._worker.frame_ready.connect(self._on_frame)
        self._worker.status_ready.connect(self._on_status)
        self._worker.log_ready.connect(self._append_log)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.pause_button.setEnabled(True)
        self.pause_button.setText("暂停")
        self.profile_box.setEnabled(False)
        self.dry_run_box.setEnabled(False)
        self.auto_attack_box.setEnabled(False)
        self.fps_box.setEnabled(False)
        self.preview_fps_box.setEnabled(False)
        self._set_key_fields_enabled(False)

    def _on_stop(self) -> None:
        if self._worker is None:
            return
        self._worker.request_stop()
        self.stop_button.setEnabled(False)
        self.pause_button.setEnabled(False)

    def _on_pause(self) -> None:
        if self._worker is None or not self._worker.isRunning():
            return
        paused = self.pause_button.text() == "暂停"
        self._worker.set_paused(paused)
        self.pause_button.setText("继续" if paused else "暂停")
        self._append_log("已暂停" if paused else "已继续")

    def _on_test_key(self, key_name: str) -> None:
        if self._worker is None or not self._worker.isRunning():
            self._append_log("请先点击“开始”，再测试按键。")
            return
        self._worker.request_key(key_name)

    def _set_key_fields_enabled(self, enabled: bool) -> None:
        for field in (
            self.attack_key_edit,
            self.jump_key_edit,
            self.left_key_edit,
            self.right_key_edit,
            self.up_key_edit,
            self.down_key_edit,
            self.hp_potion_key_edit,
            self.mp_potion_key_edit,
        ):
            field.setEnabled(enabled)

    def _on_frame(self, rgb_frame: object) -> None:
        if not isinstance(rgb_frame, np.ndarray):
            return
        height, width, channels = rgb_frame.shape
        bytes_per_line = channels * width
        image = QImage(
            rgb_frame.data,
            width,
            height,
            bytes_per_line,
            QImage.Format.Format_RGB888,
        ).copy()
        pixmap = QPixmap.fromImage(image)
        self.preview_label.setPixmap(
            pixmap.scaled(
                self.preview_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def _on_status(self, status: dict) -> None:
        self.fps_label.setText(str(status.get("fps", "-")))
        self.action_label.setText(str(status.get("action", "-")))
        self.player_label.setText("有" if status.get("has_player") else "无")
        self.monster_label.setText(str(status.get("monsters", 0)))
        mode = "仅预览" if status.get("dry_run") else "真实"
        mode += " / 攻开" if status.get("auto_attack") else " / 攻关"
        if status.get("paused"):
            mode += " / 暂停"
        elif status.get("input_suspended"):
            mode += " / 后台停键"
        self.mode_label.setText(f"{status.get('profile', '-')} | {mode}")

    def _on_failed(self, message: str) -> None:
        self._append_log(f"错误：{message}")
        QMessageBox.critical(self, "运行失败", message)

    def _on_worker_finished(self) -> None:
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.pause_button.setEnabled(False)
        self.pause_button.setText("暂停")
        self.profile_box.setEnabled(True)
        self.dry_run_box.setEnabled(True)
        self.auto_attack_box.setEnabled(True)
        self.fps_box.setEnabled(True)
        self.preview_fps_box.setEnabled(True)
        self._set_key_fields_enabled(True)
        self._worker = None

    def _append_log(self, message: str) -> None:
        self.log_view.append(message)
        self.log_view.moveCursor(QTextCursor.MoveOperation.End)

    def closeEvent(self, event) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.request_stop()
            self._worker.wait(3000)
        super().closeEvent(event)
