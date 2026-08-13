from __future__ import annotations

import logging
from typing import Any

LOGGER = logging.getLogger(__name__)


def resolve_device(preference: Any = "auto") -> str | int:
    """解析训练/推理设备。

    preference:
    - auto / null / ""：优先 CUDA，没有则 CPU
    - cuda / gpu / nv：强制 NVIDIA；不可用时回退 CPU 并告警
    - cpu：强制 CPU
    - 0 / "0"：指定 GPU 编号
    """
    raw = "auto" if preference is None else str(preference).strip().lower()
    if raw in {"", "null", "none"}:
        raw = "auto"

    import torch

    cuda_ok = torch.cuda.is_available()

    if raw in {"auto"}:
        if cuda_ok:
            name = torch.cuda.get_device_name(0)
            LOGGER.info("设备=CUDA:0（%s）", name)
            return 0
        LOGGER.info("未检测到可用 NVIDIA CUDA，回退到 CPU")
        return "cpu"

    if raw in {"cuda", "gpu", "nv", "nvidia"}:
        if cuda_ok:
            name = torch.cuda.get_device_name(0)
            LOGGER.info("设备=CUDA:0（%s）", name)
            return 0
        LOGGER.warning("配置要求使用 NVIDIA，但当前 PyTorch 看不到 CUDA，回退到 CPU")
        return "cpu"

    if raw == "cpu":
        LOGGER.info("设备=CPU（手动指定）")
        return "cpu"

    if raw.isdigit():
        index = int(raw)
        if cuda_ok and index < torch.cuda.device_count():
            name = torch.cuda.get_device_name(index)
            LOGGER.info("设备=CUDA:%d（%s）", index, name)
            return index
        LOGGER.warning("指定的 GPU %s 不可用，回退到 CPU", raw)
        return "cpu"

    raise ValueError(f"不支持的 device 配置：{preference!r}，可用 auto/cuda/cpu/0")


def describe_torch_backend() -> str:
    import torch

    if torch.cuda.is_available():
        return f"torch={torch.__version__}, cuda={torch.version.cuda}, gpu={torch.cuda.get_device_name(0)}"
    return f"torch={torch.__version__}, cuda=unavailable"
