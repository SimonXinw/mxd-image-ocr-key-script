from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

import yaml

from mxd_bot.device import resolve_device
from mxd_bot.model_paths import resolve_output_weights, sanitize_model_name

LOGGER = logging.getLogger(__name__)


def train_model(config: dict[str, Any], resume: bool = False) -> Path:
    training = config["training"]
    device = resolve_device(training.get("device", config["model"].get("device", "auto")))
    data_path = Path(training["data"])
    if not data_path.exists():
        raise FileNotFoundError(f"找不到数据集配置：{data_path}")

    models_dir = Path(config["model"].get("weights_dir", "models"))
    destination = resolve_output_weights(
        data_path,
        training.get("output_weights"),
        models_dir=models_dir,
    )
    run_name = sanitize_model_name(
        str(training.get("run_name") or destination.stem)
    )
    run_dir = Path("runs") / run_name
    configured_resume = training.get("resume_weights")
    last_weights = (
        Path(configured_resume)
        if configured_resume
        else run_dir / "weights" / "last.pt"
    )

    from ultralytics import YOLO

    if resume:
        if not last_weights.exists():
            raise FileNotFoundError(
                f"找不到续训权重：{last_weights}。请先完整训练一次，或确认上次中断后已生成 last.pt。"
            )
        LOGGER.info("从断点续训：%s", last_weights)
        model = YOLO(str(last_weights))
        results = model.train(resume=True, device=device)
    else:
        resolved_data_path = _write_resolved_dataset_config(
            data_path,
            run_dir / "data.resolved.yaml",
        )
        _ensure_dataset_images(resolved_data_path)

        LOGGER.info(
            "开始新训练，名称=%s data=%s 输出=%s base_model=%s",
            run_name,
            data_path,
            destination,
            training["base_model"],
        )
        model = YOLO(str(training["base_model"]))
        results = model.train(
            data=str(resolved_data_path),
            epochs=int(training["epochs"]),
            imgsz=int(training["image_size"]),
            batch=int(training["batch"]),
            workers=int(training["workers"]),
            project=str(Path("runs").resolve()),
            name=run_name,
            exist_ok=True,
            device=device,
        )

    source_weights = Path(results.save_dir) / "weights" / "best.pt"
    if not source_weights.exists():
        raise RuntimeError(f"训练结束但未找到权重：{source_weights}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_weights, destination)
    LOGGER.info("最佳模型已复制到：%s", destination)
    return destination


def _write_resolved_dataset_config(data_path: Path, output_path: Path) -> Path:
    with data_path.open("r", encoding="utf-8") as file:
        data_config = yaml.safe_load(file) or {}

    dataset_root = Path(data_config.get("path", "."))
    if not dataset_root.is_absolute():
        dataset_root = (data_path.parent / dataset_root).resolve()
    data_config["path"] = str(dataset_root)

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
