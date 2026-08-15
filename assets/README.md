# 玩家名字模板

需要使用名字定位时，把只包含自己游戏名字的裁剪图保存为：

```text
assets/player_name.png
```

该图片不会提交到 Git。训练和运行时必须保持相同的游戏分辨率、字体缩放和 UI 缩放。

# 血蓝条 ROI 标定参考

```text
assets/vitals_roi_ref.png
```

满血满蓝截图上画出的 HP/MP 框，对应 `config.yaml` 的 `vitals.hp_roi` / `vitals.mp_roi`。
换 UI 或分辨率后，用新截图重标这两个比例。
