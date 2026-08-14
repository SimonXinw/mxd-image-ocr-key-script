# 变更记录

累计记录这个项目做过什么、为什么这么做、调了哪些参数。目的是隔一段时间回来能想起当时的结论，不用重看代码。

写法约定：

- 最新的放最上面，按日期分段（`## YYYY-MM-DD`）。
- 每条用 `feat` / `fix` / `chore` / `refactor` 前缀，和 commit 规范保持一致。
- 涉及调参的，写清**改前 → 改后**和**为什么**，这是最值钱的部分。
- 只记有决策价值的事，不记流水账（改个错别字不用写）。

条目模板：

```markdown
## YYYY-MM-DD

### feat: 一句话说清做了什么

- 背景：遇到了什么现象 / 想解决什么。
- 做法：改了哪些文件、什么思路。
- 参数：`config.yaml` 的 `xxx` 从 A 改成 B，因为……
- 影响：需要同步更新 `docs/combat-flow.md` / `README.md` 的哪一节。
```

---

## 2026-08-14

### chore: 澄清攻击/巡逻/跳跃判定，确认暂不改代码

- 背景：排疑时容易把 `attack_range` + 迟滞理解成「只有 180～220 才打」；跳跃也容易理解成脚底高度差；巡逻触发条件不够直观。
- 结论（故意不改 `decision.py`）：
  1. 攻击本就是 `0 ≤ abs(dx) ≤ attack_limit`，贴脸会打，代码正确。
  2. 竖直距离继续用框中心。改脚底会牵动已调通的 `jump_when_target_above_pixels=45` 和 `target_vertical_tolerance=140`，等出现明显「同层误判」再改。
  3. 巡逻继续只在完全无怪时启动；有怪不可达保持 `idle`。
- 做法：更新 `docs/combat-flow.md`——补检测类/动作类表、流程图节点写明「贴脸也算」「无怪才巡逻」「中心点距离」、参数表改写攻击与跳跃含义、增加「常见误解」三节。
- 参数：无数值变动。

### chore: 明确 config.yaml 为正式配置，example 降级为参数说明书

- 背景：README 一直把 `config.yaml` 描述成"本地文件、需要从 example 复制"，但它其实早就入库了，导致文档里出现「以 example 数值为准」这种错误约定。两份文件也已经漂移（`confidence` 0.25/0.45、warrior `attack_range_pixels` 220/180、`template_center_offset` -55/-49）。
- 做法：确认 `.gitignore` 不忽略 `config.yaml`，代码里也没有任何地方回写它（只有 `train.py` 写 `runs/mxd_data.resolved.yaml`），因此可以放心手工维护注释。把之前被工具重写掉的引号和分节顺序整理回来，解析结果与提交版本逐键比对为完全一致。`config.example.yaml` 顶部加说明，定位为参数说明书：保留全部注释和通用默认值，**明确不追求数值一致**，只在新增配置项时两边都加键。
- 影响：`README.md` 删掉复制 example 的安装步骤、更新项目结构和第 2 节；`docs/combat-flow.md` 参数表来源改为 `config.yaml`；`.cursor/rules/keep-docs-in-sync.mdc` 与 `.cursor/skills/sync-combat-docs/SKILL.md` 反转了「以谁为准」；`src/mxd_bot/config.py` 的缺失提示改为提示 `git restore`。

### fix: 修复决策引擎测试，补上锁定与迟滞的用例

- 背景：加了目标锁定帧数确认和动作防抖后，`tests/test_decision.py` 挂了 4 个——旧用例都假设一帧就能出结果，等于决策引擎这段最容易出错的代码已经没有测试保护。
- 做法：加 `feed()` 辅助函数连续喂帧；`test_jumps_toward_monster_on_higher_platform` 的怪原来在 dx=120，现在会先落进攻击范围，改到 dx=200 才真的触发跳跃；`test_ignores_monster_outside_vertical_tolerance` 期望值从 `PATROL_RIGHT` 改成 `IDLE`，因为"有怪但够不着就站着别乱巡逻"是有意为之，另起一个空怪列表的用例覆盖巡逻。新增攻击迟滞进出边界、超出追击距离、单帧闪烁误检三个用例。
- 影响：10 个用例全过。

### chore: 建立文档与 AI 协作机制

