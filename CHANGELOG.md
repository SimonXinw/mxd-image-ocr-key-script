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

## 2026-08-15

### feat: 多模型按数据集命名并可在 GUI 下拉切换

- 背景：不同怪物数据集都输出 `best.pt` 容易覆盖，也无法在预览窗口快速选择模型。
- 训练：默认按 `data.yaml` 所在文件夹命名，复制到 `models/<数据集名>.pt`；新增 `--data`、`--output`、`--run-name`、`--resume-weights` 参数。
- GUI：递归扫描 `model.weights_dir` 中的 `.pt`，显示模型下拉框和刷新按钮；所选权重仅在本次启动时传给 Worker。
- 中文：模型文件名和 GUI 显示保留中文。
- 数据集：修正 `models/刺蘑菇-僵尸蘑菇/data.yaml` 多写一层 `../` 的路径；类别保持 Roboflow 原名 `monster`。`monster_classes` 同时接受 `mob` 与 `monster`，兼容旧 `best.pt`。
- 文档：同步 `README.md`、`config.yaml`、`config.example.yaml`、`docs/combat-flow.md`、本文件。

### feat: GUI 增加「开始截图」，采集间隔改为 1 秒

- 背景：每次采集都要单独跑 `collect` 命令不方便；希望像「仅预览」一样勾一下就能边跑边存图。
- 做法：顶部栏新增「开始截图」勾选框，写入 `collection.enabled`；`gui_worker` 运行期间按间隔保存原始画面到 `captures/`。抽出 `save_capture_frame()` 供 GUI 与 `collect` 共用。
- 参数：`collection.interval_seconds` 从 `0.35` → `1.0`；新增 `collection.enabled`（默认 `false`）。
- 文档：同步 `README.md`、`config.example.yaml`、本文件。

### fix: 非管理员启动直接报错退出，不再只打一条警告

- 背景：原 `_warn_if_not_admin()` 只是 `LOGGER.warning`，容易被日志淹没，用户还会误以为是项目代码主动丢了按键。
- 澄清：按键丢弃是 **Windows 内核 UIPI** 干的，项目代码从头到尾没有因权限跳过发键（`_ready` 只跟 `dry_run` 有关）。这一层用户态绕不过去，本项目要求必须管理员运行。
- 做法：删掉 `_warn_if_not_admin()`，改为模块级函数 `ensure_running_as_admin()`，只判断 `IsUserAnAdmin()`，不是管理员就抛 `AdminRequiredError`。调用点放在 `__main__.py` 的 `run` / `gui` 分支最前面，**在加载 YOLO 模型之前**就失败，不用等几十秒；`SystemExit` 输出一行中文提示，没有 traceback。`collect` / `train` / `doctor` 不需要管理员，不受影响。
- 测试：权限用例精简为 2 个（非管理员报错、管理员放行）；共 20 个用例通过。
- 文档：同步 `docs/combat-flow.md`、`README.md`、本文件。

### fix: 焦点只在启动时抢一次，运行期间不再打断其他软件

- 背景：`_focus_target_window` 在每次攻击、移动、跳跃前都会 `ShowWindow` + `SetForegroundWindow`，导致切到别的软件后冒险岛客户端立刻被弹回最上层。
- 做法：新增 `InputController.focus_game_window_once()`，由 `app.py` 和 `gui_worker.py` 在真实模式启动时各调一次；之后不再调用任何聚焦 API。用 `GetForegroundWindow()` 跟踪前台变化。
- 恢复移动：切回游戏时，如果 `_held_direction` 仍在长按，直接再发一次方向键 `keyDown`；不额外改后台停键等逻辑。
- 测试：覆盖启动聚焦一次、已在前台则不聚焦、运行期间不抢焦点、切回后重按方向键；共 20 个用例通过。
- 文档：同步 `docs/combat-flow.md`、`README.md`、本文件。

### chore: 默认改为真实模式，识别 60 帧 / 预览 24 帧

- 参数：`behavior.dry_run` 从 `true` 改成 `false`（调试阶段结束，默认直接打）；`ui.target_fps` 从 30 改成 60（提高反应速度）；`ui.preview_fps` 从 15 改成 24（画面顺一点，同时不跟着识别帧率白烧 CPU）。
- 做法：同步 `gui_app.py`、`gui_worker.py` 里读配置失败时的兜底默认值，避免配置缺项时又退回旧值。
- 影响：GUI 打开时「仅预览」默认不勾，点开始即真实发键并把游戏切前台一次。低配显卡请把识别帧率手动降回 30。

