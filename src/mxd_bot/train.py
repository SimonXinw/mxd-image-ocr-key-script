from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

import yaml

from mxd_bot.device import resolve_device

LOGGER = logging.getLogger(__name__)
DEFAULT_RUN_DIR = Path("runs") / "mxd_detect"
DEFAULT_LAST_WEIGHTS = DEFAULT_RUN_DIR / "weights" / "last.pt"


def train_model(config: dict[str, Any], resume: bool = False) -> Path:
    training = config["training"]
    device = resolve_device(training.get("device", config["model"].get("device", "auto")))

    from ultralytics import YOLO

    if resume:
        last_weights = Path(training.get("resume_weights", DEFAULT_LAST_WEIGHTS))
        if not last_weights.exists():
            raise FileNotFoundError(
                f"找不到续训权重：{last_weights}。请先完整训练一次，或确认上次中断后已生成 last.pt。"
            )
        LOGGER.info("从断点续训：%s", last_weights)
        model = YOLO(str(last_weights))
        results = model.train(resume=True, device=device)
    else:
        data_path = Path(training["data"])
        if not data_path.exists():
            raise FileNotFoundError(f"找不到数据集配置：{data_path}")

        resolved_data_path = _write_resolved_dataset_config(data_path)
        _ensure_dataset_images(resolved_data_path)

        LOGGER.info("开始新训练，base_model=%s", training["base_model"])
        model = YOLO(str(training["base_model"]))
        results = model.train(
            data=str(resolved_data_path),
            epochs=int(training["epochs"]),
            imgsz=int(training["image_size"]),
            batch=int(training["batch"]),
            workers=int(training["workers"]),
            project=str(Path("runs").resolve()),
            name="mxd_detect",
            exist_ok=True,
            device=device,
        )

    source_weights = Path(results.save_dir) / "weights" / "best.pt"
    if not source_weights.exists():
        raise RuntimeError(f"训练结束但未找到权重：{source_weights}")

    destination = Path(config["model"]["weights"])
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_weights, destination)
    LOGGER.info("最佳模型已复制到：%s", destination)
    return destination


def _write_resolved_dataset_config(data_path: Path) -> Path:
    with data_path.open("r", encoding="utf-8") as file:
        data_config = yaml.safe_load(file) or {}

    dataset_root = Path(data_config.get("path", "."))
    if not dataset_root.is_absolute():
        dataset_root = (data_path.parent / dataset_root).resolve()
    data_config["path"] = str(dataset_root)

    output_path = Path("runs") / "mxd_data.resolved.yaml"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        yaml.safe_dump(data_config, file, allow_unicode=True, sort_keys=False)

    return output_path


def _ensure_dataset_images(resolved_data_path: Path) -> None:
    with resolved_data_path.open("r", encoding="utf-8") as file:
        data_config = yaml.safe_load(file) or {}

    dataset_root = Path(data_config["path"])
    for split_key in ("train", "val"):
        split_rel = data_config.get(split_key)
        if not split_rel:
            raise ValueError(f"dataset 配置缺少 {split_key}")

        split_dir = dataset_root / split_rel
        if not split_dir.exists():
            raise FileNotFoundError(
                f"找不到 {split_key} 图片目录：{split_dir}。请先采集并标注数据集。"
            )

        image_count = sum(1 for _ in split_dir.glob("*.*"))
        if image_count == 0:
            raise FileNotFoundError(
                f"{split_key} 目录为空：{split_dir}。请先放入标注好的图片。"
            )
