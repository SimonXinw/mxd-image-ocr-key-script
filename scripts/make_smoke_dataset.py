from pathlib import Path

import cv2
import numpy as np

root = Path("dataset")
for split in ["train", "val"]:
    (root / "images" / split).mkdir(parents=True, exist_ok=True)
    (root / "labels" / split).mkdir(parents=True, exist_ok=True)

rng = np.random.default_rng(0)


def make_sample(path_img: Path, path_lbl: Path, n_mobs: int) -> None:
    img = np.full((480, 640, 3), 40, dtype=np.uint8)
    labels: list[str] = []

    px, py, pw, ph = 300, 280, 40, 70
    cv2.rectangle(img, (px, py), (px + pw, py + ph), (0, 220, 0), -1)
    labels.append(
        f"0 {(px + pw / 2) / 640:.6f} {(py + ph / 2) / 480:.6f} {pw / 640:.6f} {ph / 480:.6f}"
    )

    for _ in range(n_mobs):
        mx = int(rng.integers(30, 560))
        my = int(rng.integers(80, 380))
        mw, mh = 36, 36
        cv2.rectangle(img, (mx, my), (mx + mw, my + mh), (0, 0, 220), -1)
        labels.append(
            f"1 {(mx + mw / 2) / 640:.6f} {(my + mh / 2) / 480:.6f} {mw / 640:.6f} {mh / 480:.6f}"
        )

    if not cv2.imwrite(str(path_img), img):
        raise OSError(f"failed to write {path_img}")
    path_lbl.write_text("\n".join(labels) + "\n", encoding="utf-8")


for i in range(24):
    make_sample(
        root / "images" / "train" / f"t{i:02d}.png",
        root / "labels" / "train" / f"t{i:02d}.txt",
        n_mobs=2 + i % 3,
    )

for i in range(6):
    make_sample(
        root / "images" / "val" / f"v{i:02d}.png",
        root / "labels" / "val" / f"v{i:02d}.txt",
        n_mobs=2,
    )

print("synthetic dataset ready")
