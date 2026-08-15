# MXD 屏幕视觉自动化实验框架

这是一个 Windows 上运行的纯屏幕视觉原型：

1. `mss` 截取指定游戏窗口；
2. 自定义 YOLO 模型识别 `player` 和 `mob`；
3. 计算玩家与最近怪物的横向、纵向距离；
4. 状态机决定攻击、左右移动、跳跃或巡逻；
5. 演练模式只画检测框，确认无误后才允许发送键盘操作。

它不读取内存、不注入进程、不修改客户端，但游戏运营方仍可能禁止自动化。建议仅用于自建环境、视觉研究和获准的功能测试。

## 当前能力与边界

- 面向“单张地图、战士或牧师刷怪”的第一版。
- 可通过 YAML 修改攻击距离、按键、冷却和 Buff 周期。
- 换地图后通常需要补充新地图截图并增量训练。
- 支持两种玩家定位：
  - YOLO 检测 `player` 类；
  - OpenCV 匹配自己的名字截图；
  - 默认 `hybrid`：优先名字模板，找不到时回退到 YOLO。
- 当前只处理附近/同层或略高平台的怪物，不包含完整地图建模、绳梯、传送点、自动补药和死亡恢复。

## 文档导航

| 想知道什么 | 看这里 |
| --- | --- |
| 怎么装、怎么跑、怎么训练 | 本文件 |
| 打怪逻辑到底怎么判定的、参数怎么调 | [`docs/combat-flow.md`](docs/combat-flow.md)（含可直接生成图片的 Mermaid 流程图） |
| 之前为什么改成现在这样、参数改前改后 | [`CHANGELOG.md`](CHANGELOG.md) |

改了 `decision.py`、`input_controller.py`、`player_locator.py`、`detector.py`、`capture.py` 或配置参数后，要同步更新前两份文档。`.cursor/rules/keep-docs-in-sync.mdc` 会在改到这些文件时自动提醒 AI；想一次性全量核对，让 AI 执行 `.cursor/skills/sync-combat-docs`。

## 回家测试清单

打开冒险岛后可以开始测，但**不要直接 `--live`**。按这个顺序：

1. 游戏用**窗口模式**，分辨率先固定；`config.yaml` 已经在仓库里，直接改它即可。
2. 把 `window.title_contains` 改成你实际窗口标题里稳定的一段。
3. 采集截图：

```powershell
C:\mxd-venv\Scripts\python.exe -m mxd_bot --config config.yaml collect
```

4. 标注 `player` / `mob`，整理进 `dataset/images` 与 `dataset/labels`。
5. 训练自己的模型：

```powershell
C:\mxd-venv\Scripts\python.exe -m mxd_bot --config config.yaml train
```

6. 启动就会打开监控面板（默认）：

```powershell
C:\mxd-venv\Scripts\python.exe -m mxd_bot --config config.yaml run
```

`gui` 命令效果相同。左侧可切换职业、演练/真实、目标帧率；右侧是截屏镜像+检测框。

只要命令行、不要面板时：

```powershell
C:\mxd-venv\Scripts\python.exe -m mxd_bot --config config.yaml run --cli --profile warrior --dry-run
```

7. 框和方向都对了，在面板里取消「演练模式」后再点开始；或：

```powershell
C:\mxd-venv\Scripts\python.exe -m mxd_bot --config config.yaml run --live
```

重要：仓库里如果已有 `models/best.pt`，也可能只是合成色块冒烟模型，**不能直接认游戏怪物**。回家第一件事是采真实截图并重新训练。

### 已下载 Roboflow 数据集时

如果 ZIP 解压到了 `models/maplestory_monster.v10i.yolov11`：

```powershell
C:\mxd-venv\Scripts\python.exe scripts\import_roboflow_yolo.py
C:\mxd-venv\Scripts\python.exe -m mxd_bot --config config.yaml train
```

导入脚本会：

1. 把 `train/valid` 拷进本仓库 `dataset/`；
2. 把 Roboflow 的多边形标签转成检测框；
3. 把类别显示名 `monster` 映射成项目里的 `mob`（标签数字 ID 不变：0=怪，1=人）。

## 项目结构

