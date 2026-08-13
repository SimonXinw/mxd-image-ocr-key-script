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
        layout = QHBoxLayout(root)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        splitter.addWidget(self._build_sidebar())
        splitter.addWidget(self._build_preview())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([320, 960])

        self._append_log("GUI 已就绪。请先打开游戏窗口，再点开始。")

    def _build_sidebar(self) -> QWidget:
        panel = QWidget()
        panel.setMinimumWidth(300)
        panel.setMaximumWidth(380)
        layout = QVBoxLayout(panel)

        controls = QGroupBox("控制")
        controls_layout = QVBoxLayout(controls)

        self.start_button = QPushButton("开始")
        self.stop_button = QPushButton("停止")
        self.pause_button = QPushButton("暂停")
        self.stop_button.setEnabled(False)
        self.pause_button.setEnabled(False)

        self.start_button.clicked.connect(self._on_start)
        self.stop_button.clicked.connect(self._on_stop)
        self.pause_button.clicked.connect(self._on_pause)

        controls_layout.addWidget(self.start_button)
        controls_layout.addWidget(self.pause_button)
        controls_layout.addWidget(self.stop_button)
        layout.addWidget(controls)

        settings = QGroupBox("参数")
        form = QFormLayout(settings)

        self.profile_box = QComboBox()
        self.profile_box.addItems(sorted(self._base_config["profiles"].keys()))
        current_profile = self._base_config["behavior"].get("profile", "warrior")
        index = self.profile_box.findText(current_profile)
        if index >= 0:
            self.profile_box.setCurrentIndex(index)

        self.dry_run_box = QCheckBox("演练模式（不发送按键）")
        self.dry_run_box.setChecked(bool(self._base_config["behavior"].get("dry_run", True)))

        self.fps_box = QSpinBox()
        self.fps_box.setRange(10, 60)
        self.fps_box.setValue(int(self._base_config.get("ui", {}).get("target_fps", 30)))

        form.addRow("职业配置", self.profile_box)
        form.addRow(self.dry_run_box)
        form.addRow("目标帧率", self.fps_box)
        layout.addWidget(settings)

        status = QGroupBox("状态")
        status_form = QFormLayout(status)
        self.fps_label = QLabel("-")
        self.action_label = QLabel("-")
        self.player_label = QLabel("-")
        self.monster_label = QLabel("-")
        self.mode_label = QLabel("-")
        status_form.addRow("FPS", self.fps_label)
        status_form.addRow("动作", self.action_label)
        status_form.addRow("玩家", self.player_label)
        status_form.addRow("怪物数", self.monster_label)
        status_form.addRow("模式", self.mode_label)
        layout.addWidget(status)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMinimumHeight(180)
        layout.addWidget(self.log_view, stretch=1)

        tip = QLabel("预览是截屏镜像+画框，可拖到游戏窗口旁边对照。")
        tip.setWordWrap(True)
        layout.addWidget(tip)
        return panel

    def _build_preview(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        self.preview_label = QLabel("尚未开始")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet("background:#111; color:#ddd;")
        self.preview_label.setMinimumSize(640, 360)
        layout.addWidget(self.preview_label)
        return panel

    def _build_runtime_config(self) -> dict[str, Any]:
        config = deepcopy(self._base_config)
        config["behavior"]["profile"] = self.profile_box.currentText()
        config["behavior"]["dry_run"] = self.dry_run_box.isChecked()
        config["behavior"]["debug_window"] = False
        config["behavior"]["startup_delay_seconds"] = 0
        config.setdefault("ui", {})
        config["ui"]["target_fps"] = int(self.fps_box.value())
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
        self.fps_box.setEnabled(False)

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
        self.player_label.setText("已找到" if status.get("has_player") else "未找到")
        self.monster_label.setText(str(status.get("monsters", 0)))
        mode = "演练" if status.get("dry_run") else "真实按键"
        if status.get("paused"):
            mode += " / 暂停"
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
        self.fps_box.setEnabled(True)
        self._worker = None

    def _append_log(self, message: str) -> None:
        self.log_view.append(message)
        self.log_view.moveCursor(QTextCursor.MoveOperation.End)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        if self._worker is not None and self._worker.isRunning():
            self._worker.request_stop()
            self._worker.wait(3000)
        super().closeEvent(event)
