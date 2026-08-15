from pathlib import Path

from mxd_bot.model_paths import (
    dataset_model_name,
    discover_weight_files,
    resolve_output_weights,
    sanitize_model_name,
)


def test_dataset_model_name_preserves_chinese(tmp_path: Path) -> None:
    data_path = tmp_path / "刺蘑菇-僵尸蘑菇" / "data.yaml"
    data_path.parent.mkdir()
    data_path.touch()

    assert dataset_model_name(data_path) == "刺蘑菇-僵尸蘑菇"


def test_sanitize_model_name_replaces_windows_invalid_chars() -> None:
    assert sanitize_model_name('蘑菇:<测试>?*') == "蘑菇--测试---"


def test_default_output_uses_dataset_folder_name(tmp_path: Path) -> None:
    data_path = tmp_path / "蘑菇" / "data.yaml"
    data_path.parent.mkdir()
    data_path.touch()
    models_dir = tmp_path / "models"

    assert resolve_output_weights(data_path, models_dir=models_dir) == (
        models_dir / "蘑菇.pt"
    )


def test_bare_output_name_is_saved_under_models(tmp_path: Path) -> None:
    data_path = tmp_path / "dataset" / "data.yaml"

    assert resolve_output_weights(
        data_path,
        "刺蘑菇",
        models_dir=tmp_path / "models",
    ) == (tmp_path / "models" / "刺蘑菇.pt")


def test_explicit_output_path_is_preserved(tmp_path: Path) -> None:
    data_path = tmp_path / "dataset" / "data.yaml"
    output = tmp_path / "exports" / "monster-v2.pt"

    assert resolve_output_weights(data_path, output) == output


def test_discover_weight_files_recursively_and_sorted(tmp_path: Path) -> None:
    first = tmp_path / "models" / "best.pt"
    second = tmp_path / "models" / "蘑菇" / "刺蘑菇.pt"
    second.parent.mkdir(parents=True)
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    (tmp_path / "models" / "ignore.txt").write_text("x", encoding="utf-8")

    assert discover_weight_files(tmp_path / "models") == [
        first.resolve(),
        second.resolve(),
    ]