```text
.
├─ config.yaml               # 程序实际读取的正式配置，已入库，改这份
├─ config.example.yaml       # 参数说明书：每项的含义和可选值，数值不必与上面一致
├─ CHANGELOG.md              # 累计变更记录和调参理由
├─ dataset/data.yaml         # YOLO 类别及数据集路径
├─ docs/combat-flow.md       # 打怪逻辑流程图与参数速查
├─ .cursor/
│  ├─ rules/                 # 改核心模块时自动触发的文档同步规则
│  └─ skills/                # 手动调用的全量文档核对流程
├─ src/mxd_bot/
│  ├─ capture.py             # 按窗口标题截取客户区
│  ├─ detector.py            # YOLO 实时推理
│  ├─ player_locator.py      # 名字模板 / YOLO 玩家定位
│  ├─ decision.py            # 选怪和行为状态机
│  ├─ input_controller.py    # 演练或真实键盘输出
│  ├─ collect.py             # 截图采集
│  └─ train.py               # YOLO 训练
└─ tests/                    # 不依赖游戏的决策测试
```

## 1. 安装

建议使用 Python 3.11、3.12 或 3.13。本机实测安装 `torch` 时，项目目录过长会触发 Windows `WinError 206`，因此虚拟环境请放到短路径：

```powershell
cd C:\Users\Administrator\Desktop\projects\xw\ai-projects\mxd-image-ocr-key-script
py -3.13 -m venv C:\mxd-venv
C:\mxd-venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

如果 PowerShell 禁止激活脚本，可只对当前终端执行：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
C:\mxd-venv\Scripts\Activate.ps1
```

不想激活虚拟环境时，也可以直接用：

```powershell
C:\mxd-venv\Scripts\python.exe -m mxd_bot --config config.yaml --help
```

### NVIDIA GPU（推荐）

默认配置 `device: auto`：有 NVIDIA CUDA 就用显卡，没有就回退 CPU。

检查设备：

```powershell
C:\mxd-venv\Scripts\python.exe -m mxd_bot doctor
```

如果显示 CPU / `cuda=unavailable`，在虚拟环境中安装 CUDA 版 PyTorch（本机已验证 `cu124` + GTX 1660 SUPER）：

```powershell
C:\mxd-venv\Scripts\python.exe -m pip uninstall -y torch torchvision
C:\mxd-venv\Scripts\python.exe -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
C:\mxd-venv\Scripts\python.exe -m mxd_bot doctor
```

开关方式：

```yaml
model:
  device: auto   # auto | cuda | cpu | 0
training:
  device: auto   # 可不写，默认跟随 model.device
```

命令行临时覆盖：

```powershell
C:\mxd-venv\Scripts\python.exe -m mxd_bot --config config.yaml train --device cuda
C:\mxd-venv\Scripts\python.exe -m mxd_bot --config config.yaml train --device cpu
C:\mxd-venv\Scripts\python.exe -m mxd_bot --config config.yaml run --profile warrior --dry-run --device cuda
```

## 2. 修改基础配置

`config.yaml` 是程序实际读取的配置，已经在仓库里，直接编辑：

```yaml
window:
  title_contains: "北斗GMS083"

behavior:
  profile: "warrior"
  dry_run: false
```

- `title_contains` 必须能匹配游戏窗口标题，可只写标题中稳定的一部分。
- GUI 下拉框显示中文职业；内部配置键仍是战士 `warrior`、法师/牧师 `priest`。
- 当前攻击范围：战士 180，法师/牧师 230；选择职业后会自动使用对应配置。
- 按键和技能冷却在 `profiles` 下修改。
- 当前默认 `dry_run: false`（直接真实发键）。换地图、改参数后想先只看识别，把它改回 `true` 或在 GUI 勾「仅预览」。
- 游戏使用窗口模式，训练和运行时保持相同分辨率与 UI 缩放。

不确定某个配置项是什么意思、有哪些可选值时，查 `config.example.yaml`——那份是参数说明书，注释最全，数值只是通用起点，不必和 `config.yaml` 一致。战斗参数怎么调看 [`docs/combat-flow.md`](docs/combat-flow.md)。

## 3. 采集训练图片

先进入目标地图并正常移动、攻击，让截图包含：

