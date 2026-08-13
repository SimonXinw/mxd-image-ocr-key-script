"""把 Roboflow YOLO 导出目录导入到本仓库 dataset/。

支持：
- 检测框标签（class x y w h）
- 分割多边形标签（自动转成外接框）
- valid -> val
- 把 Roboflow 的 monster 显示名映射为 mob（标签数字 ID 不变）
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def polygon_to_xywh(coords: list[float]) -> tuple[float, float, float, float] | None:
    if len(coords) < 6 or len(coords) % 2 != 0:
        return None

    xs = coords[0::2]
    ys = coords[1::2]
    xmin = max(0.0, min(xs))
    xmax = min(1.0, max(xs))
    ymin = max(0.0, min(ys))
    ymax = min(1.0, max(ys))
    width = xmax - xmin
    height = ymax - ymin
    if width <= 0 or height <= 0:
        return None

    return ((xmin + xmax) / 2, (ymin + ymax) / 2, width, height)


def convert_label_line(line: str) -> str | None:
    parts = line.strip().split()
    if len(parts) < 5:
        return None

    class_id = parts[0]
    values = [float(item) for item in parts[1:]]

    if len(values) == 4:
        x, y, w, h = values
    else:
        box = polygon_to_xywh(values)
        if box is None:
            return None
        x, y, w, h = box

    return f"{class_id} {x:.6f} {y:.6f} {w:.6f} {h:.6f}"


def clear_split(dataset_root: Path, split: str) -> None:
    for kind in ("images", "labels"):
        target = dataset_root / kind / split
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True, exist_ok=True)


def import_split(source_root: Path, dataset_root: Path, source_split: str, target_split: str) -> int:
    source_images = source_root / source_split / "images"
    source_labels = source_root / source_split / "labels"
    if not source_images.exists():
        raise FileNotFoundError(f"找不到图片目录：{source_images}")

    clear_split(dataset_root, target_split)
    count = 0

    for image_path in sorted(source_images.iterdir()):
        if image_path.suffix.lower() not in IMAGE_SUFFIXES:
            continue

        label_path = source_labels / f"{image_path.stem}.txt"
        target_image = dataset_root / "images" / target_split / image_path.name
        target_label = dataset_root / "labels" / target_split / f"{image_path.stem}.txt"

        shutil.copy2(image_path, target_image)

        converted_lines: list[str] = []
        if label_path.exists():
            for raw_line in label_path.read_text(encoding="utf-8").splitlines():
                converted = convert_label_line(raw_line)
                if converted is not None:
                    converted_lines.append(converted)

        target_label.write_text("\n".join(converted_lines) + ("\n" if converted_lines else ""), encoding="utf-8")
        count += 1

    return count


def write_data_yaml(dataset_root: Path) -> None:
    content = """# 从 Roboflow maplestory_monster 导入。
# 标签数字 ID 保持 Roboflow 原样：0=怪，1=人。
# 显示名把 monster 映射成 mob，方便和 config.yaml 对齐。
path: .
train: images/train
val: images/val

names:
  0: mob
  1: player
"""
    (dataset_root / "data.yaml").write_text(content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="导入 Roboflow YOLO 数据集")
    parser.add_argument(
        "--source",
        default="models/maplestory_monster.v10i.yolov11",
        help="Roboflow 解压目录",
    )
    parser.add_argument("--dataset-root", default="dataset", help="本仓库 dataset 目录")
    args = parser.parse_args()

    source_root = Path(args.source)
    dataset_root = Path(args.dataset_root)
    if not source_root.exists():
        raise FileNotFoundError(f"找不到源目录：{source_root}")

    train_count = import_split(source_root, dataset_root, "train", "train")
    val_count = import_split(source_root, dataset_root, "valid", "val")
    write_data_yaml(dataset_root)

    print(f"已导入 train={train_count}, val={val_count}")
    print(f"data.yaml 已写入：{dataset_root / 'data.yaml'}")
    print("类别映射：Roboflow monster(0) -> mob，player(1) -> player")
    print("下一步：python -m mxd_bot --config config.yaml train")


if __name__ == "__main__":
    main()
