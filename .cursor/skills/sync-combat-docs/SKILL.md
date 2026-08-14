---
name: sync-combat-docs
description: 全量核对 MXD 项目的代码与文档是否一致，逐项检查 docs/combat-flow.md 的 Mermaid 流程图、参数速查表、代码位置对照、README 配置说明和 CHANGELOG，并补齐缺失内容。用于用户要求"检查/更新文档"、"对一下流程图"、发版前审查，或一次改动横跨多个核心模块时。
disable-model-invocation: true
---

# 同步打怪逻辑文档

日常小改动由 `.cursor/rules/keep-docs-in-sync.mdc` 自动提醒。这个技能做的是**全量核对**：把代码当作事实，逐项验证文档，发现不一致就直接改。

## 执行清单

复制这份清单并逐项打勾：

```
- [ ] 1. 读代码，提取当前真实逻辑
- [ ] 2. 核对 Mermaid 流程图
- [ ] 3. 核对参数速查表
- [ ] 4. 核对代码位置对照表
- [ ] 5. 核对 README 配置说明
- [ ] 6. 补 CHANGELOG
- [ ] 7. 校验 Mermaid 语法
```

## 1. 读代码，提取当前真实逻辑

必读：

- `src/mxd_bot/decision.py` — `decide()`、`_select_target()`、`_match_locked_target()`、`_stabilize_action()`
- `src/mxd_bot/input_controller.py` — `execute()` 及方向键长按、冷却
- `src/mxd_bot/player_locator.py` — 定位优先级和搜索区域
- `config.yaml` — 程序实际读取的正式配置，已入库，**参数取值以它为准**

用 `git diff` 或 `git log` 确认自 `docs/combat-flow.md` 顶部「最后同步」日期以来改了什么，缩小核对范围。

## 2. 核对 Mermaid 流程图

对照 `decision.py` 逐个判定分支检查：

- 每个 `if` / `elif` 分支在图上都有对应节点，条件文字和代码里的比较方向一致。
- 阈值在图上用**配置项名字**表示（如 `attack_range`），不要写死数值——数值放参数表，避免两处都要改。
- 代码删掉的分支，图上也要删。

## 3. 核对参数速查表

- 表里每个参数都能在 `config.yaml` 找到，「当前值」与之一致。
- `config.yaml` 里的 `behavior` / `profiles` / `model` / `player` / `ui` 参数，表里都有对应行。
- 每行的「什么时候调」要写成可操作的现象描述（"左右横跳就调大"），不是重复参数名。
- 顺带检查 `config.example.yaml` 有没有漏掉 `config.yaml` 新增的键。只补键和注释，**不要**同步数值——两份文件的数值本来就允许不同。

## 4. 核对代码位置对照表

模块重命名、函数改名、文件拆分后更新此表。表里的函数名要真实存在，可用搜索验证。

## 5. 核对 README 配置说明

只在这些情况改 README：启动命令变了、配置文件入口变了、新增了用户要手动做的步骤（比如截新模板图）。README 面向"怎么跑起来"，逻辑细节一律留在 `docs/combat-flow.md`，用链接引过去，不要复制粘贴两份。

## 6. 补 CHANGELOG

在 `CHANGELOG.md` 顶部按日期加条目，沿用文件里已有的模板与 `feat` / `fix` / `chore` / `refactor` 前缀。调参必须写**改前 → 改后 + 为什么**。

## 7. 校验 Mermaid 语法

改完流程图必检，这几条最容易踩：

- 节点文字里不能有 `|`，绝对值写 `abs(dx)`。
- 节点文字含 `(` `)` `,` 时，整段用双引号包住：`M{"abs(dx) ≤ attack_limit ?"}`。
- 换行用 `<br/>`，不要在标签里直接敲回车。
- 边标签只用 `-->|文字|` 这一种写法。

## 收尾

改完在回复里列出改了哪些文件、各自改了什么，并把「最后同步」日期更新为今天。如果核对下来完全一致，直接说"已核对，无需更新"，不要为了交付而制造改动。