- 背景：打怪逻辑越改越复杂，参数散落在 `config.yaml` 和几个模块里，聊完就忘。
- 做法：新增 `docs/combat-flow.md` 作为战斗逻辑唯一权威说明（Mermaid 流程图 + 参数速查 + 代码位置对照）；新增本文件累计历史；新增 `.cursor/rules/keep-docs-in-sync.mdc`（按文件 glob 触发）和 `.cursor/skills/sync-combat-docs/`（按需手动调用）。
- 影响：以后改核心模块，规则会提醒同步文档。

### feat: 用 ByteTrack + 多重防抖稳住选怪和动作

- 背景：怪物移动时 YOLO 分数会瞬间下降，检测框闪断，导致机器人左右横跳、不停换目标、该打的怪不打。
- 做法：
  - `model.tracking_enabled` 开启 ByteTrack，`Box` 增加 `track_id`，锁定目标按 ID 匹配而不是按坐标猜。
  - `decision.py` 增加 `_stabilize_action()`：攻击立即响应，其余动作要连续确认几帧才切换。
  - 攻击范围加迟滞：已在攻击状态时多容忍 `attack_release_margin_pixels`，避免在边界反复走走停停。
  - 目标丢失后有 `target_lost_grace_seconds` 宽限期，先按旧位置追，确认消失才重新选。
  - 新目标要连续出现 `target_acquire_frames` 帧才锁定，过滤一闪而过的远处误检。
- 参数：`confidence` 0.08 → 0.45；`attack_range_pixels` 150 → 180；`attack_cooldown_seconds` 0.48 → 0.40；`target_vertical_tolerance` 110 → 140；新增 `max_chase_horizontal_pixels: 420`。
- 影响：`docs/combat-flow.md` 的流程图和参数表。

### fix: 方向键被游戏当成小键盘数字

- 背景：手按方向键正常，程序模拟按键却变成打字。
- 做法：`input_controller.py` 改用 `SendInput` 直接发扫描码；发方向键前临时关掉 NumLock，停止时恢复。
- 影响：无配置项，属于底层修复。

### fix: 角色走到右下角时绿框飞到左下角

- 背景：UI 区域有和角色名字相似的文字，模板匹配误命中。
- 做法：`player_locator.py` 的名字搜索限定在画面垂直中间区域，并优先靠近上一帧玩家位置的匹配。
- 参数：新增 `search_center_x_ratio: 1.0`、`search_center_y_ratio: 0.40`。

### refactor: 移除输入前按 Esc 关聊天框的逻辑

- 背景：每次发键前按 Esc 会误关游戏菜单、打断动作。
- 做法：删掉 `close_chat_before_input` 配置和相关代码。

### feat: GUI 面板补齐运行时开关

- 做法：攻击 / 跳跃 / 方向 / 吃药按键改成下拉框可选并支持手动测试（手动测试绕过演练模式，直接发真键）；新增「自动攻击」独立开关，不再和演练模式绑在一起；识别帧率与预览帧率拆成两个设置；布局压缩成顶部工具条 + 右侧窄面板 + 主预览区。
- 参数：新增 `behavior.auto_attack_enabled`、`ui.preview_fps`。

### fix: 窗口抓取与玩家模板加载

- `capture.py` 抓取顺序定为 mss 优先，其次 PrintWindow、BitBlt；mss 是纯屏幕读取，对游戏进程零交互，被检测风险最低。
- `player_locator.py` 修复 RGBA 模板图触发的 `ValueError: too many values to unpack`，先合成到背景再转灰度。
- `overlay.py` 按定位来源区分颜色：模板绿框、YOLO 黄框、中心兜底灰框，并加了图例。

---

## 2026-08-13 及更早

对应 commit：`1d5fdbd` 移动打怪、`70a2aa0` 窗口抓取、`2ad390d` GUI 面板、`d87f317` 数据集训练、`e0f7884` 初始化。

- 搭起纯屏幕视觉流水线：截图 → YOLO → 决策状态机 → 键盘模拟，全程不读内存、不注入进程。
- 完成第一版 YOLO 训练流程（`collect` / `train`），支持 Roboflow 数据集导入。
- 完成 PySide6 监控面板，`run` 默认开面板，`--cli` 才走无界面。
