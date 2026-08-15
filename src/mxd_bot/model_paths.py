from __future__ import annotations

import re
from pathlib import Path

INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def dataset_model_name(data_path: Path) -> str:
    """默认用 data.yaml 所在文件夹命名模型，中文会原样保留。"""
    return sanitize_model_name(data_path.resolve().parent.name)


def sanitize_model_name(name: str) -> str:
    """只替换 Windows 文件名禁用字符，不把中文强制转换成英文。"""
    cleaned = INVALID_FILENAME_CHARS.sub("-", name.strip())
    cleaned = cleaned.rstrip(". ")
    return cleaned or "model"


def resolve_output_weights(
    data_path: Path,
    output: str | Path | None = None,
    models_dir: Path = Path("models"),
) -> Path:
    """解析训练输出；仅提供文件名时自动放进 models/。"""
    if output is None or not str(output).strip():
        return models_dir / f"{dataset_model_name(data_path)}.pt"

    raw_path = Path(str(output).strip())
    if raw_path.suffix.lower() != ".pt":
        raw_path = raw_path.with_suffix(".pt")

    if not raw_path.is_absolute() and raw_path.parent == Path("."):
        raw_path = models_dir / sanitize_model_name(raw_path.name)
    return raw_path


def discover_weight_files(models_dir: Path = Path("models")) -> list[Path]:
    """递归发现可供 GUI 选择的 pt，兼容中文目录和文件名。"""
    if not models_dir.exists():
        return []

    weights = {path.resolve() for path in models_dir.rglob("*.pt") if path.is_file()}
    return sorted(weights, key=lambda path: str(path).casefold())
