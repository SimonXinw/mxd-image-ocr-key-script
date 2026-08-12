from __future__ import annotations

import argparse
import logging

from mxd_bot.app import run_bot
from mxd_bot.collect import collect_screenshots
from mxd_bot.config import apply_overrides, load_config
from mxd_bot.train import train_model


def main() -> None:
    parser = argparse.ArgumentParser(description="MXD 屏幕视觉自动化实验框架")
    parser.add_argument("--config", default="config.yaml", help="YAML 配置文件路径")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("collect", help="从游戏窗口采集训练截图")
    subparsers.add_parser("train", help="训练 YOLO 检测模型")

    run_parser = subparsers.add_parser("run", help="启动实时识别与决策")
    run_parser.add_argument("--profile", help="覆盖 behavior.profile")
    mode_group = run_parser.add_mutually_exclusive_group()
    mode_group.add_argument("--dry-run", action="store_true", help="只显示决策，不发送按键")
    mode_group.add_argument("--live", action="store_true", help="发送真实按键")

    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    config = load_config(args.config)

    if args.command == "collect":
        collect_screenshots(config)
    elif args.command == "train":
        train_model(config)
    elif args.command == "run":
        dry_run = True if args.dry_run else False if args.live else None
        runtime_config = apply_overrides(config, args.profile, dry_run)
        run_bot(runtime_config)


if __name__ == "__main__":
    main()
