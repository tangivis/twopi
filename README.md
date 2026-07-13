# Agent 开发学习资料：pi vs tau

以 `~/workspace/code/pi`（TypeScript 生产级 agent harness）与 `~/workspace/code/tau`（Python 教学级复刻）为教材的对比学习资料。

## 内容

| 文件 | 说明 |
|---|---|
| **[pi-vs-tau-架构对比学习指南.md](pi-vs-tau-架构对比学习指南.md)** | 主文档：架构分析、10 大机制逐维度对比、最佳实践对照、框架选型、应用场景、学习路径与 12 个动手实验、**从零复刻 mini-harness 的 11 个里程碑施工图（第 9 章）**、**模型接入指南——格式要求 / 统一层最佳实践 / 本地模型配置示例（第 10 章）**、**与 LangGraph 等主流框架的深度对比——三种控制流范式 / 四种写法代码对照 / 决策清单（第 11 章）** |
| [webui/index.html](webui/index.html) | 可交互 WebUI 教程（浏览器直接打开即可；也已发布为在线 Artifact） |
| **[mini/](mini/README.md)** | **从零复刻的起步练习工程**：M0/M1 已完成（`uv sync && ./check.sh` 开箱全绿），M2 适配器与 M3 循环是带规格测试的练习（`MINI_MILESTONE=3` 启用，5 条契约已验证可通关），参考答案在 `mini/solutions/` |
| [sources/pi-architecture-notes.md](sources/pi-architecture-notes.md) | pi 代码级分析笔记（英文，含 file:line 出处） |
| [sources/tau-architecture-notes.md](sources/tau-architecture-notes.md) | tau 代码级分析笔记（英文，含 file:line 出处） |
| [sources/best-practices-research.md](sources/best-practices-research.md) | 2025-2026 agent 最佳实践调研（英文，25+ 来源） |

## 快速开始

1. 读主文档第 0-2 章（为什么、是什么、最小循环）
2. 打开 WebUI 玩一遍 agent 循环分步演示
3. 按主文档第 8 章的阅读路线啃代码：**先 tau 后 pi**
4. 做动手实验（从"跑起来"到"写自己的扩展"）

生成于 2026-07-11，基于 pi v0.80.6 (`4c18610`) 与 tau v0.1.5。