- 怪物的站立、移动、受击、转身等动作；
- 玩家左右朝向、跳跃、攻击和被特效部分遮挡的情况；
- 有怪、无怪、UI 遮挡等负样本。

两种方式任选其一：

1. **GUI（推荐）**：`run` 打开面板后勾选「开始截图」，再点开始。会按 `collection.interval_seconds`（当前 1s）把原始游戏画面存到 `captures/`，不影响识别和打怪。
2. **单独采集命令**：

```powershell
python -m mxd_bot --config config.yaml collect
```

单独采集会倒计时 3 秒，然后按同样间隔保存：

- `F9`：停止；
- 预览窗口按 `q`：停止；
- `Ctrl+C`：紧急停止。

单地图建议先采集 300～800 张有差异的截图。连续几乎相同的图片不要全部拿去训练，否则验证分数可能虚高。

## 4. 标注图片

可使用 [CVAT](https://www.cvat.ai/)、[Label Studio](https://labelstud.io/) 或 Roboflow，导出 **YOLO Detection** 格式。

第一版固定两个类别，类别顺序必须和 `dataset/data.yaml` 一致：

```text
0 player
1 mob
```

标注规则：

1. `player`：只框自己的角色身体，不框名字、宠物和技能特效。
2. `mob`：每只活着的怪各画一个紧贴身体的框。
3. 被遮挡但仍能辨认的目标也要标；完全看不见的不标。
4. 同一种目标必须保持一致，不要有时框身体、有时连名字一起框。
5. 无怪图片保留为空标签，能降低误报。

按约 80%/20% 随机分为训练集和验证集，最终目录必须是：

```text
dataset/
├─ data.yaml
├─ images/
│  ├─ train/*.png
│  └─ val/*.png
└─ labels/
   ├─ train/*.txt
   └─ val/*.txt
```

每张图片和标签文件同名，例如 `abc.png` 对应 `abc.txt`。

> 如果使用名字模板定位玩家，可以只训练 `mob`，但要同步调整 `dataset/data.yaml` 的类别和模型输出；初次使用仍建议同时标 `player`，便于回退。

## 5. 训练 YOLO

确认数据目录完成后：

```powershell
C:\mxd-venv\Scripts\python.exe -m mxd_bot --config config.yaml train
```

中途可用 `Ctrl+C` 停止。要接着上次进度续训：

```powershell
C:\mxd-venv\Scripts\python.exe -m mxd_bot --config config.yaml train --resume
```

续训读取 `runs/mxd_detect/weights/last.pt`。如果这个文件不存在，说明还没有可续的断点，需要先完整开训一次。

默认从 `yolo11n.pt` 迁移学习 100 轮。训练结果在：

```text
runs/mxd_detect/
```

最佳权重会自动复制到：

```text
models/best.pt
```

显存不足时修改：

```yaml
training:
  batch: 4
  image_size: 640
```

CPU 训练过慢时可用带 GPU 的电脑或 Colab 训练，再把 `best.pt` 放到本项目的 `models/`。

不要只看训练集结果。至少检查 `runs/mxd_detect/val_batch*_pred.jpg`、混淆矩阵以及实际游戏预览；漏检多就补漏检场景，误报多就补相似背景的负样本。

## 6. 先以演练模式启动

`run` / `gui` 默认都会打开监控面板（方案 A：左控制 + 右预览）。**必须用管理员身份的 PowerShell 启动**，否则会直接报错退出：

```powershell
C:\mxd-venv\Scripts\python.exe -m mxd_bot --config config.yaml run
```

- 预览是游戏截屏镜像，不是第二个客户端，可拖到冒险岛窗口旁边对照。
- 默认识别帧率 60（`ui.target_fps`）、预览帧率 24（`ui.preview_fps`）。1660S 这类显卡建议把识别降到 30。
- 默认不勾「仅预览」，点开始就会真实发键，并把游戏窗口切到前台一次。想先空跑就勾上「仅预览」。

只要命令行、不要面板：

```powershell
C:\mxd-venv\Scripts\python.exe -m mxd_bot --config config.yaml run --cli --profile warrior --dry-run
```

牧师：

```powershell
python -m mxd_bot --config config.yaml run --profile priest --dry-run
```

调试窗口会显示检测框、FPS 和当前决策。确认以下项目后才能进入真实模式：

- 自己的位置稳定，不能把其他玩家当成自己；
- 怪物框没有频繁跳动或把 UI 当怪物；
- 近距离显示 `attack`；
- 怪物在左/右侧时显示对应移动；
- 找不到自己时必须显示 `idle`；
- 没怪时才显示左右巡逻。

快捷键：

- `F8`：暂停/继续；
- `F9`：停止并释放按键；
- 调试窗口 `q`：停止；
- `Ctrl+C`：紧急停止；
- PyDirectInput 默认还支持鼠标移到屏幕左上角触发 failsafe。

## 7. 真实按键模式

只有演练稳定后才运行：

```powershell
python -m mxd_bot --config config.yaml run --profile warrior --live
```

启动后有倒计时。真实模式用 `SendInput` 扫描码发键。**只在启动时把游戏窗口切到前台一次**，之后运行期间不会再抢焦点。切回游戏时，如果正在长按移动，会自动重新按下当前方向键。

攻击距离和按键示例：

```yaml
profiles:
  warrior:
    attack_key: "ctrl"
    jump_key: "alt"
    attack_range_pixels: 180
    attack_cooldown_seconds: 0.40
  priest:
    attack_key: "ctrl"
    jump_key: "alt"
    attack_range_pixels: 230
    attack_cooldown_seconds: 0.75
```

实际攻击范围取决于职业、技能和分辨率，需要在演练窗口根据像素距离调整。

## 8. 使用自己的名字定位

YOLO 玩家框会受换装备、职业和特效影响。名字固定时，模板匹配通常更稳定：

1. 在游戏原始分辨率下截一张图。
2. 只裁剪自己头顶/脚下的名字文字，尽量不要包含变化背景。
3. 保存为 `assets/player_name.png`。
4. 保持配置：

```yaml
player:
  locator: "hybrid"
  name_template: "assets/player_name.png"
  template_threshold: 0.82
  template_center_offset: [0, -55]
```

绿色圆点应落在角色身体中心。偏了就调整 `template_center_offset`；名字在角色下方时，Y 通常是负数。分辨率、字体缩放或名字变化后要重新截图。

## 9. 换地图和增量训练

换图时不要立刻重头训练：

1. 在新地图再采 200～500 张；
2. 标注后混入旧数据，确保旧地图不会遗忘；
3. 将 `training.base_model` 改为当前 `models/best.pt`；
4. 训练 30～80 轮并重新检查两个地图。

如果新图有多层平台、绳梯或传送点，仅靠“最近怪物”会做出错误路线。此时应为每张地图增加小地图定位、平台区域和预设巡逻路线，而不是盲目增加 YOLO 轮数。

## 10. 常见问题

### 找不到游戏窗口

修改 `window.title_contains`，确保窗口可见且没有最小化。标题匹配忽略大小写。

### `models/best.pt` 不存在

先完成标注并运行训练，或者把其他电脑训练出的权重复制到该路径。

### FPS 很低

- 使用 `yolo11n.pt` / nano 权重；
- 保持 `image_size: 640` 或降低到 512；
- 配置 `capture_region` 只截游戏场景；
- 安装正确的 CUDA PyTorch；
- 关闭不必要的调试窗口后再评估。

### 按键没有效果

- 先用演练确认决策正常；
- 确保使用 `--live`（或 GUI 取消「仅预览」）；
- 真实模式用 `SendInput` 扫描码发键，只在启动时抢一次焦点；切回游戏且仍在长按移动时会重按方向键；
- 必须以管理员身份运行。非管理员启动 `run` / `gui` 会直接报错退出，因为 Windows 的 UIPI 不允许低权限进程向游戏窗口注入输入，按键会被系统静默丢弃；
- 不要通过关闭 UAC 等方式绕过系统安全边界，用管理员身份启动即可。

### 训练准确但游戏里漏检

常见原因是验证集和训练集来自同一段连续截图。按采集时间段或实际场景划分验证集，并补充攻击特效、边缘位置和不同怪物动作。

## 11. 开发检查

```powershell
python -m compileall -q src tests
pytest
ruff check .
```

核心逻辑测试不需要启动游戏或加载 YOLO 权重。