### fix: 明确权限不一致导致按键被系统拦截

- 背景：检测、决策和游戏焦点均正常，但角色完全不响应模拟按键。
- 已确认原因：游戏以管理员权限运行，脚本不是管理员；Windows UIPI 会静默拦截低权限进程向高权限进程注入的 `SendInput`。
- 做法：保留启动时的管理员权限告警及焦点诊断日志；删除基于错误推断加入的焦点防抖、修饰键清理和分层自测代码。
- 发键方式：继续使用与已验证版本一致的 `SendInput` 扫描码，不读取、不修改游戏内存，也不注入游戏进程。
- 文档：同步 `docs/combat-flow.md`、`README.md`、本文件。

### feat: 职业下拉框改为中文并使用独立攻击范围

- 背景：职业下拉框只显示 `warrior/priest`，且正式配置中两个职业攻击范围都是 180，无法直观看出选择职业后的距离差异。
- 做法：GUI 显示「战士（攻击范围 180）」和「法师/牧师（攻击范围 230）」，内部仍使用原有配置键，避免破坏 CLI；选择后继续由对应 `profiles` 配置创建决策引擎。
- 参数：`profiles.priest.attack_range_pixels` 从 180 → 230；战士保持 180，若实测远距离空放再降到 160。
- 文档：同步 `docs/combat-flow.md`、`README.md`、本文件。

### fix: 去掉前台停键与抢焦点，直接发键

- 背景：前台检查会把真实模式卡住；抢焦点又会干扰预览面板操作。
- 做法：删除停键拦截和 `SetForegroundWindow`，真实模式直接 `SendInput`。
- 边界：游戏需保持前台才能收到按键。
- 文档：同步 `docs/combat-flow.md`、`README.md`、本文件。

## 2026-08-14

### fix: 游戏失去前台时暂停发键，不再强制抢焦点

- 背景：`input_controller.py` 原先在每次攻击、移动、跳跃和手动测试前调用 `ShowWindow` + `SetForegroundWindow`。用户切到其他软件后，下一次动作会立即把冒险岛重新拉到最前面。
- 做法：彻底删除主动聚焦逻辑。发送任何自动按键、Buff 或手动测试前只检查目标 HWND 是否为前台窗口；不是前台时立即松开持续方向键、恢复 NumLock 并暂停发键，识别和预览继续，GUI 状态显示「后台停键」。切回游戏后自动恢复。
- 边界：游戏进程不会暂停，角色站在原地仍可能被怪攻击；该保护只负责阻止按键误发到其他软件。
- 测试：新增后台窗口暂停、切回游戏恢复两个测试；共 14 个用例通过。
- 文档：同步更新 `README.md` 和 `docs/combat-flow.md` 的输入流程。

### fix: 竖直导航改用脚底坐标，避免大小怪误判层级

- 背景：原逻辑用检测框中心 Y 判断同层和跳跃。高矮不同的怪站在同一平台时中心 Y 天然不同，会误判成上层怪；同一只怪动画改变框高度也会让中心漂移。
- 依据：参考纯视觉项目 [TinForge/MS-ML-Bot](https://github.com/TinForge/MS-ML-Bot)，其同平台判断使用 `player.y2`、`mob.y2` 与平台顶边，即检测框底部；项目检测类也包含 `Player`、`Mob`、`Platform`、`Ladder`。其他成熟项目则通常用小地图 + 平台/梯子路线图做跨层寻路，而不是只靠人物与怪物中心距离。
- 做法：`Box` 新增 `ground_point`（框底中心）；`decision.py` 的可达过滤、最近目标代价、候选匹配、锁定目标匹配、攻击高度和跳跃高度统一改用地面锚点。横向位置仍是中心 X。
- 测试：增加「同平台但框高度不同仍攻击」和「框高度不同仍按脚底差跳跃」两个用例；共 12 个用例通过。
- 分类结论：当前权重继续保持 `mob/player` 两类。平台寻路下一阶段应扩成 `mob/player/platform/ladder` 四类；`up` 是输入动作，不是检测类。没有标注和重训前不提前改 `dataset/data.yaml`，避免破坏现有模型类别映射。
- 参数：无数值变动；`jump_when_target_above_pixels=45` 与 `target_vertical_tolerance=140` 的语义从「中心 Y 差」改成「脚底 Y 差」。
- 文档：更新 `docs/combat-flow.md` 的坐标约定、Mermaid、参数表、已知边界和分类路线。

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
