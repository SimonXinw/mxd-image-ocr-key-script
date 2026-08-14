from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


def load_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(
            f"找不到配置文件：{config_path}。仓库自带 config.yaml，"
            "被删掉时可用 git restore config.yaml 找回。"
        )

    with config_path.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}

    _validate_config(config)
    return config


def apply_overrides(
    config: dict[str, Any],
    profile: str | None = None,
    dry_run: bool | None = None,
) -> dict[str, Any]:
    result = deepcopy(config)

    if profile is not None:
        if profile not in result["profiles"]:
            available = ", ".join(result["profiles"])
            raise ValueError(f"未知职业配置 {profile!r}，可选：{available}")
        result["behavior"]["profile"] = profile

    if dry_run is not None:
        result["behavior"]["dry_run"] = dry_run

    return result


def _validate_config(config: dict[str, Any]) -> None:
    required_sections = {
        "window",
        "model",
        "player",
        "behavior",
        "profiles",
        "collection",
        "training",
    }
    missing = sorted(required_sections - config.keys())
    if missing:
        raise ValueError(f"配置缺少字段：{', '.join(missing)}")

    if not str(config["window"].get("title_contains", "")).strip():
        raise ValueError("window.title_contains 不能为空")

    profile = config["behavior"].get("profile")
    if profile not in config["profiles"]:
        raise ValueError(f"behavior.profile={profile!r} 未在 profiles 中定义")

    locator = config["player"].get("locator")
    if locator not in {"yolo", "template", "hybrid"}:
        raise ValueError("player.locator 只能是 yolo、template 或 hybrid")

    confidence = float(config["model"].get("confidence", 0))
    if not 0 < confidence <= 1:
        raise ValueError("model.confidence 必须在 (0, 1] 范围内")

    monster_classes = config["model"].get("monster_classes", [])
    if not monster_classes:
        raise ValueError("model.monster_classes 至少需要一个类别")
