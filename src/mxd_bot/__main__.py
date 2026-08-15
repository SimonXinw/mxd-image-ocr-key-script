from __future__ import annotations

import argparse
import logging
from copy import deepcopy

from mxd_bot.app import run_bot
from mxd_bot.collect import collect_screenshots
from mxd_bot.config import apply_overrides, load_config
from mxd_bot.device import describe_torch_backend
from mxd_bot.input_controller import AdminRequiredError, ensure_running_as_admin
from mxd_bot.train import train_model

LOGGER = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="MXD 屏幕视觉自动化实验框架")
    parser.add_argument("--config", default="config.yaml", help="YAML 配置文件路径")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("collect", help="从游戏窗口采集训练截图")
    subparsers.add_parser("doctor", help="检查 PyTorch / CUDA 设备状态")
    subparsers.add_parser("gui", help="启动监控面板（等同于 run，默认打开界面）")

    train_parser = subparsers.add_parser("train", help="训练 YOLO 检测模型")
    train_parser.add_argument(
        "--resume",
        action="store_true",
        help="按本次任务名从 runs/<名称>/weights/last.pt 断点续训",
    )
    train_parser.add_argument(
        "--device",
        help="覆盖设备：auto / cuda / cpu / 0",
    )
    train_parser.add_argument(
        "--data",
        help="覆盖训练数据集 data.yaml，例如 models/刺蘑菇-僵尸蘑菇/data.yaml",
    )
    train_parser.add_argument(
        "--output",
        help="最佳权重输出名或路径；只写 xxx.pt 时保存到 models/xxx.pt",
    )
    train_parser.add_argument(
        "--run-name",
        help="覆盖 runs/ 下的训练任务名；默认使用输出 pt 的文件名",
    )
    train_parser.add_argument(
        "--resume-weights",
        help="指定续训使用的 last.pt；默认按本次任务名从 runs/<名称>/weights/last.pt 查找",
    )

    run_parser = subparsers.add_parser(
        "run",
        help="启动识别；默认打开监控面板，加 --cli 才用无界面模式",
    )
    run_parser.add_argument("--profile", help="覆盖 behavior.profile（面板下拉初始值也会同步）")
    run_parser.add_argument("--device", help="覆盖设备：auto / cuda / cpu / 0")
    run_parser.add_argument(
        "--cli",
        action="store_true",
        help="不打开监控面板，使用旧的命令行/OpenCV 调试窗",
    )
    mode_group = run_parser.add_mutually_exclusive_group()
    mode_group.add_argument("--dry-run", action="store_true", help="只显示决策，不发送按键")
    mode_group.add_argument("--live", action="store_true", help="发送真实按键")

    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    if args.command == "doctor":
        LOGGER.info(describe_torch_backend())
        from mxd_bot.device import resolve_device

        resolve_device("auto")
        return

    config = load_config(args.config)

    if args.command == "collect":
        collect_screenshots(config)
    elif args.command == "train":
        runtime_config = deepcopy(config)
        if getattr(args, "device", None):
            runtime_config["model"]["device"] = args.device
            runtime_config["training"]["device"] = args.device
        if args.data:
            runtime_config["training"]["data"] = args.data
        if args.output:
            runtime_config["training"]["output_weights"] = args.output
        if args.run_name:
            runtime_config["training"]["run_name"] = args.run_name
        if args.resume_weights:
            runtime_config["training"]["resume_weights"] = args.resume_weights
        train_model(runtime_config, resume=bool(args.resume))
    elif args.command in {"gui", "run"}:
        # 放在加载模型之前，权限不对就立刻失败，不用等几十秒。
        try:
            ensure_running_as_admin()
        except AdminRequiredError as exc:
            raise SystemExit(str(exc)) from exc

        if args.command == "gui" or not getattr(args, "cli", False):
            from mxd_bot.gui import run_gui

            runtime_config = deepcopy(config)
            if getattr(args, "device", None):
                runtime_config["model"]["device"] = args.device
            if args.command == "run":
                dry_run = True if args.dry_run else False if args.live else None
                if dry_run is not None:
                    runtime_config["behavior"]["dry_run"] = dry_run
                if args.profile:
                    if args.profile not in runtime_config["profiles"]:
                        available = ", ".join(runtime_config["profiles"])
                        raise ValueError(f"未知职业配置 {args.profile!r}，可选：{available}")
                    runtime_config["behavior"]["profile"] = args.profile
            run_gui(runtime_config)
            return

        dry_run = True if args.dry_run else False if args.live else None
        runtime_config = apply_overrides(config, args.profile, dry_run)
        if getattr(args, "device", None):
            runtime_config["model"]["device"] = args.device
        run_bot(runtime_config)


if __name__ == "__main__":
    main()
