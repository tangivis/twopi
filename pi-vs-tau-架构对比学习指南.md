# pi vs tau：Agent 开发架构对比学习指南

> 以两个真实开源项目为教材，系统学习 coding agent / agent harness 的设计与实现。
>
> - **pi** `~/workspace/code/pi` — TypeScript 生产级 agent harness（Mario Zechner / badlogic，v0.80.6）
> - **tau** `~/workspace/code/tau` — Python 教学级复刻（alejandro-ao，v0.1.5，官方自述 *"A Python implementation of a minimalist Pi-style coding-agent harness"*）
>
> 编写日期：2026-07-11（2026-07-12 增补第 9–11 章：从零复刻 / 模型接入 / 深度对比主流框架；2026-07-13 增补第 12 章：延伸样本 rust-ai-agent 对比）。基于 pi commit `4c18610`、tau v0.1.5（2026-07-09）；2026-07-12 复核：pi 已 pull 至 `8479bd84`（新增 5 个修复性小提交，版本仍 0.80.6，分析结论不受影响），tau 无更新（`b344d3e`）。
> 英文原始分析笔记见 `sources/`（pi/tau 各一份代码级笔记 + 一份网上最佳实践调研，含全部出处链接）。

---

## 目录

- [0. 导读：为什么这两个项目是绝佳教材](#0-导读)
- [1. 认识两个项目](#1-认识两个项目)
- [2. Agent 的本质：一个循环](#2-agent-的本质一个循环)
- [3. 三层架构：共同的蓝图](#3-三层架构共同的蓝图)
- [4. 核心机制逐维度深度对比](#4-核心机制逐维度深度对比)
  - [4.1 Provider 抽象与流式事件](#41-provider-抽象与流式事件)
  - [4.2 Agent 循环细节](#42-agent-循环细节)
  - [4.3 工具系统](#43-工具系统)
  - [4.4 系统提示词](#44-系统提示词)
  - [4.5 会话持久化与树形分支](#45-会话持久化与树形分支)
  - [4.6 上下文管理与压缩](#46-上下文管理与压缩)
  - [4.7 扩展系统](#47-扩展系统)
  - [4.8 安全与权限](#48-安全与权限)
  - [4.9 TUI 实现](#49-tui-实现)
  - [4.10 工程化实践](#410-工程化实践)
- [5. 与业界最佳实践对照](#5-与业界最佳实践对照)
- [6. 框架生态与选型](#6-框架生态与选型)
- [7. 应用场景](#7-应用场景)
- [8. 学习路径与动手实验](#8-学习路径与动手实验)
- [9. 从零复刻：搭建你自己的 mini-harness](#9-从零复刻搭建你自己的-mini-harness)
- [10. 模型接入指南：格式要求、统一层与本地模型](#10-模型接入指南格式要求统一层与本地模型)
- [11. 深度对比：pi/tau 与 LangGraph 等主流框架](#11-深度对比pitau-与-langgraph-等主流框架)
- [12. 延伸样本：rust-ai-agent（Rust）和 pi/tau 一样吗？](#12-延伸样本rust-ai-agentrust和-pitau-一样吗)
- [13. 参考资料](#13-参考资料)

---

## 0. 导读

**为什么选这两个项目对比学习？** 因为 tau 就是 pi 的 Python 教学复刻——两者共享同一套架构蓝图（连文档域名都是数学梗：tau 的文档在 `twotimespi.dev`，因为 τ = 2π）。这给了你一个罕见的学习机会：

1. **同一个设计，两种语言、两种成熟度的实现。** 你可以先读 tau（核心层仅 1,351 行 Python，一个下午读完），建立心智模型；再去 pi 里看同一个概念在生产环境里长成什么样（11 万行 TypeScript，处理了几十个 provider 的兼容性怪癖）。
2. **tau 的 `dev-notes/` 是一份公开的"建造日志"**：约 40 篇 phase 笔记，每篇都写明"这个功能对应 pi 的什么设计、为什么这样做、怎么测试"。相当于有人替你把 pi 拆解了一遍。
3. **pi 是"极简 harness"哲学的代表作**（作者 badlogic 的宣言文章是 2025 年 agent 圈被广泛讨论的文本），拿它对照 Anthropic 官方最佳实践、12-Factor Agents、Claude Code 的做法，能看清 agent 设计的几条真正的分歧轴线。

**快速结论（TL;DR）**：

- Agent 的核心是一个 ~10 行的循环：调用 LLM → 执行它要求的工具 → 把结果塞回对话 → 重复，直到模型不再调工具。两个项目的其余十几万行代码，都是围绕这个循环解决**工程问题**：多 provider 适配、流式事件、会话持久化、上下文压缩、可扩展性、终端 UI。
- 两者共同的关键设计：**三层单向依赖**（provider 层 → agent 大脑 → 产品层）、**事件流作为前端契约**、**默认只给模型 4 个工具**（read/write/edit/bash）、**系统提示词极小**（pi < 1000 tokens）、**JSONL 追加式会话树**、**不做权限弹窗**（要安全就上容器）。
- 主要差异：pi 有完整的**运行时扩展系统**（33 个事件钩子、自扩展能力）、并行工具执行、真实 token/成本核算、多模态消息、1057 个模型的目录；tau 刻意省略这些（扩展系统明确"推迟到 Phase 21"），换来核心层的极致可读性。
- 学习路线：**先 tau 后 pi**，边读边做第 8 章的实验。

---

## 1. 认识两个项目

### 1.1 pi：生产级极简 harness

- **作者与动机**：Mario Zechner（badlogic，libGDX 作者）。他在 2025-11-30 的文章《pi: a minimal coding agent harness》里解释了为什么离开 Claude Code 自己造：*"Claude Code 已经变成一艘飞船，80% 的功能我用不上"*；每次发版提示词和工具都在变、有你无法审计的隐藏上下文注入，而**"精确控制进入模型上下文的每一个 token 能带来更好的输出"**。
- **定位**：不只是一个 CLI 工具，而是一套可组装的 harness：`pi-ai`（统一 LLM API）、`pi-agent-core`（agent 运行时）、`pi-coding-agent`（CLI 产品）、`pi-tui`（终端 UI 库）都是独立发布的 npm 包。Vercel AI SDK 的 `HarnessAgent` 已把 pi 与 Claude Code、Codex 并列为三大可包装 harness；Armin Ronacher 称其拥有"所有 agent 里最短的系统提示词"，OpenClaw 以它为基础构建。
- **验证**：在 Terminal-Bench 2.0（89 个容器化真实终端任务，评测的是 harness+model 组合）上与 Codex/Cursor 同级——这是"薄 harness 不输厚 harness"最硬的实证。

### 1.2 tau：为阅读而生的教学复刻

- **作者与定位**：alejandro-ao（技术教育者）。README 原话：*"Tau is also meant to be read. It is a teaching project for understanding the shape of a coding-agent system without starting from a giant production codebase."* 它同时是能真用的终端 coding agent（PyPI 包 `tau-ai`，`uv tool install tau-ai`）。
- **与 pi 的关系**：`AGENTS.md` 第一句就是 *"Tau is a Python implementation of Pi's minimalist coding-agent harness architecture"*；provider 目录文件头注明 *"generated from Pi API-provider metadata"*；dev-notes 里的路线图写明 *"目标不是逐行移植，而是在使用 Python 原生工具的同时保留同样的边界"*。
- **开发节奏**：2026-06-11 首次提交，一个月约 539 个 commit 迭代到 v0.1.5——本身就是"用 agent 写 agent"的样本。

### 1.3 数据速览

| 维度 | pi | tau |
|---|---|---|
| 语言 / 运行时 | TypeScript，Node ≥ 22.19（支持 Bun 编译单文件二进制） | Python ≥ 3.12（PEP 695 type 别名、match 语句） |
| 版本 | 0.80.6（所有包 lockstep 同步版本） | 0.1.5 |
| 包结构 | 5 个 npm workspace 包 | 1 个包内 3 个顶层模块 |
| 源码规模 | ≈ 111,700 行（ai 36.7k / agent 8.2k / coding-agent 52.7k / tui 12.1k / orchestrator 2.0k） | ≈ 24,600 行（tau_ai 3.4k / tau_agent 1.35k / tau_coding 19.8k） |
| 测试规模 | ≈ 83,000 行，vitest + node:test（@xterm/headless 仿真终端） | ≈ 19,200 行，pytest + anyio，~725 个测试 |
| 核心依赖 | @anthropic-ai/sdk、openai、@google/genai 等官方 SDK（懒加载）；TUI 零重依赖 | **不用任何厂商 SDK**：httpx 手写 SSE；pydantic v2、Textual、Rich、typer |
| 类型/校验 | TypeScript strict + TypeBox（JSON Schema）+ AJV 校验 | mypy --strict + pydantic（extra="forbid"）|
| 构建工具链 | tsgo（TS 7 原生编译器预览）、Biome、npm workspaces、husky | uv、ruff、hatchling |
| 支持的模型 | 9 种 wire API、~36 个 provider、**1,057 个模型**（构建时从 models.dev 等生成目录） | 5 个 provider 适配器覆盖 ~24 个内置 provider（catalog.toml 静态目录 + 用户覆盖） |
| 默认工具 | read / bash / edit / write（grep/find/ls 为可选项） | read / write / edit / bash（grep 等靠 bash） |
| 界面形态 | 交互 TUI（自研）/ print / JSON / **RPC 模式**（30+ 命令驱动外部前端）/ SDK | 交互 TUI（Textual）/ print（text/json/transcript 三种渲染器） |
| 扩展性 | extensions（TS 模块热加载）+ skills + prompt templates + themes + packages | skills + prompt templates（extensions 明确推迟） |
| 许可 | MIT | MIT |

> 一个值得玩味的数字：pi 的**测试代码（8.3 万行）比 tau 的全部代码（2.5 万行）还多 3 倍**。"教学版"与"生产版"的差距主要不在核心设计，而在兼容性长尾和测试覆盖上。

---

## 2. Agent 的本质：一个循环

### 2.1 定义：workflow vs agent

Anthropic《Building Effective Agents》（2024-12，agent 领域被引用最多的设计文档）给出的区分：

- **Workflow**：LLM 和工具按**预定义代码路径**编排（提示链、路由、并行、orchestrator-workers、evaluator-optimizer 五种模式）。
- **Agent**：LLM **动态决定自己的流程和工具使用**，"通常就是在循环里根据环境反馈使用工具的 LLM"——关键是每一步都能从环境获得**真实反馈**（工具执行结果）。

### 2.2 最小循环

整个行业的循环都是同一个形状（sketch.dev 称之为"9 行循环的不合理有效性"，Thorsten Ball 用 300 行 Go 写了个能改代码的 agent 证明"魔法在模型不在脚手架"）：

```python
messages = [user_prompt]
while True:
    response = llm(system_prompt, messages, tools)   # 1. 问模型
    messages.append(response)
    if not response.tool_calls:                      # 2. 不调工具 = 干完了
        break
    for call in response.tool_calls:                 # 3. 执行工具
        result = execute(call)
        messages.append(tool_result(call.id, result))  # 4. 结果塞回对话，回到 1
```

tau 的 `src/tau_agent/loop.py`（276 行）就是这个循环的"注释加强版"；pi 的 `packages/agent/src/agent-loop.ts` 是它的工程加强版（加了 steering 注入、并行执行、截断守卫等，见 4.2）。**先把这 10 行焊在脑子里，后面所有内容都是给它做加法。**

### 2.3 "薄 harness"哲学

为什么这两个项目都刻意做"少"？三类证词：

1. **独立开发者侧**（Ball、sketch.dev、Zechner）：循环是平凡的，能力在模型里；harness 注入的每个 token 都是干扰项。小提示词 + 少工具 = 更干净的信号 + 可复现的行为。pi 的系统提示词 + 工具定义 **< 1,000 tokens**（Claude Code 超过 10k）。
2. **大厂侧**：Claude Code 负责人 Boris Cherny：*"我们希望人们尽可能感受到原始的模型"*、*"每次新模型发布，我们都会删掉一堆代码"*（Claude Code 约 90% 由它自己写成）。方向上与极简派一致。
3. **反对框架、不反对工程**（12-Factor Agents）：生产 agent 大多是"确定性软件 + 关键处的 LLM 步骤"；框架能带你到 70-80% 质量，然后团队会把它拆掉。核心主张：**自己拥有提示词（factor 2）、自己拥有上下文窗口（factor 3）、自己拥有控制流（factor 8）、把 agent 写成无状态 reducer（factor 12）**——这四条几乎就是 pi/tau 的设计说明书。

> 平衡视角：薄 harness ≠ 没有工程。会话持久化、压缩、重试、中断这些"真功能"依然要有人写——pi/tau 的立场是**用自己看得见的平凡代码写**，而不是引入隐藏提示词的框架。

---

## 3. 三层架构：共同的蓝图

两个项目的分层完全同构（tau 有意为之）：

```text
┌──────────────────────────────────────────────────────────────────┐
│  产品层：pi-coding-agent  /  tau_coding                            │
│  CLI 入口、TUI、内置工具(read/write/edit/bash)、系统提示词、          │
│  会话落盘、压缩策略、skills、配置与凭据、slash 命令                    │
├──────────────────────────────────────────────────────────────────┤
│  大脑层：pi-agent-core  /  tau_agent          ← 可移植、不知道终端存在 │
│  agent 循环、事件类型、消息模型、工具接口、steering/follow-up 队列、    │
│  会话数据结构(追加式条目树)                                          │
├──────────────────────────────────────────────────────────────────┤
│  Provider 层：pi-ai  /  tau_ai                                     │
│  把 Anthropic/OpenAI/Google/… 的私有流式协议翻译成统一事件流；          │
│  模型目录、认证(API key/OAuth)、重试、thinking 参数映射               │
└──────────────────────────────────────────────────────────────────┘
     (pi 另有 pi-tui 终端 UI 库 与实验性的 pi-orchestrator)
```

**指导性口号**（tau README 从 pi 原样继承）：

```text
AgentHarness  = 可复用的大脑
CodingSession = coding agent 的环境
TUI           = 众多可能前端中的一种
```

三条设计含义：

1. **依赖单向**：大脑层不 import 终端、不 import 本地配置路径、不认识 slash 命令。tau 的 ADR 0001 甚至规定 Textual 必须隔在一个 adapter（`tui/adapter.py`，约 100 行事件→显示状态的翻译）后面，理论上可整体换掉 UI 框架。
2. **事件是契约**：前端（TUI、print 渲染器、pi 的 RPC 客户端、你未来写的 Web UI）只消费 `AgentEvent` 流，不碰内部状态。这就是为什么 pi 能同时提供 TUI/print/JSON/RPC 四种模式而核心零改动。
3. **一个有趣的细节差异**：中立数据模型（消息、工具类型）在 pi 里定义在最底层 `pi-ai`（`types.ts`），provider 层向上提供类型；tau 则把它们放在中间层 `tau_agent`，让 `tau_ai` 反向 import——tau 的理由是"中立模型属于大脑"。两种放法都成立，共同点是：**全项目只有一份消息类型，provider 差异在边界处消化**。

---

## 4. 核心机制逐维度深度对比

每小节结构：**概念 → pi 做法 → tau 做法 → 差异与评注**。文件路径均相对各自仓库根目录。

### 4.1 Provider 抽象与流式事件

**问题**：每家 LLM 的流式协议、消息格式、thinking 参数、工具调用编码都不同；agent 需要一个中立层，否则上层逻辑会被厂商差异污染。

**pi（`packages/ai`）**：
- 区分 **API 协议** 与 **Provider**：9 种 wire API（`anthropic-messages`、`openai-completions`、`openai-responses`、`google-generative-ai`、`bedrock-converse-stream` 等，`src/types.ts:15-24`）服务 ~36 个 provider——作者的观察是"四五种 wire API 就能覆盖整个市场"。
- 统一事件流 `AssistantMessageEvent`：`start → text_start/delta/end、thinking_*、toolcall_*  → done|error`，每个增量事件都携带**累积中的 partial AssistantMessage**。载体是自研 `EventStream<T,R>`（push 队列 + async 迭代 + `result()` promise）。
- **硬契约：stream 函数永不 throw**（`types.ts:296-308`）——一切失败编码为流内 `error` 事件，`stopReason: "error"|"aborted"` + `errorMessage`。错误进入统一通道，上层循环只处理一种形状。
- 兼容性长尾是 pi-ai 的真正体量所在：`OpenAICompletionsCompat` 约 20 个怪癖开关、**10 种 thinking 文本方言**（deepseek/qwen/zai/together/…）；~24 条正则识别各家"上下文溢出"错误（有的厂商甚至不报错——z.ai 静默接受溢出，靠 `usage.input > contextWindow` 检测）；`transformMessages()` 归一化工具调用 ID（OpenAI Responses 的 ID 可达 450+ 字符，Anthropic 要求 ≤64 字符）并为非视觉模型降级图片——这是**会话可以中途换厂商**的基石。
- 模型目录**构建时生成**（抓取 models.dev / OpenRouter / Vercel Gateway 再人工覆写）：1,057 个模型带价格、上下文窗口、thinking 档位。运行时可 `refreshModels()`。
- 计费与缓存是一等公民：`Usage` 含 cacheRead/cacheWrite 与费用分解；Anthropic 路径自动放置 `cache_control` 断点（系统提示词、工具定义、最后一条用户消息），OpenAI 路径用 `prompt_cache_retention: "24h"` + session 亲和头。
- OAuth 三家：Anthropic（Claude Pro/Max）、OpenAI Codex（ChatGPT 订阅）、GitHub Copilot（device code）。

**tau（`src/tau_ai`）**：
- `ModelProvider` 是一个 **Protocol**（结构化类型，无基类）：`stream_response(model, system, messages, tools, signal) -> AsyncIterator[ProviderEvent]`。
- 7 种 `ProviderEvent`（pydantic 模型，`extra="forbid"`）：`ResponseStart / Retry / TextDelta / ThinkingDelta / ToolCall / ResponseEnd / Error`。注意 `ToolCall` 事件携带**完整**工具调用——tau 不向消费者流式输出工具参数增量（pi 会），少一层复杂度。
- **不用厂商 SDK**：全部 httpx + 手写 SSE 解析。5 个适配器：`OpenAICompatibleProvider`（925 行主力，靠 catalog 驱动的 compat 字典覆盖 OpenAI/OpenRouter/Groq/DeepSeek/xAI/…，并自动在 chat/completions 与 /v1/responses 间路由）、`AnthropicProvider`、`OpenAICodexProvider`（ChatGPT 订阅 OAuth）、`GoogleGenerativeAIProvider`（会透传 Gemini 的 thought_signature）、`MistralConversationsProvider`，外加测试用 `FakeProvider`。
- 重试：指数退避 `min(max_delay, 0.25 * 2^attempt)`，仅当"尚未产出任何事件"时才重试网络错误；退避睡眠切成 50ms 片以便取消。
- **明确的空白**：`ProviderResponseEndEvent` 没有 usage 字段——tau 完全不做 token/成本核算（catalog 里有价格数据但只是元数据），上下文用量全靠 chars/4 估算。这是教学取舍：先把主干讲清楚。

**评注**：这一层是"教学版 vs 生产版"差距最直观的地方（3.4k vs 36.7k 行）。核心抽象两边一致且都很小；pi 多出来的 90% 是**真实世界的兼容性税**——学习时先读 tau 的 `provider.py`+`events.py`+`anthropic.py`（约 700 行），再去 pi 的 `overflow.ts`/`transform-messages.ts` 见识长尾有多长。tau 手写 SSE 也更有教学价值：你能看见 `data:` 前缀是怎么被剥掉的。

### 4.2 Agent 循环细节

**pi（`packages/agent/src/agent-loop.ts`）**——纯函数循环，返回 `EventStream<AgentEvent, AgentMessage[]>`：
1. 双层循环：外层处理 follow-up（agent 本该停下时注入的后续任务），内层 `while (还有工具调用 || 有待注入消息)`。
2. 每轮开始先注入 **steering** 消息（用户在 agent 运行中插话）；轮末再次轮询。
3. 流式请求前依次应用 `transformContext`（裁剪/注入，压缩的挂载点）→ `convertToLlm`（把应用自定义消息类型过滤成 LLM 消息）→ **每轮现取 API key**（OAuth token 会过期）。
4. **截断守卫**：若 `stopReason === "length"`，该消息里的**所有工具调用直接判失败不执行**——参数可能被截断，执行不安全。（新手极易踩的坑：截断的 JSON 参数修修补补也要执行。）
5. 工具执行**默认并行**，但任何一个声明 `executionMode: "sequential"` 的工具会把整批降为串行；准备阶段（校验参数、`beforeToolCall` 钩子——可拦截）始终串行；`tool_execution_end` 事件按完成顺序发出，但**结果消息按 assistant 消息里的原始顺序追加**——transcript 顺序确定性优先。
6. 钩子丰富：`beforeToolCall`（可 block）、`afterToolCall`（可改写结果）、`prepareNextTurn`（可换 context/model/thinking——压缩和中途换模型靠它）、`shouldStopAfterTurn`。
7. 工具结果可带 `terminate: true`（整批全 terminate 则提前结束）、`addedToolNames`（运行中注册新工具，见 4.7）。

**tau（`src/tau_agent/loop.py`）**——单个纯 async generator（~130 行有效代码）：
1. 无状态：调用者拥有 `messages` 列表，循环只向里 append。
2. Provider 事件 1:1 翻译成 agent 事件；文本/思考增量原样转发。
3. 工具**严格串行**执行（`for call in tool_calls`）；异常在工具边界捕获转成 `ok=False` 结果（"工具是隔离边界"）；未知工具名产生失败结果而不是崩溃；`tool_call_id` 不匹配会自动修复。
4. 取消语义：协作式 `CancellationToken`（50ms 轮询）；中途取消时**剩余工具调用会补上合成的 "Tool call cancelled" 结果**——因为 OpenAI 系 API 拒绝"有 tool_call 无 tool_result"的悬空 transcript。这个"transcript 必须始终对 provider 合法"的意识，两边都有（pi 在 Agent 类层面，tau 还有 `harness._append_interrupted_tool_results()` 在恢复会话时补漏）。
5. steering 在每个工具批次后排空；follow-up 只在 agent 即将停止时排空。`max_turns` 默认 `None`（无上限，dev-notes 注明 "Like Pi"）。

**队列语义（两边一致，值得单独记住）**：
- `prompt()` 运行中调用会直接抛错——运行中只能 `steer()`（插话，下轮生效）或 `follow_up()`（排队，agent 停下前注入）。
- 队列模式默认 `one-at-a-time`（每个边界只取一条），可切 `all`。
- 用户消息也通过事件流回显（`message_start/message_end`），前端从**同一条事件流**渲染一切，不需要旁路。

**上面一层**：pi 的 `Agent` 类（状态容器 + 订阅者，监听器 promise **按订阅顺序 await 且参与 run 结算**——会话持久化的顺序保证来自这里）；tau 的 `AgentHarness`（同职责，deque 队列 + 监听器）。pi 另有新的可移植 `harness/` 子系统（带 ExecutionEnv/FileSystem 抽象，为 pi-chat 等非终端宿主准备）。

**评注**：并行 vs 串行工具执行是两边最大的循环级差异。并行快（读 5 个文件一起读），但需要处理结果排序、文件互斥（pi 用 realpath 键控的 promise 链给 edit/write 排队）；串行简单且顺序天然确定。Anthropic 的多 agent 研究文章证实并行工具调用可大幅缩短时延——但那是研究场景；coding 场景里大部分工具批次本来就只有 1-2 个调用。**先学串行，理解正确性约束后再看 pi 怎么做并行。**

### 4.3 工具系统

**共同哲学**：默认只给 4 个工具——`read / write / edit / bash`。搜索？`bash` 里跑 grep。这直接对标 badlogic 的宣言：工具越少，工具描述占用的上下文越少，模型的行为越可预测。（pi 备有可选的 grep/find/ls 三件套：grep 走 ripgrep `--json`、find 走 fd，均自动下载二进制。）

| 工具 | 两边一致的设计 | 差异 |
|---|---|---|
| `read` | 1-indexed offset/limit；**头部截断** + 教学式续读提示 `[Showing lines A-B of TOTAL. Use offset=N to continue.]`；图片文件返回 base64 | pi 用 photon-wasm 把图自动缩到 2000×2000 并进入多模态消息；tau 的图片只能塞在工具结果 data 里（消息模型是纯字符串） |
| `write` | 自动 mkdir -p；与 edit 共享**按真实路径的互斥锁** | pi 用 promise 链，tau 用 asyncio.Lock |
| `edit` | 参数 `{path, edits:[{oldText,newText}]}` 多处编辑；oldText 必须**恰好出现一次**；跨 edit 不许重叠；全部校验通过才写盘（all-or-nothing）；CRLF 归一化后按原文件风格还原；保留 BOM；返回 unified diff | pi 有**模糊匹配管线**（NFKC、行尾空白、智能引号、Unicode 破折号、异形空格），exact `indexOf` 失败后兜底；tau 只做行尾归一化的精确匹配 |
| `bash` | 合并 stderr；可选 timeout（**无默认值**）；进程组整体 SIGKILL（Unix `detached`/`start_new_session` + killpg）；输出**尾部截断**（2000 行 / 50KB），全量落到临时 log 文件并把路径告诉模型；**没有后台模式**（哲学："用 tmux"） | pi 非零退出码直接 throw 成错误结果；tau 把退出码放进结构化 data |

**工具接口定义**：
- pi：`AgentTool = { name, description, parameters: TypeBox Schema, execute(id, args, signal, onUpdate), prepareArguments?, executionMode? }`，AJV 在执行前校验模型产出的参数；流式 JSON 用 partial-json 修复解析。
- tau：`AgentTool` 是 **frozen dataclass**，`input_schema` 是**手写的 JSON Schema 字典**（不从 pydantic 派生！），executor 是普通 async 函数。README 原话：*"Tools are ordinary typed functions"*——没有装饰器、没有注册框架、没有魔法。
- 两边都带 `prompt_snippet` / `prompt_guidelines` 元数据——工具自带它在系统提示词里的那一行，系统提示词由工具集**机械组装**（见 4.4）。
- 两边都有 `prepareArguments` 规整层，容忍模型的常见笔误（把 edits 发成 JSON 字符串、用旧版顶层 oldText/newText——pi 代码注释里点名了 Opus 4.6 和 GLM-5.1 的怪癖）。**工具对模型宽容、对结果严格**，是一条隐性最佳实践。

**对照 Anthropic《Writing effective tools for agents》**：截断提示要**引导下一步**（两边的续读 footer 是教科书案例）、错误消息是提示词（edit 的 "Found 3 occurrences, must be unique" 直接告诉模型怎么修）、整合工具而非包装每个 API 端点（4 个工具 vs 每接口一工具）、Claude Code 把工具响应截到 25k tokens（两边用 2000 行/50KB，同一思想）。

### 4.4 系统提示词

**共同做法**（tau 的 `system_prompt.py` 明确注释 "Pi-style"）：确定性机械拼装，无模板引擎——

```text
身份一句话
Available tools: <各工具的一行 prompt_snippet>
Guidelines: <工具自带的 guidelines 去重 + "Be concise…">
<project_context>
  <project_instructions path="…">AGENTS.md 内容</project_instructions>
</project_context>
<available_skills>
  <skill name=… description=… location=…/>   ← 只列索引！
</available_skills>
当前日期 + cwd
```

**关键技巧：渐进式披露（progressive disclosure）**。技能只在系统提示词里放"名字 + 一句描述 + 文件路径"的 XML 索引，模型需要时自己 `read` 那个 SKILL.md。两边都规定：**只有 read 工具存在时才渲染 skills 区块**。同理，pi 的系统提示词里写着自家文档的绝对路径（"用户问 pi 自身问题时才去读"）——这就是"**agent 能解释自己**"的实现机制，也是它能"自我扩展"的一半基础。

**AGENTS.md 发现**：两边都从多级目录收集项目指令（tau：`~/.tau/`、`~/.agents/`、项目根到 cwd 的每层祖先目录、`.tau/`、`.agents/`；pi 同类逻辑且兼容 `CLAUDE.md`）。

**对照最佳实践**：Anthropic《Effective context engineering》说系统提示词要在"正确的高度"——不是硬编码的脆弱逻辑，也不是空洞口号。pi/tau 的做法是激进版：把"高度"压到最低限度，然后**靠工具让模型即时取用一切**（just-in-time retrieval，与 Claude Code 的 glob/grep 模型同思路）。代价：模型每次都要现学项目；收益：没有陈旧的注入内容，token 花在哪一目了然。

### 4.5 会话持久化与树形分支

**共同数据模型**（tau 从 pi 继承）：会话 = **JSONL 追加式条目树**。

- 每行一个条目：`{id, parentId, timestamp, type, ...}`。条目类型两边高度重合：`message / model_change / thinking_level_change / compaction / branch_summary / label / session_info / custom`（tau 及 pi 新 harness 另有 `leaf` 指针条目）。
- **树而非线性数组**：分支（比如"从这条消息重新来"）只是把 leaf 指针移到某个祖先节点，然后新条目从那里往下长。**永不删除、永不改写已有行**——历史完整可审计，用文本编辑器就能读。
- 被放弃的分支可生成 `branch_summary`（模型写摘要），回到主干时模型仍知道"刚才试过什么"。
- **落盘时机**：每个 `message_end` 即持久化（消息完成即持久，不等 run 结束）；空会话**延迟建文件**（避免一堆空 JSONL）。
- 系统提示词**不入会话文件**，resume 时重建——升级 harness 后旧会话自动获得新提示词。
- 存储位置：pi `~/.pi/agent/sessions/--<cwd编码>--/<时间戳>_<uuidv7>.jsonl`；tau `~/.tau/sessions/<路径slug>-<sha256前6>/<uuid>.jsonl` + 每项目 `index.jsonl` 索引。
- 都支持：`--resume` / resume 选择器、HTML 自包含导出、JSONL 导出。pi additionally：`/fork`（提取当前路径成新文件，可跨项目）、`/clone`、`/share`（secret gist）、会话版本迁移 v1→v2→v3。tau additionally：**自动会话命名**（首条用户消息后用模型起 ≤4 词标题——文档明确标注"这是对 pi 的有意产品分歧"）。

**评注**：这是两个项目最优雅的共同设计。对照 12-Factor（factor 5 统一执行状态与业务状态、factor 6 简单的暂停/恢复 API、factor 12 无状态 reducer）：`SessionState.from_entries(entries, leaf_id)` 字面上就是一个 reducer——重放条目得到状态。LangGraph 把 checkpoint/time-travel 当核心卖点，pi/tau 用"JSONL + 父指针"实现了同类能力的 80%，零框架。另外注意 UUIDv7/时间戳文件名的细节：让文件系统排序即时间排序。

### 4.6 上下文管理与压缩

**为什么重要**：context rot 是实测现象（Chroma 2025-07 报告：18 个模型全部随输入变长非均匀退化）。badlogic 的经验值：**质量在 ~100k tokens 后明显下滑**——所以哪怕窗口有 200k，也应主动管理。

**共同机制**（tau 从 pi 移植，参数都一样）：
- **触发**：`contextTokens > contextWindow - reserveTokens`，`reserveTokens = 16,384`。
- **切点选择**：从最新往旧累计 `keepRecentTokens = 20,000`，切点**永不落在 tool_call 与其 tool_result 之间**（否则 transcript 对 provider 非法）；pi 若切在 turn 中间会生成"两段式"摘要。
- **摘要生成**：模型生成，结构化提示词模板（Goal / Constraints / Progress: Done-InProgress-Blocked / Key Decisions / Next Steps / Critical Context）；已有摘要时用"增量更新"变体合并；`/compact <说明>` 可附加侧重点。
- **溢出恢复**：provider 报上下文溢出 → 移除错误消息 → 以 "overflow" 为由压缩一次 → `continue` 重试**一次**；再溢出则放弃并告知用户。溢出错误**不走**普通重试通道（重试解决不了溢出）。
- **压缩也是追加**：`compaction` 条目记录 `summary + 被替换的条目范围`，重放时在原位置折叠成一条合成 UserMessage——原始消息仍在文件里，历史无损。

**差异**：pi 用**真实 usage**（上一条 assistant 消息的 token 计数）计算当前上下文占用，chars/4 只是兜底；tau 只有 chars/4 估算（+每消息/每工具的开销常数）。pi 的压缩摘要还会累计维护 `<read-files>/<modified-files>` 清单——对照 Claude Code 最佳实践文档里"压缩时永远保留改动文件列表"的建议。

**对照业界**：Anthropic 的三种长任务技术——compaction（两边已实现）、结构化笔记/文件系统记忆（两边的哲学替代品：TODO.md、"文件就是最好的状态"——Manus 也把"文件系统当终极上下文"列为核心经验）、sub-agents（两边都拒绝内置，pi："bash 里再开一个 pi，全程可观察"）。KV-cache 视角（Manus："KV 缓存命中率是生产 agent 最重要的指标"，缓存 token 价格差 10 倍）：追加式消息模型天然缓存友好；pi 显式管理 cache_control 断点；系统提示词里的"当前日期"放在**末尾**而非开头，也是缓存前缀稳定性的细节。

### 4.7 扩展系统

**这是 pi 的灵魂子系统，也是 tau 最大的省略项**（roadmap Phase 21 明确推迟）。

**pi 的四级扩展机制**：
1. **Extensions**（TS 模块，jiti 进程内热加载，无构建步骤）：默认导出 `(pi: ExtensionAPI) => void`。~33 个事件覆盖三类能力：**观察**（loop 全事件镜像）、**拦截**（`input` 改写用户输入、`tool_call` 拦截/改参、`tool_result` 改写结果、`context` 直接改发给 LLM 的消息数组、`before_provider_request` 改请求）、**注册**（`registerTool/Command/Shortcut/Flag/Provider/MessageRenderer`，`ctx.ui.*` 对话框和自定义 TUI 组件）。扩展状态通过 `appendEntry` 持久化到会话、`session_start` 时重放。
2. **Skills**：`SKILL.md`（Agent Skills 规范，与 Claude Code 技能兼容，甚至可把发现目录指向 `~/.claude/skills`）。
3. **Prompt templates**：`.pi/prompts/*.md`，`/name args` 调用，bash 风格参数替换（`$1`、`$@`、`${2:-default}`）。
4. **Packages**：从 npm/git/本地路径安装扩展/技能/模板/主题的组合包。

**自我扩展闭环**（pi 最独特的卖点）：系统提示词指向自带文档 → 模型读文档学会写扩展 → 写完 `/reload` 热加载（或运行中 `registerTool`，新工具通过 `addedToolNames` 机制**立即**可调用，无需重启会话）。Armin Ronacher 对 pi 的评语主题就是"软件构建软件"——agent 扩展自己的 harness。

**tau 现状**：只有 skills（严格 Agent Skills 规范——ADR 0003 详细分析了 pi 的双模式兼容包袱后决定"pre-1.0 直接走严格路线"，裸 `.md` 给迁移警告）+ prompt templates（`{{ arguments }}` 占位符）+ `custom` 会话条目（为未来扩展留的钩子）。`/skill:name` 在 tau 里刻意**不是** slash 命令而是提示词展开。

**评注**：扩展系统是"极简核心"能成立的另一半——pi 拒绝内置 MCP/权限/计划模式的每一条，README 都跟着一句"用扩展自己装一个"。学习价值：pi 的 `ExtensionAPI` 类型定义（`extensions/types.ts`）本身就是一份"agent harness 有哪些可拦截点"的清单，值得通读。

### 4.8 安全与权限

**两边一致的立场：不做权限弹窗。** pi 文档的论证（2025 年 agent 圈最有争议的观点之一）：
- "当 agent 能写代码并执行代码时，权限提示就是安全剧场（security theater）"——你批准的那条命令可以写一个做坏事的脚本，下一条"无害"命令执行它；exfiltration 不是弹窗能挡住的。
- "进程内的半吊子沙箱容易被误解为安全边界。**真正的隔离必须来自操作系统或容器/虚拟化边界。**"
- 所以：要安全 → 容器里跑 + 掐网络。pi 提供三种容器化模式文档（Gondolin 微 VM 扩展——凭据留宿主机、工具进 VM；纯 Docker；OpenShell）。tau 同样零权限机制（连确认弹窗都没有），安全面只有：目录级 catalog 不可被克隆的仓库覆盖（防 base_url 劫持）、凭据文件 0600、bash 不 source 用户 rc 文件。
- pi 另有 **project trust**：加载项目内 `.pi/`（扩展/技能/设置）前要求一次信任决策——明确文档化为"输入加载守卫，不是沙箱"。这是对"恶意仓库带恶意扩展"这一真实攻击面的最小回应。

**对照 Claude Code 的光谱**（另一极）：默认弹窗+allowlist → `--dangerously-skip-permissions`（官方长期建议只在断网容器里用）→ 2025-10 的沙箱方案（bubblewrap/Seatbelt 文件系统隔离 + 代理网络隔离，内部减少 84% 弹窗）→ 2026-03 的 auto mode（用户反正批准 93% 的弹窗，改用小模型分类器审查动作）。**有趣的收敛**：Anthropic 的沙箱文章实质上承认了 pi 的论点——真边界胜过弹窗；差别只在未沙箱环境里要不要保留弹窗这道"减速带"。

**给学习者的框架**：权限系统的价值取决于**信任上下文**。个人工作站上跑自己的代码仓 → pi 的立场成立；企业 SRE agent 碰生产系统 → 审计、分级授权、HITL 是刚需（见第 7 章）。这不是谁对谁错，是同一条轴上的两个工作点。

### 4.9 TUI 实现

- **pi 自研 `pi-tui`**（1.2 万行，依赖只有 marked + get-east-asian-width）：组件渲染成字符串数组，TUI 类做**差分渲染**——对比上次的行，只重画变化区间（append-only 快速路径、相对光标移动、`CSI ?2026` 同步输出防闪烁）；支持 Kitty/iTerm2 内联图片协议、OSC-11 背景色检测自动明暗主题、IME 硬件光标跟踪；用 @xterm/headless 当参照终端做测试。**为什么自研？**通用 TUI 框架（React/Ink 等）在长聊天流上的全量重绘/协调开销是 coding agent 的经典痛点（Claude Code 的闪烁问题人尽皆知），差分渲染是针对"只往下长的转录流"这一特定负载的优化。
- **tau 用 Textual**（ADR 0001）：成熟 Python TUI 框架 + Rich 渲染 markdown/代码高亮，隔在 `TuiEventAdapter` 后面。并发模型很有教学价值：prompt 在 Textual worker 里跑（exclusive），**递增的 `run_id` 丢弃取消后迟到的事件**（异步 UI 的经典竞态解法）；Enter=steer、Alt+Enter=follow-up、Esc=取消。
- 交互特性两边高度对齐：模型选择器（含 scoped models 快速循环）、树形分支选择器、`!cmd`（进上下文）/`!!cmd`（不进上下文）终端命令、主题、可重绑定按键。

**评注**：这层的取舍最典型——pi 为体验自研（并把 TUI 做成独立可复用的包），tau 为教学借力生态。做自己的项目时默认学 tau（别重造 TUI），除非你的产品差异化恰好在终端体验上。

### 4.10 工程化实践

| 维度 | pi | tau |
|---|---|---|
| 类型纪律 | TS strict；`erasableSyntaxOnly`（源码只用可擦除语法，Node 直跑 .ts，无构建也能运行——扩展热加载同理） | mypy **strict**；pydantic `extra="forbid"` 一切从严 |
| 测试哲学 | **faux provider**（假 LLM）跑全套 e2e，测试套件不打真 API；`test.sh` 先备份 auth.json 并清空所有 key 让 LLM 依赖测试自跳过；TUI 用无头终端仿真 | 同思想：`FakeProvider` 脚本化事件流，循环/harness 测试读起来像规格说明书；224 个 Textual pilot 测试驱动真 TUI |
| 供应链 | 外部依赖**精确锁版**、`min-release-age=2`（防上架当天的投毒包）、shrinkwrap 带生命周期脚本白名单、处处 `--ignore-scripts`、npm OIDC 可信发布 | 常规 uv.lock（教学项目未做强化） |
| 发布 | lockstep 版本；"没有 major 版本"（patch=修复+新增，minor=破坏性） | 常规 semver 早期版本 |
| 自举 | 仓库自带 `.pi/`（真实扩展、模板、技能），repo 由 pi 自己开发维护；作者把自己的开发会话发布成 HuggingFace 数据集 | AGENTS.md 详细规定"agent 如何给 tau 写代码"（dev-notes 每阶段必须留笔记） |

pi 的供应链清单值得单独收藏——2025-2026 npm 投毒潮后，这是**agent 时代 CLI 工具**（自带执行权限的软件！）应有的防御姿态范本。

---

## 5. 与业界最佳实践对照

### 5.1 Anthropic《Building Effective Agents》检查单

| 原则 | pi / tau 的落地 |
|---|---|
| 从简单开始，能不用 agent 就不用 | 整个项目就是这条原则的极端化：先给你一个裸循环 |
| Agent = 环境反馈循环中的 LLM | `agent-loop.ts` / `loop.py` 的字面实现 |
| 透明的规划过程 | 无隐藏注入；事件流全量可观察；pi 的 `--mode json` 直接吐全部事件 |
| 投资 ACI（agent-computer interface） | 4 个精心打磨的工具：教学式截断提示、错误即提示词、prepareArguments 容错、poka-yoke（edit 唯一匹配约束让"改错地方"结构性困难） |

### 5.2 工具设计（《Writing effective tools for agents》）

- ✅ 整合的少量工具（4 个 vs 每个 API 一个）· 一行 when-to-use 描述（prompt_snippet）· 截断信息引导下一步 · 错误可行动 · 分页/offset
- ⚠️ 两边都**没有**系统化的工具评测（eval）流程——Anthropic 文章的核心建议第一条。你自己做 agent 时补上：几十个真实任务、跑循环、看 transcript 找困惑点。

### 5.3 上下文工程（《Effective context engineering》+ Manus 经验）

- ✅ 找到"最小的高信号 token 集"：<1000 token 的 harness 开销 · just-in-time 检索（glob/grep/read，不预灌 RAG）· compaction 保决策弃冗余 · 文件系统当记忆 · 追加式消息天然 KV-cache 友好 · 错误保留在上下文里（模型看见失败才会改）
- ⚠️ pi 有真实 usage 驱动的精确核算；tau 的 chars/4 在中文/代码密集场景会偏差较大（一个可以动手改进的点，见第 8 章实验）。

### 5.4 12-Factor Agents 对照

| Factor | pi/tau |
|---|---|
| 2 拥有自己的提示词 | ✅ 机械拼装，全部可见 |
| 3 拥有上下文窗口 | ✅ transformContext / 压缩全部自持 |
| 4 工具只是结构化输出 | ✅ TypeBox / 手写 JSON Schema |
| 6 简单的启动/暂停/恢复 API | ✅ prompt/steer/follow_up/abort + JSONL resume |
| 8 拥有控制流 | ✅ 循环是自己的一个函数 |
| 9 把错误压入上下文 | ✅ 错误变 tool_result / 溢出走压缩重试 |
| 10 小而聚焦的 agent | ✅ 单 agent、窄工具面 |
| 12 无状态 reducer | ✅ `SessionState.from_entries()` 字面实现 |
| 7 用工具调用联系人类（HITL） | ❌ 两边都无内置——pi 的答案是"用扩展自己装" |
| 11 随处可触发 | pi 的 RPC/SDK/print 模式给了原料；tau 只有 CLI |

### 5.5 有意的"不做"清单及其争议

| 不做什么 | pi/tau 的理由 | 反方观点 / 收敛点 |
|---|---|---|
| MCP | "上下文开销太大"（MCP server 动辄吃掉 7-9% 窗口）；CLI 工具 + README 更省 | MCP 已捐入 Linux 基金会、全行业采用，生态价值真实；Anthropic 自己也在推"代码执行式 MCP"把 schema 挪出提示词——**两边正在收敛**：工具目录不该全量常驻上下文 |
| 内置 sub-agents | "bash 里再开一个实例，全程可观察" | Anthropic 多 agent 研究系统证明研究类任务提升 90%（但 token 15 倍，且明说 **coding 不适合**多 agent——上下文难共享）。pi 的立场对 coding 场景基本成立 |
| 权限弹窗 | 安全剧场论（见 4.8） | Claude Code 的沙箱与 auto mode 实质认同"真边界论"，但为未沙箱环境保留弹窗；企业场景弹窗+审计仍是刚需 |
| 计划模式 / TODO 工具 | "它们让模型困惑。用 TODO.md" | Manus 的"复述 todo.md 对抗 lost-in-the-middle"支持文件派；Claude Code 的 TaskCreate 派认为结构化任务利于 UI 呈现。属于品味分歧 |
| 后台 bash | "用 tmux，完全可观察" | 品味分歧；长时任务多的场景内置后台管理确实更顺手 |

---

## 6. 框架生态与选型

按抽象层级从"裸金属"到"全托管"排列（详表与出处见 `sources/best-practices-research.md` §3；**范式级的深度对比与四种写法的代码对照见第 11 章**）：

| 层级 | 代表 | 一句话定位 | 什么时候选 |
|---|---|---|---|
| 裸循环 | 直接调 Messages API（Thorsten Ball 300 行教程） | 理解本质 | 学习；极简嵌入 |
| **薄 harness** | **pi、tau**、sketch.dev | 循环 + 工具 + 会话 + 上下文管理，全部自持可见 | 想完全控制上下文；terminal coding；作为库嵌入自己产品 |
| 最小框架 | smolagents（HF，核心 ~1000 行，特色 CodeAgent：动作写成可执行 Python 而非 JSON，约省 30% 步数）、OpenAI Agents SDK（Agents/Handoffs/Guardrails/Sessions + tracing） | 少量原语 + 一个鲜明主张 | 研究原型；OpenAI 系多 agent handoff |
| 类型化中间层 | PydanticAI（"GenAI 界的 FastAPI"：类型化输出、DI、可接 Temporal 做持久执行）、Vercel AI SDK（TS 流式 UI 全家桶，`HarnessAgent` 可直接驱动 pi/Claude Code/Codex） | 生产 Python/TS 应用的水电煤 | 需要校验输出/流式 web UI |
| 图编排 | LangGraph（状态机/checkpoint/time-travel/HITL 中断） | 持久化工作流引擎 | 长时有状态业务流；愿付学习成本（12-Factor 批判的主要对象也是它） |
| 全家桶 harness | **Claude Agent SDK**（Claude Code 整机作为库：内置工具/循环/压缩/子代理/hooks/权限/会话） | batteries-included | 要"开箱即用的 Claude Code 能力"且接受 Claude-only 与不透明 |
| 企业多 agent | Google ADK（多语言、A2A 协议、eval 工具链）、CrewAI（角色制、35 行起步）、AutoGen | 平台化 | 企业云绑定 / 快速 demo |

**pi/tau 在光谱上的位置**：它们证明了"薄 harness"档位的存在价值——比裸循环多了你**一定**会需要的四件套（多 provider、会话、压缩、中断/插话），又不引入任何隐藏提示词。2025-2026 的行业共识迁移方向恰好是"从编排框架转向上下文工程 + 自持的薄 harness"（12-Factor、Manus、Anthropic 上下文文章、pi 各自独立得出同一结论）。

**学完 pi/tau 后怎么用这张表**：做玩具 → 裸循环；做自己的 coding/terminal agent → fork pi 思路或用 pi 扩展；做 Python 生产服务 → PydanticAI 或 Claude Agent SDK；做长时业务工作流 → 再评估 LangGraph/Temporal。

---

## 7. 应用场景

（行业现状：LangChain 调查 57.3% 的团队已有 agent 进生产；客服 26.5% 居首，研究与数据分析 24.4% 次之。）

| 场景 | 真实案例 | 对 harness 的压力点 | pi/tau 架构的适配度 |
|---|---|---|---|
| **Coding agent** | Claude Code、Codex、Cursor、pi 本身 | 上下文管理、edit 工具可靠性、会话分支、中断/插话 | ✅ 原生主场 |
| **客服** | Intercom Fin（周百万对话，~71% 解决率，$0.99/解决）、Sierra | 护栏/政策遵从、HITL 升级、跨渠道会话状态、单次解决经济学 | ⚠️ 更像"路由+护栏"workflow 而非开放循环；事件流和会话模型可复用，护栏要自己加 |
| **深度研究** | OpenAI Deep Research、Anthropic Research（orchestrator-workers，内部评测 +90%，token 15 倍） | 并行子 agent、隔离上下文、引用后处理、token 预算 | ⚠️ pi 的"再开一个进程"哲学在这里成本高；这是多 agent 编排真正值回票价的场景 |
| **Computer use** | Anthropic computer use API、OpenAI Operator | 截图进/动作出循环、延迟、沙箱 VM、凭据处人类接管 | 循环结构相同，工具面完全不同 |
| **数据分析** | 代码执行沙箱 + 产物回传（xlsx/docx）；Manus | 沙箱代码执行、文件 I/O、"文件系统即记忆" | ✅ bash+文件哲学直接迁移 |
| **DevOps / SRE** | Azure SRE Agent、incident.io / PagerDuty AI SRE | **读多写少的权限分级、审计日志、人类升级**——权限系统真正挣钱的领域 | ⚠️ pi 的"无权限"立场在此不适用，需要 beforeToolCall 级别的拦截（pi 扩展恰好给了挂点） |

**规律**：循环与事件流是**通用**资产；工具面、权限姿态、编排深度是**场景**资产。学 pi/tau 得到前者，换场景时重做后者。

---

## 8. 学习路径与动手实验

### 8.1 阅读路线（建议顺序）

**第一周：tau 建立心智模型**（每步都是一次可完成的阅读）

1. `tau/README.md` + 官网三篇：`what-is-tau`、`internals/architecture`、`internals/design-principles`（7 条设计原则背下来）
2. 数据模型：`src/tau_agent/messages.py`（47 行）→ `tools.py` → `events.py`
3. **核心**：`src/tau_agent/loop.py`（276 行，对照官网 `internals/agent-loop` 页逐步读）
4. `src/tau_agent/harness.py`（298 行：队列、取消、transcript 修复）
5. 会话：`src/tau_agent/session/`（entries → jsonl → tree → memory，注意 `SessionState.from_entries` 这个 reducer）+ 根目录 `session-temp.jsonl` 真实样本
6. Provider：`src/tau_ai/provider.py` + `events.py` + `anthropic.py`（看 SSE 怎么手工解析）
7. 产品层择要：`tau_coding/tools.py`（4 个工具全文）→ `system_prompt.py` → `session.py` 的 `prompt()` 与压缩路径 → `tui/adapter.py`
8. 泛读 `dev-notes/`：roadmap、design/01-architecture、design/04-sessions、adr/0003（看一个真实的架构决策怎么写）

**第二周：pi 看生产形态**（带着 tau 的地图去找差异）

1. `packages/coding-agent/README.md` 的 Philosophy 段 + `docs/security.md`（无权限立场的完整论证）
2. `packages/agent/src/agent-loop.ts`（对照 tau 的 loop.py：找出 steering 注入点、截断守卫、并行执行、prepareNextTurn）
3. `packages/agent/src/agent.ts`（订阅者顺序结算）与 `types.ts`（AgentTool 接口）
4. `packages/coding-agent/src/core/tools/`（edit-diff.ts 的模糊匹配管线值得精读）
5. `core/system-prompt.ts`、`core/compaction/compaction.ts`、`docs/session-format.md`
6. `packages/ai/src/types.ts`（9 种 API、compat 开关）、`utils/overflow.ts`（感受兼容性长尾）
7. **扩展系统**：`extensions/types.ts` 的 ExtensionAPI + `examples/extensions/` 逐个跑
8. 外围文章：badlogic 的 pi 宣言、Armin Ronacher 的评测（链接见第 13 章）

### 8.2 动手实验（由浅入深 12 个）

1. **跑起来**：两个都装上（`uv tool install tau-ai`；pi 按 README 从源码跑 `./pi-test.sh`），用各自问对方仓库"explain this repo"，对比行为与 token 感受。
2. **读 JSONL**：跑一个小会话，打开 `~/.tau/sessions/` 下的文件逐行读；画出条目的父子树；手工改 leaf 指针再 resume，验证分支切换。
3. **裸循环**：不看两边源码，用 `tau_ai` 的 `AnthropicProvider`（或裸 httpx）+ 50 行代码复刻 2.2 节的最小循环，给它 read/bash 两个工具，让它修一个真实的类型错误。（对标 Thorsten Ball 练习）
4. **事件流观察**：用 `FakeProvider` 写一个脚本，打印一次两轮工具调用的完整 `AgentEvent` 序列；画事件时序图（agent_start → turn_start → message_* → tool_execution_* → turn_end → …）。
5. **加工具（tau）**：给 tau 加一个 `grep` 工具（参照 pi 的 ripgrep --json 实现），带 100 条上限截断 + 引导性 footer；补一个 FakeProvider 测试。
6. **触发压缩**：把 `auto_compact_threshold` 调到很小，观察压缩条目、摘要结构（Goal/Progress/Next Steps…），再 resume 验证重放折叠。
7. **写 SKILL.md**：写一个"提交信息规范"技能放 `.agents/skills/`，验证 pi 和 tau **同一个文件都能用**（Agent Skills 规范通用性）。
8. **pi 扩展入门**：让 pi 自己给自己写一个扩展（它的卖点）：比如"每次 edit 后自动跑 ruff/tsc 并把错误作为 followUp 注入"。
9. **权限实验**：用 pi 的 `tool_call` 事件写一个"bash 命令确认弹窗"扩展（ctx.ui.confirm）——亲手实现被 pi 拒绝内置的功能，体会两边论点。
10. **精确核算（tau）**：给 `ProviderResponseEndEvent` 加 usage 字段（OpenAI 适配器已经请求了 `include_usage`！），把 chars/4 估算替换成真实数值——这是给 tau 提 PR 的现成选题。
11. **并行工具（tau）**：把 `_execute_tool_calls` 改成 `asyncio.gather` 并行版，处理好结果顺序与文件锁——然后对照 pi 的实现自评。
12. **自定义前端**：照 tau 官网 `internals/custom-frontend` 指南，用 `CodingSession` + 事件流写一个最小 Web 前端（FastAPI + SSE）；或者用 pi 的 `--mode rpc` 从 Node 驱动一个。

### 8.3 检验清单（能答上来才算学会）

- 为什么 `stopReason == "length"` 时所有工具调用都不能执行？
- 为什么取消后要给悬空的 tool_call 补合成结果？不补会发生什么？
- steering 和 follow-up 的注入时机差在哪？为什么要两条队列？
- 压缩的切点为什么不能落在 tool_call 和 tool_result 之间？
- 会话为什么是"树 + leaf 指针"而不是数组？分支时为什么不删除旧条目？
- 系统提示词为什么不持久化到会话文件？
- 渐进式披露（skills 只放索引）省的是什么？代价是什么？
- pi 的"无权限"论证成立的前提条件是什么？什么场景下不成立？

---

## 9. 从零复刻：搭建你自己的 mini-harness

> 读完看懂 ≠ 会造。这一章是完整的施工图：从空目录出发，按 **11 个里程碑（M0–M10）** 复刻 pi/tau 架构的最小可用版（下文暂称 `mini`），每个里程碑都有明确产出、验收测试和 pi/tau 对照文件。路线浓缩自 tau 真实的 24 个开发阶段（`dev-notes/architecture/` 的建造日志）——这是一条被验证过的施工顺序，不是纸上推演。
>
> 预期投入：每晚 2 小时 + 周末，约 **2–3 周**到 M8（可用的 print 模式 agent）；M9/M10 再加一周。全程目标代码量 ≤ 3,000 行（tau 核心层 + 最小产品层的量级）。

### 9.0 开工前：定边界、立规矩、选技术

**复刻什么？** 复刻的是**边界**，不是代码行（tau roadmap 原话："目标不是逐行移植，而是保留同样的边界"）。你要造的是：

```text
mini_ai      Provider 层：1 个真适配器 + 1 个 FakeProvider
mini_agent   大脑层：循环 + 事件 + 消息 + 工具接口 + 队列 + 会话数据结构
mini_app     产品层：4 个工具 + 系统提示词 + JSONL 落盘 + CLI（print 模式）
```

**第一天就立的五条铁律**（每一条都是两个项目用守卫代码强制执行的不变量，违反任何一条后面都会返工）：

1. **transcript 任何时刻对 provider 合法**：每个 tool_call 必有对应 tool_result，取消/崩溃/恢复时用合成结果补齐。
2. **事件流是前端唯一契约**：`mini_agent` 里不许出现 `print`、不许 import 终端/UI/配置路径。
3. **会话只追加，永不改写**：分支 = 移动 leaf 指针；压缩 = 追加摘要条目。
4. **provider stream 永不 throw**：一切失败编码为流内 error 事件，循环只处理一种错误形状。
5. **错误进上下文**：工具失败转成 `ok=False` 的结果消息发回给模型，不吞、不藏、不炸循环。

**技术选型**（照抄 tau 即可，不要在这里创新）：

| 决策 | 推荐 | 理由 |
|---|---|---|
| 语言 | Python ≥ 3.12（或 TS + Node ≥ 22 照 pi） | PEP 695 type 别名 + match 语句正好够用 |
| HTTP/流 | `httpx` + 手写 SSE 解析 | 不用厂商 SDK：你会真正理解协议，且零依赖锁定 |
| 数据模型 | `pydantic` v2，全部 `extra="forbid"` | 脏字段第一时间炸出来 |
| 工具 schema | **手写 JSON Schema 字典** | 不要从 pydantic 自动派生——工具 schema 是给模型读的提示词，值得手工打磨 |
| 类型/质量门 | `mypy --strict` + `ruff` + `pytest`（anyio 插件），第一天就开 | tau 的经验：strict 从 day 1 开成本最低 |
| 项目管理 | `uv init --package mini`，src 布局 | — |

**节奏纪律**：每个里程碑的验收测试全绿才进下一个；每个里程碑结束打一个 git tag（`m0`、`m1`……），返工时可以精确回退。测试从 M2 起全部基于 FakeProvider——**永远不要让测试套件打真 API**（pi/tau 共同实践）。

> 🚀 **起步工程已就绪**：`agent-study/mini/` 是按本章施工图搭好的练习工程——M0/M1 已完成（`./check.sh` 开箱全绿，git 已 tag 到 m1），FakeProvider 与 6 种 ProviderEvent 已提供，M2（OpenAI 兼容适配器）与 M3（循环）是带 TODO 骨架的练习；M3 附 5 条规格测试（`MINI_MILESTONE=3` 启用），已用参考实现验证可通关（参考答案在 `mini/solutions/`，有剧透警告）。从 `mini/README.md` 开始。

### 9.1 M0 · 骨架与依赖方向守卫（半天）

**构建**：
- `uv init --package mini`；`src/mini_ai/`、`src/mini_agent/`、`src/mini_app/` 三包 + 空 `tests/`。
- 配好 mypy strict / ruff / pytest；写一个 CI 也能跑的 `check.sh`（lint + type + test 三连）。
- 写第一个测试：**依赖方向守卫**——断言 `mini_agent` 的所有模块 import 里不出现 `mini_app`，`mini_ai` 里不出现 `mini_app`（AST 扫描 20 行就够）。这个测试会在整个项目生命周期里持续抓违规。

**验收**：`check.sh` 全绿；故意在 `mini_agent` 里 import `mini_app`，守卫测试变红。

**对照**：tau `pyproject.toml`；pi `tsconfig.base.json` + `AGENTS.md` 的工程规则。

### 9.2 M1 · 核心类型：消息、工具、事件（半天）

**构建**（全部放 `mini_agent`，学 tau 让中立模型住在大脑层）：

```python
# mini_agent/messages.py —— 先用纯字符串 content（tau 式），多模态以后再说
class UserMessage(BaseModel):
    role: Literal["user"] = "user"
    content: str

class ToolCall(BaseModel):
    id: str; name: str; arguments: dict[str, Any]

class AssistantMessage(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: str
    tool_calls: list[ToolCall] = []
    finish_reason: Literal["stop", "tool_use", "length", "error", "aborted"] = "stop"

class ToolResultMessage(BaseModel):
    role: Literal["tool"] = "tool"
    tool_call_id: str; name: str
    content: str            # 给模型看的
    ok: bool = True
    data: dict[str, Any] = {}   # 给 UI 看的（diff、图片 base64……）

type AgentMessage = UserMessage | AssistantMessage | ToolResultMessage
```

```python
# mini_agent/tools.py —— 工具是普通函数 + 手写 schema，没有魔法
@dataclass(frozen=True, slots=True)
class AgentTool:
    name: str
    description: str
    input_schema: Mapping[str, Any]      # 手写 JSON Schema
    executor: ToolExecutor               # async (ToolCall) -> AgentToolResult
    prompt_snippet: str = ""             # 它在系统提示词里的那一行
```

- 事件（`events.py`）：先定义 10 个够用——`agent_start/end`、`turn_start/end`、`message_start/delta/end`、`tool_execution_start/end`、`error{recoverable}`，pydantic + `type` Literal 判别，`type AgentEvent = …` 联合。

**决策点**：content 用 `str` 还是内容块列表？——先 `str`（tau 的取舍），把图片等塞 `ToolResultMessage.data`。想升级成 pi 式多模态时只需改 provider 边界。

**验收**：每个类型 JSON round-trip 测试；给消息塞未知字段必须报错（`extra="forbid"` 生效）。

**对照**：tau `tau_agent/messages.py`（47 行）/`tools.py`/`events.py`；pi `packages/ai/src/types.ts`。

### 9.3 M2 · Provider 层：FakeProvider 先行 + 一个真适配器（1–2 天）

**先写 FakeProvider，再写真的**——它是从现在到最后所有测试的地基：

```python
# mini_ai/provider.py
class ModelProvider(Protocol):
    def stream_response(self, *, model: str, system: str,
                        messages: list[AgentMessage], tools: list[AgentTool],
                        signal: CancellationToken | None = None,
                        ) -> AsyncIterator[ProviderEvent]: ...

# mini_ai/fake.py —— 回放脚本化事件序列，并记录收到的请求
class FakeProvider:
    def __init__(self, scripts: list[list[ProviderEvent]]): ...
```

- Provider 事件先定 6 个：`response_start / text_delta / tool_call（整体交付，不流增量——tau 的简化）/ response_end{message, finish_reason} / retry / error`。
- 真适配器选 **Anthropic Messages API**（SSE 结构最清晰）或 OpenAI `/chat/completions`。手写 SSE 的全部要点：
  - 按行读流，只认 `data: ` 前缀；`[DONE]`（OpenAI）或 `message_stop`（Anthropic）收尾；
  - 工具调用参数是分片 JSON（`input_json_delta` / `arguments` 增量），攒够再 `json.loads`；
  - **永不 throw**：网络错误/HTTP 4xx/5xx 全部转成 `error` 事件 yield 出去；
  - 重试规则照抄两边共识：只在**尚未产出任何事件**时重试网络错误；HTTP 408/429/5xx 指数退避 `min(max, 0.25·2^n)`；退避睡眠切成 50ms 片以便取消。

**验收**：FakeProvider 脚本测试（文本流 + 一次工具调用 + 一次 error）；一个不进测试套件的 `smoke.py` 用真 key 手动跑通；断掉网络时得到 error 事件而不是异常栈。

**对照**：tau `tau_ai/provider.py`/`events.py`/`fake.py`/`anthropic.py`；pi `packages/ai/src/api/anthropic-messages.ts`（感受生产版长什么样）。

### 9.4 M3 · 循环：全项目最重要的 130 行（1 天）

写成**纯 async generator**（tau 式）：无状态、调用者拥有 `messages`、循环只 append。简化骨架（省略部分事件）：

```python
async def run_agent_loop(*, provider, model, system, messages, tools,
                         drain_steering, drain_follow_up,
                         signal=None, max_turns=None):
    yield AgentStartEvent()
    turn = 0
    while max_turns is None or turn < max_turns:     # 默认无上限，像 pi/tau
        yield TurnStartEvent(turn=turn)
        assistant = None
        async for ev in provider.stream_response(model=model, system=system,
                                                 messages=messages, tools=tools, signal=signal):
            # provider 事件 1:1 翻译成 agent 事件；response_end 时 append 进 transcript
            assistant = translate_and_maybe_append(ev, messages)  # 你来实现
            yield to_agent_event(ev)
        if assistant is None:                         # 流断了却没有消息
            yield ErrorEvent("stream ended without assistant message"); break
        if assistant.finish_reason == "length":       # ← 截断守卫！
            fail_all_tool_calls(assistant, messages)  # 参数可能不完整，全部拒绝执行
        elif assistant.tool_calls:
            async for ev in execute_tool_calls(assistant.tool_calls, tools, messages, signal):
                yield ev                              # 串行执行；异常→ok=False；未知工具→失败结果
        else:
            yield TurnEndEvent(turn=turn)
            if not drain_steering() and not drain_follow_up():
                break                                 # 真的没活了
            continue
        yield TurnEndEvent(turn=turn)
        drain_steering()                              # steering 只在工具批次边界注入
        turn += 1
    yield AgentEndEvent()
```

**必须实现的四个守卫**（新手事故高发区，两个项目都有对应代码）：
1. **截断守卫**：`finish_reason == "length"` → 所有工具调用不执行、直接生成失败结果；
2. **异常边界**：工具 executor 抛异常 → 捕获转 `ok=False` 结果，循环继续；
3. **未知工具**：模型幻觉出不存在的工具名 → 失败结果而不是 KeyError；
4. **取消补齐**：中途取消 → 剩余工具调用补合成 "cancelled" 结果，保 transcript 合法。

**验收**（用 FakeProvider 写，这些测试就是你的循环规格书）：
- 两轮工具调用的脚本，断言**精确事件序列**：`agent_start → turn_start → message_* → tool_execution_start/end → turn_end → turn_start → … → agent_end`；
- 断言结束时 transcript 里每个 tool_call 都有 tool_result；
- 分别触发四个守卫的测试各一个。

**对照**：tau `tau_agent/loop.py`（276 行，你的答案纸）；pi `packages/agent/src/agent-loop.ts`（看多了什么：steering 双轮询、并行执行、prepareNextTurn 钩子）。

### 9.5 M4 · 四个工具：坑最密集的一站（2–3 天）

放 `mini_app`（工具属于"环境"不属于"大脑"）。每个工具的规格直接抄 4.3 节的共同设计，这里列**必须做对的点**：

- **read**：1-indexed `offset/limit`；超 2000 行 / 50KB **头部截断**，footer 必须教续读：`[Showing lines A–B of TOTAL. Use offset=N to continue.]`。
- **write**：自动 `mkdir -p`；与 edit 共享**按 resolve 后路径**的 `asyncio.Lock`。
- **edit**：参数 `{path, edits:[{oldText,newText}]}`；每个 `oldText` 在**原文件**中必须恰好出现一次（0 次和 2+ 次都是错误，错误消息要写明出现次数）；跨 edit 不许重叠；**全部校验通过才写盘**；CRLF→LF 归一化匹配、按原文件风格还原、保 BOM；返回 unified diff 放进 `data`。
- **bash**：`create_subprocess_shell` + `start_new_session=True`，超时/取消时 `os.killpg(SIGKILL)` **杀整个进程组**（只杀 shell 会留孤儿进程）；stderr 并入 stdout；**尾部截断** 2000 行/50KB，全量输出落临时文件并把路径写进结果；无默认超时。

**验收**（每条都是 pi/tau 真实处理过的 case）：
- edit：非唯一匹配拒绝、重叠拒绝、CRLF 文件改完还是 CRLF、"改了等于没改"报错；
- read：截断 footer 内容精确断言；
- bash：`sleep 100 & sleep 100` 超时后 `ps` 里不残留孤儿进程；非零退出码产生 `ok=False`；
- 并发两个 edit 同一文件不互相覆盖（文件锁生效）。

**对照**：tau `tau_coding/tools.py`（1,057 行全文精读）；pi `core/tools/edit-diff.ts`（看模糊匹配管线——你的 v2 素材）。

### 9.6 M5 · Harness：状态、双队列、取消（1 天）

```python
class AgentHarness:
    # 状态：_messages、_running、_cancel_token、两个 deque（steering / follow_up）
    def prompt(self, content) -> AsyncIterator[AgentEvent]:   # 运行中调用 → 抛 RuntimeError
    def steer(self, content) -> None                          # 入队，工具批次边界注入
    def follow_up(self, content) -> None                      # 入队，agent 将停时注入
    def cancel(self) -> None                                  # 置 token；循环协作式退出
    def _repair_dangling_tool_calls(self) -> None             # prompt/resume 前补挂起结果
```

- 队列默认 `one-at-a-time`（每个边界只取一条）；
- 用户消息经事件流回显（`message_start(role=user)/message_end`），前端只有一个数据源；
- `subscribe(listener)` 支持 sync/async 监听器——M7 的落盘就挂在这里。

**验收**：运行中 `prompt()` 抛错；`steer()` 的消息恰好出现在下一个工具批次之后（用 FakeProvider 的多轮脚本断言位置）；取消后 transcript 合法（守卫 4 生效）；`_repair_dangling_tool_calls` 的单元测试。

**对照**：tau `tau_agent/harness.py`（298 行）；pi `agent.ts`（看订阅者按序 await 并参与 run 结算——落盘顺序保证）。

### 9.7 M6 · 系统提示词：机械拼装（半天）

```text
一句身份 → Available tools:（各工具的 prompt_snippet）→ Guidelines:（去重）
→ <project_context><project_instructions path="…">AGENTS.md 内容</…></…>
→ 当前日期 + cwd（放末尾！开头放动态内容会毁掉 KV 缓存前缀）
```

- AGENTS.md 发现：项目根（找 `.git`/`pyproject.toml` 标记）→ 逐级到 cwd；
- 不做模板引擎，就是字符串拼接——可测试、可 diff。

**验收**：golden-file 测试（固定输入 → 逐字节比对输出）；**预算测试**：`len(prompt)/4 < 1200`——从此任何人往提示词里塞东西都会被 CI 拦下来问一句"值得吗"。

**对照**：tau `system_prompt.py`；pi `core/system-prompt.ts`。

### 9.8 M7 · 会话持久化：追加式条目树（1–2 天）

```python
# mini_agent/session/entries.py —— 先做 5 种条目就够
# session_info / message / leaf{entry_id} / model_change / compaction（M9 用）
class BaseEntry(BaseModel):
    id: str          # uuid4 hex
    parent_id: str | None
    timestamp: str

def state_from_entries(entries, leaf_id=None) -> SessionState:
    """无状态 reducer：重放条目 → 得到状态。12-Factor F12 的字面实现。"""
```

- 存储：`~/.mini/sessions/<项目slug>/<uuid>.jsonl`，一行一条目；
- **落盘时机 = 每个 `message_end` 事件**（挂在 harness 的 subscribe 上），消息完成即持久，不等 run 结束；同时追加 `leaf` 指针条目；
- 空会话**延迟建文件**（第一条真实消息才落盘）；
- `--resume <id>`：读全部条目 → 取最新 leaf → 重放路径 → 恢复 harness → **先补悬空 tool_result 再接受新 prompt**；
- 系统提示词不入会话文件，resume 时重建。

**验收**：核心测试是一场"事故演习"——FakeProvider 跑到工具执行中途直接抛 SIGKILL 级中断（模拟断电），然后 resume：transcript 合法、能继续对话；reducer 纯函数测试（同一批条目重放两次结果相等）；手工用文本编辑器打开 JSONL 能看懂每一行（"历史可以用肉眼读"是验收标准之一）。

**对照**：tau `tau_agent/session/`（entries→jsonl→tree→memory 四个小文件）+ 根目录 `session-temp.jsonl` 样本；pi `docs/session-format.md`。

### 9.9 M8 · CLI print 模式：第一次真正可用（半天）

```bash
mini -p "explain this repo"            # 只打印最终回答
mini -p "fix the failing test" --json  # 每行一个 JSON 事件（给脚本/CI 用）
mini --resume <id> -p "continue"
```

- argparse/typer 皆可；`-p` 进 print 模式，事件渲染器做成 Protocol（text/json 两个实现）；
- 非 TTY 时自动选 print 模式（pi 的行为）。

**验收**：拿它干一件真活——**用你自己的 mini 修一个真实仓库里的真实 bug**。这是整条路线的第一个奖励时刻，也是最诚实的集成测试。顺手在管道里跑：`echo "..." | mini -p - | grep ...`。

**对照**：tau `cli.py` + `rendering/`；pi `main.ts` 的 `resolveAppMode`。

### 9.10 M9 · 压缩与溢出恢复（1–2 天）

照抄两边共同参数与规则（4.6 节）：
- 估算：chars/4 + 每消息/每工具开销常数（够用；升级真实 usage 是后话）；
- 触发：`估算 > contextWindow − 16384`；保留最近约 20,000 tokens；
- **切点永不落在 tool_call 与 tool_result 之间**（从最新往旧走，跳过非法切点）；
- 摘要用模型生成，结构化提示词六段：Goal / Constraints / Progress(Done·InProgress·Blocked) / Key Decisions / Next Steps / Critical Context；
- 压缩 = 追加 `compaction` 条目（记录 summary + 被覆盖的条目 id），reducer 重放时在原位置折叠成一条合成 UserMessage；
- **溢出恢复**：provider 报上下文溢出 → 压缩一次 → `continue` 重试一次 → 再溢出就放弃并告知用户；溢出**不走**普通重试通道。

**验收**：把阈值调成 2k 强制触发，断言：切点合法、摘要条目落盘、resume 后重放正确折叠、二次溢出正确放弃。

**对照**：tau `context_window.py`；pi `core/compaction/compaction.ts`（看两段式摘要与 read/modified 文件清单——v2 素材）。

### 9.11 M10 · 选做扩展包（每项 1–3 天，按兴趣挑）

| 扩展 | 一句话难点 | 对照 |
|---|---|---|
| Textual TUI | 事件→显示状态放进独立 adapter；prompt 跑 worker；**递增 run_id 丢弃取消后迟到的事件** | tau `tui/adapter.py`、`app.py` |
| 树形分支 | 分支 = 追加新 leaf 指针；被弃分支生成 branch_summary | tau `session.py` `branch_to_entry` |
| `beforeToolCall` 钩子 | 你的权限系统/扩展系统的种子——一个能 block 的回调而已 | pi `agent-loop.ts` `prepareToolCall` |
| 真实 usage/成本 | 在 `response_end` 事件加 usage 字段，替换 chars/4 | pi `Usage`/`calculateCost` |
| 并行工具执行 | `asyncio.gather` + 结果按原始顺序回填 + 文件锁 | pi `executeToolCalls` |
| 第二个 provider | OpenAI `/chat/completions` 适配器 → 亲手体会"中立层"的价值 | tau `openai_compatible.py` |
| Skills | 系统提示词里只放 `<available_skills>` 索引，模型自己 read | tau `skills.py` |

### 9.12 里程碑总表

| # | 产出 | 关键验收 | 对照 tau | 对照 pi | 预估 |
|---|---|---|---|---|---|
| M0 | 三包骨架 + 质量门 | 依赖方向守卫测试 | `pyproject.toml` | `tsconfig.base.json` | 0.5 天 |
| M1 | 消息/工具/事件类型 | round-trip + forbid | `messages.py` `tools.py` `events.py` | `ai/src/types.ts` | 0.5 天 |
| M2 | FakeProvider + 1 真适配器 | 脚本流测试；error 不 throw | `provider.py` `anthropic.py` `fake.py` | `api/anthropic-messages.ts` | 1–2 天 |
| M3 | 循环（async generator） | 精确事件序列 + 四守卫 | `loop.py` | `agent-loop.ts` | 1 天 |
| M4 | read/write/edit/bash | 唯一匹配/截断 footer/进程组击杀 | `tools.py` | `core/tools/` | 2–3 天 |
| M5 | Harness + 双队列 + 取消 | steer 边界注入；重入抛错 | `harness.py` | `agent.ts` | 1 天 |
| M6 | 系统提示词拼装 | golden file + <1200 token 预算 | `system_prompt.py` | `system-prompt.ts` | 0.5 天 |
| M7 | JSONL 条目树 + resume | 断电演习 → resume 合法 | `session/` | `session-format.md` | 1–2 天 |
| M8 | CLI print/json 模式 | 用它修一个真 bug | `cli.py` `rendering/` | `main.ts` | 0.5 天 |
| M9 | 压缩 + 溢出恢复 | 强制小阈值全链路 | `context_window.py` | `compaction.ts` | 1–2 天 |
| M10 | TUI/分支/钩子…（选做） | — | 各处 | 各处 | 按需 |

### 9.13 复刻过程十大典型翻车（提前打疫苗）

1. 执行了被截断（`finish_reason=length`）消息里的工具调用 → 半截 JSON 参数乱写文件；
2. 取消/崩溃后不补悬空 tool_result → 下一轮 provider 直接 4xx 拒收；
3. 压缩切点切开 tool_call/tool_result 对 → 同上，transcript 非法；
4. 运行中允许 `prompt()` 重入 → 两个循环写同一个 transcript；
5. 工具异常直接炸掉循环 → 应转 `ok=False` 结果，错误属于模型的输入；
6. edit 匹配到多处仍替换第一处 → 必须"恰好一次"否则报错；
7. bash 超时只杀 shell 不杀进程组 → 孤儿进程越积越多；
8. 工具输出不截断 → 一条 `cat big.log` 塞爆上下文；截断了又不给续读提示 → 模型原地卡死；
9. 系统提示词**开头**放日期/随机值 → KV 缓存前缀全废，成本×10（日期放末尾）；
10. 把错误藏起来不进上下文 → 模型看不到失败，永远重复同一个错误。

（第 11 条隐藏关卡：把"上下文溢出"当普通错误重试——重试永远解决不了溢出，它只属于压缩通道。）

---

## 10. 模型接入指南：格式要求、统一层与本地模型

> 本章回答两个高频问题：**"随便什么模型的 API 都能接吗？有格式要求吗？"** 和 **"现在的最佳实践是不是 API 都用统一格式？"** 简答：几乎都能接，但有两条硬性要求；业界统一的是**你自己代码里的内部格式**，市面上的 API 从来没有统一过。文末给出 mini / tau / pi 三个层面接入本地模型的可用配置（均核对自官方文档）。

### 10.1 接入任意模型的两条硬性要求

**① API 必须支持工具调用（tool use / function calling）——不可妥协。** Agent 循环的本质是"模型返回结构化 tool_calls → harness 执行 → 以专门的消息角色发回结果"。API 必须能：接收工具的 JSON Schema 定义、返回可解析的工具调用、接受工具结果消息。没有原生工具调用的模型理论上可用提示词包装（让模型输出 JSON 自己解析），但可靠性差一个量级，学习阶段不建议碰。

**② 最好支持流式（SSE），但不是必须。** 事件流架构不依赖流式——不支持流式的 API 把整条响应当一个事件发即可，只是没有打字机效果。

另外要分清**接口能力与模型能力**：接得上 ≠ 跑得好。工具调用 JSON 写不对、多轮循环坚持不下来，是模型问题不是 harness 问题（见 10.5 的本地模型部分）。

### 10.2 wire 格式现状：没有标准，只有事实标准

LLM 推理 API 至今没有行业标准。实际存在的主流 wire 格式就四种，"同一件事的四种写法"对照：

| | OpenAI Chat Completions | Anthropic Messages | Google Gemini | OpenAI Responses |
|---|---|---|---|---|
| 系统提示词 | messages 里 `role:"system"`（推理模型用 `developer`） | 顶层 `system` 参数 | `systemInstruction` | `instructions` 参数 |
| 工具定义 | `tools:[{type:"function", function:{name, parameters}}]` | `tools:[{name, input_schema}]` | `tools:[{functionDeclarations:[…]}]` | `tools:[{type:"function", name, …}]` |
| 工具结果 | `role:"tool"` 消息 + `tool_call_id` | **user 消息**里的 `tool_result` 内容块（`is_error`） | `functionResponse` part | `function_call_output` 条目 |
| 流式 | `choices[].delta`，工具参数分片拼接 | `content_block_start/delta/stop` + `input_json_delta` | `streamGenerateContent?alt=sse` | 语义化 `response.*` 事件 |
| 认证 | `Authorization: Bearer` | `x-api-key` + `anthropic-version` 头 | URL `?key=` | `Authorization: Bearer` |
| 怪癖举例 | `max_tokens` vs `max_completion_tokens` 字段名分裂 | `max_tokens` 必填；工具结果挂在 user 角色下 | JSON Schema 需净化；`thought_signature` 必须回传 | 工具调用 ID 可长达 450+ 字符 |

两个关键事实：

- **OpenAI Chat Completions 是事实标准**：几乎所有厂商（OpenRouter、DeepSeek、Groq、xAI、智谱、Kimi、通义兼容模式……）和所有本地引擎都克隆它。写好这一个适配器 ≈ 接入 90% 的模型。
- **反向克隆潮**：DeepSeek、Kimi、智谱等近来还提供 **Anthropic 兼容端点**——为的是让 Claude Code 系工具零改动接入。行业在克隆事实标准，而不是等一个委员会标准。

pi 的实证数据是最好的注脚：**9 种协议实现覆盖 36 个厂商、1,057 个模型**（作者原话："四五种 wire API 就能覆盖整个市场"）；tau 用 5 个适配器覆盖 24 个内置 provider，其中 `OpenAICompatibleProvider` 一个类打二十几家。

### 10.3 最佳实践：内部统一 = 中立层 + 适配器 + 逃生舱

几乎所有认真做的 agent 项目都收敛到同一个形状——**核心循环只面对一套自己定义的中立数据模型，每个厂商一个适配器在边界处翻译**（pi-ai、tau_ai、Vercel AI SDK、PydanticAI、LiteLLM、OpenAI Agents SDK 全是这个模式）。理由有四：

1. **循环只处理一种形状**：pi 的"stream 永不 throw、失败编码为流内 error 事件"契约，只有在统一层上才成立；
2. **会话可移植**：pi 的 `transformMessages` 归一化工具调用 ID、为非视觉模型降级图片，才有"聊到一半从 Claude 切到 GPT"；
3. **可测试**：FakeProvider 只需伪造你自己的中立事件，不用伪造四种厂商协议；
4. 这就是 12-Factor F3"拥有你的上下文窗口"的工程落地——你拥有中立 transcript，wire 格式只是每次请求的派生品。

**但要避开"最小公分母陷阱"。** 各家都有独有能力：Anthropic 的 cache_control 断点、Gemini 的 thought_signature、五花八门的 thinking 参数。把 API 压平成交集，这些全丢——这是早年 LangChain/LiteLLM 被诟病的核心。成熟做法是**统一事件流 + 逃生舱**：

- pi：每种 API 一套 compat 类型，约 20 个怪癖开关 + 10 种 thinking 文本方言；
- tau：中立 `ToolCall` 上留 `thought_signature` 字段，把 Gemini 的私有数据原样透传回去。

统一 ≠ 抹平差异，是"共性走主干道、个性走透传"。

两个必要的澄清：

- **单厂商深耕是正当的另一条路**：Claude Agent SDK 就是 Claude-only，换来吃满厂商全部能力（服务端压缩、上下文编辑、缓存细节），零适配税。产品绑定一家模型时，统一层是纯开销。
- **MCP 统一的是"工具"，不是模型 API**：它解决"agent 怎么接外部工具生态"，与推理 API 格式是两个正交问题，别混淆。

### 10.4 三种接入姿势

| 姿势 | 做法 | 适合 | 代价 |
|---|---|---|---|
| **自建适配层** | 像 pi/tau：中立事件流 + 每厂商一个适配器 | 完全控制、多厂商切换；你的 mini-harness 走这条 | 兼容性长尾自己扛（按需扛，用到才写） |
| **走网关** | 对 OpenRouter / Vercel AI Gateway / LiteLLM proxy / new-api（国内生态）说 OpenAI 格式，翻译外包给网关 | 快速覆盖长尾模型、统一计费 | 多一跳延迟；翻译质量看网关；部分厂商特性丢失 |
| **单厂商深耕** | 直接用 Claude Agent SDK 或裸厂商 SDK | 产品绑定一家、要吃满厂商特性 | 无可移植性 |

三者可组合：比如自建适配层里只写 `openai-compatible` 和 `anthropic` 两个适配器，长尾模型统一从 OpenRouter 走 `openai-compatible` 进来——pi 和 tau 实际都是这么覆盖长尾的。

### 10.5 本地模型：完全可以，注意四个坑

主流本地引擎都提供 OpenAI 兼容端点：

| 引擎 | 端点 | 工具调用 |
|---|---|---|
| Ollama | `http://localhost:11434/v1/chat/completions` | ✅ 原生支持（取决于模型） |
| vLLM | `http://localhost:8000/v1/…` | ✅ 需启动参数 `--enable-auto-tool-choice --tool-call-parser <按模型选>` |
| LM Studio | `http://localhost:1234/v1/…` | ✅ 较新版本支持 |
| llama.cpp（llama-server） | `http://localhost:8080/v1/…` | ⚠️ 取决于聊天模板，参差 |

四个坑：

1. **模型能力是真正的瓶颈**。7B–14B 小模型工具调用 JSON 经常写错、多轮循环容易跑偏。要"能修真实 bug"的体验，本地建议 Qwen3-32B / Qwen2.5-Coder-32B 起步。你的 M3 守卫（参数校验失败 → 错误结果发回模型）恰好是为这种情况准备的。
2. **"OpenAI 兼容"不是 100% 兼容**：usage 字段缺失、流式 tool call 分片方式不同、`max_tokens` 字段名不同、thinking 输出格式五花八门（`<think>` 标签 vs `reasoning_content` 字段——tau 的 `thinking_format` 分发器处理了 7 种方言）。你的 mini 只需处理实际在用的那一两个引擎，遇到一个修一个。
3. **上下文窗口小**：本地部署常见 8k–32k，压缩（M9）会更早触发——`contextWindow` 要配成引擎实际值，别抄云端的 200k。
4. **前缀稳定依然有收益**：本地没有 token 计费，但 vLLM/llama.cpp 的 prefix caching 与云端 KV cache 同理——"日期放系统提示词末尾"这条规矩本地同样适用。

### 10.6 实操配置：三个层面的接入示例

**① 你的 mini（M2 适配器直接指向本地）**——`openai-compatible` 适配器 + 三行配置：

```python
provider = OpenAICompatibleProvider(
    base_url="http://localhost:11434/v1",
    api_key="ollama",          # Ollama 忽略鉴权，占位即可
)
# run_agent_loop(provider=provider, model="qwen3:32b", ...)
```

**② tau 接 Ollama**——用户级 `~/.tau/catalog.toml` overlay（示例核对自官方 `reference/configuration.md`，其文档示例本身就是 11434 端口）：

```toml
schema_version = 1

[[providers]]
name = "ollama"
display_name = "Ollama (local)"
kind = "openai-compatible"          # 支持 openai-compatible / anthropic / openai-codex
base_url = "http://localhost:11434/v1"
api_key_env = "OLLAMA_API_KEY"      # 占位；本地引擎不校验
models = ["qwen3:32b"]
default_model = "qwen3:32b"

[providers.context_windows]
"qwen3:32b" = 32768                 # ← 坑 3：配成引擎实际窗口
```

注意 tau **有意只读用户级 overlay**（没有项目级 `.tau/catalog.toml`）——克隆一个仓库不能悄悄把你的 provider 重定向到恶意 base_url。超时/重试/自定义 header 放 `~/.tau/providers.json`。

**③ pi 接 Ollama**——`~/.pi/agent/models.json`（示例核对自官方 `docs/models.md` 的 Minimal Example）：

```json
{
  "providers": {
    "ollama": {
      "baseUrl": "http://localhost:11434/v1",
      "api": "openai-completions",
      "apiKey": "ollama",
      "models": [
        { "id": "qwen2.5-coder:7b" },
        { "id": "llama3.1:8b", "contextWindow": 32768 }
      ]
    }
  }
}
```

pi 的文档还点名了本地引擎最常见的两个 compat 开关：服务器不认识推理模型的 `developer` 角色时设 `compat.supportsDeveloperRole: false`（系统提示词回退为 `system` 消息）；不支持 `reasoning_effort` 时设 `compat.supportsReasoningEffort: false`——"这通常适用于 Ollama、vLLM、SGLang 及类似的 OpenAI 兼容服务器"。这正是 10.3 说的逃生舱机制在真实产品里的样子。

### 10.7 给 mini-harness 的落地顺序

- 主用**本地/国产模型** → 把第 9 章 M2 的建议反过来：**先写 `openai-compatible` 适配器**（一个吃遍 90%），Anthropic 适配器放到 M10 的"第二个 provider"再写；
- 主用 **Claude** → 按原顺序先写 `anthropic-messages`（SSE 结构最清晰，也最适合学习）；
- 无论哪条路：**怪癖驱动开发**——compat 开关遇到一个加一个，不要预先设计"支持一切"的抽象。pi-ai 那 3.6 万行是十几个厂商的坑逐个踩出来的，不是设计出来的。

---

## 11. 深度对比：pi/tau 与 LangGraph 等主流框架

> 第 6 章给了一张选型速查表；本章回答更根本的问题：**这两类东西在"是什么"的层面差在哪里**。一句话答案：pi/tau 是"**你拥有循环**的库"，LangGraph 们是"**框架拥有执行、你来填空**"的运行时——控制反转（IoC）的方向相反。这不是谁高级谁原始，而是两种世界观，各有真实的胜场。

### 11.1 三种控制流范式

Agent 系统的控制流本质上只有三种归属方式：

**① 模型驱动循环**（pi、tau、Claude Code、Claude Agent SDK、你的 mini）
"下一步干什么"由 **LLM 在每一轮里决定**——它可以调工具、可以继续、可以停。harness 只提供工具、边界和安全网（截断守卫、异常隔离、压缩）。控制流的复杂度不在代码里，在模型的权重里。

**② 显式图 / 状态机**（LangGraph）
"下一步干什么"由**开发者画的图**决定：节点（LLM 调用、工具执行、纯函数）+ 边（含条件边）构成状态机；状态是带 reducer 合并规则的类型化 dict，由 checkpointer 逐步持久化。LLM 只在节点**内部**说话，节点之间怎么走是图说了算。LangGraph 1.0（2025-10 GA）与 LangChain 1.0 的 `create_agent` 都建在这个运行时上。

**③ 代理间交接**（OpenAI Agents SDK 的 handoffs、CrewAI 的角色制）
介于两者之间："当前由哪个 agent 说话"可以转移，每个 agent 内部仍是模型驱动循环，但拓扑（谁能交给谁）是开发者预先声明的。

对应 Anthropic《Building Effective Agents》的光谱：**LangGraph 的主场在 workflow 端**（预定义路径的五种模式：链式、路由、并行、orchestrator-workers、evaluator-optimizer），**pi/tau 的主场在 agent 端**（模型自主 + 环境反馈）。两边都能客串对方——LangGraph 的 `create_react_agent` 里就藏着同样的 10 行循环，pi 也能靠提示词约束出固定流程——但顺着各自的纹理用才不别扭。

> 旁注：smolagents 的 CodeAgent 是一条**正交的轴**——它改的不是"谁拥有控制流"，而是"动作的表达格式"（让模型写可执行 Python 而非 JSON 工具调用，约省 30% 步数）。这个思路可以嫁接到任何一种范式上。

### 11.2 同一个 agent 的四种写法

任务相同：一个带 read/bash 工具的最小 coding agent。看控制权怎么一步步移交出去：

**(a) pi/tau/mini 风格 —— 循环是你的代码**

```python
harness = AgentHarness(provider=provider, tools=[read_tool, bash_tool], system=SYSTEM)
async for event in harness.prompt("fix the failing test"):
    render(event)   # 渲染、落盘、日志、指标——每一步都是你的决定
```

**(b) LangGraph —— 你声明图，执行归框架**

```python
from langgraph.prebuilt import create_react_agent   # LangChain 1.0 起: create_agent
from langgraph.checkpoint.memory import MemorySaver

agent = create_react_agent(model, tools=[read_file, run_bash], checkpointer=MemorySaver())
for chunk in agent.stream({"messages": [("user", "fix the failing test")]},
                          config={"configurable": {"thread_id": "t1"}}):
    ...
# 手工等价物：StateGraph(MessagesState) + LLM 节点 + ToolNode + tools_condition 条件边
```

**(c) OpenAI Agents SDK —— Runner 拥有循环，你声明 Agent**

```python
agent = Agent(name="coder", instructions=SYSTEM, tools=[read_file, run_bash])
result = await Runner.run(agent, "fix the failing test", session=session)
```

**(d) Claude Agent SDK —— 连工具都是别人的**

```python
from claude_agent_sdk import query, ClaudeAgentOptions
async for msg in query(prompt="fix the failing test",
                       options=ClaudeAgentOptions(allowed_tools=["Read", "Bash"])):
    ...   # 循环、工具实现、自动压缩、会话、权限全部内置
```

从 (a) 到 (d)：**控制递减、开箱能力递增**。注意 (b) 拆开 prebuilt 后里面还是那 10 行循环——框架没有让模型变聪明，能力永远来自"模型 + 工具 + 上下文"，框架改变的只是这三样东西由谁、以何种代价来组装。

### 11.3 逐维度硬对比

| 维度 | pi / tau | LangGraph | OpenAI Agents SDK | Claude Agent SDK |
|---|---|---|---|---|
| 控制流所有权 | 你写 `while` | 框架执行你声明的图 | 框架 run loop + handoff 拓扑 | 框架整机 |
| 状态模型 | append-only 消息 transcript（+条目树） | 类型化 State dict + reducer 合并 | Session 消息列表 | 内部 transcript |
| 持久化 | JSONL 文件树，肉眼可读 | Checkpointer（内存/SQLite/Postgres），按 thread_id 寻址，支持 time-travel | Sessions（SQLite 等） | JSONL 会话，resume/fork |
| 分支/回退 | 移动 leaf 指针（追加式） | `get_state_history` + `update_state` fork 出新分支 | 手动复制 session | `/rewind`、fork |
| 事件/流式 | 自定义 AgentEvent 联合类型，前端唯一契约 | `stream(mode="updates/messages/…")` 多模式 | 流式事件 + 内置 tracing | SDK message 流 |
| HITL（人在环上） | 无内置；pi 用 `tool_call` 钩子自建 | **`interrupt()` + `Command(resume=…)` 一等公民** | guardrails + 工具审批 | permission modes + hooks |
| 多 agent | 不内置：进程级组合（"再开一个 pi"） | 子图、Send API（map-reduce）、supervisor 模式 | **handoffs 一等公民** | subagents 内置 |
| 上下文压缩 | **内置**（阈值 + 结构化摘要 + 溢出恢复） | 自己写 summarization 节点（或 langmem） | 辅助函数级支持 | **自动压缩内置** |
| 提示词透明度 | 全部可见（<1k tokens） | 高（自写提示词；prebuilt 有默认值） | 中 | 低（大量内置提示词） |
| 依赖足迹 | tau 8 个运行时依赖；pi 每包个位数 | langgraph + langchain-core 生态 | openai 系 | 全家桶（Node 运行时） |
| 测试路径 | FakeProvider 脚本化事件流 | 按节点单测 + mock 模型 | mock 模型 | 端到端为主 |
| 天然负载 | coding agent、上下文敏感任务 | 长时可恢复业务流、多阶段管道 | 多 agent 客服/路由 | "要一个现成的 Claude Code" |

**概念对照表（Rosetta Stone）**——学会一边后快速迁移到另一边：

| pi/tau 概念 | LangGraph 里的对应物 | 备注 |
|---|---|---|
| `AgentHarness.prompt()` | `graph.invoke/stream(config={thread_id})` | thread ≈ 会话 |
| steering / follow-up 队列 | `interrupt()` + `Command(resume=…)` | **方向相反**：pi/tau 是用户把消息推进运行中的循环；LangGraph 是图主动停下来等人 |
| 会话 JSONL 树 + leaf 指针 | checkpointer 历史 + `update_state` fork | 都是"状态 = 可回放的历史" |
| `transformContext` / `convertToLlm` | 节点内自由改 state、`pre_model_hook` | 都是发请求前的最后一道闸 |
| `beforeToolCall` 钩子（可 block） | `interrupt_before=["tools"]`、包装 ToolNode | pi 的钩子给扩展用，LG 的给审批用 |
| compaction 条目 + reducer 重放 | summarization 节点 + `RemoveMessage` | pi/tau 内置，LG 自己搭 |
| FakeProvider | mock ChatModel | 测试哲学相同：不打真 API |

### 11.4 两边挨的批评，各自该听哪一半

**对 LangGraph 系的批评**（12-Factor 的名句："框架把你带到 70–80%，然后你为了上生产把它拆了"）：
- **仍然成立的部分**：prebuilt 组件自带默认提示词，不主动挖就不知道模型实际看到什么（违反 F2"拥有提示词"）；出错时调试栈从你的代码穿过框架内部再到模型，认知负担真实存在；生态惯性会把你往 LangChain 全家桶里带。
- **已经过时的部分**：LangGraph 1.0 的核心运行时其实相当薄（图 + checkpoint + interrupt），提示词可以 100% 自控；**checkpointer/time-travel/interrupt 是真实的、pi/tau 没有对等物的价值**——把它当"又一个臃肿框架"一票否决是 2023 年的刻板印象。

**对 pi/tau 式薄 harness 的批评**（"玩具"、"缺企业能力"）：
- **不成立的部分**："玩具"论被 Terminal-Bench 2.0 正面反驳——<1k token 的 pi 与重型 harness 成绩同级；"简单 = 能力弱"混淆了 harness 复杂度与系统能力。
- **成立的部分**：HITL 审批、审计日志、团队治理、评测流水线确实要自建；"自己拥有一切"的前提是团队有能力、有意愿拥有——对一个 20 人共同维护的业务系统，"每人自己发明一套循环"比框架约定更糟。12-Factor 说的是"用自己的平凡代码拥有它"，不是"不需要这些能力"。

### 11.5 什么时候图真的赢，什么时候循环真的赢

**图（LangGraph 系）的真实胜场**——共同点是"控制流必须由代码保证，而不是靠模型自觉"：
1. **跨天暂停的长时业务流**：贷款审批等 3 天、审批人周一才上班——`interrupt()` + Postgres checkpointer 让工作流睡在数据库里随时唤醒。pi/tau 的 JSONL resume 覆盖的是"人重新打开对话"，不是"流程在服务端持久暂停"。
2. **预定义多阶段管道**：Anthropic 五种 workflow 模式的工程化落地（先分类再路由、并行打分再汇总）。
3. **硬性合规门**：某一步**必须**有人签字——用图的边保证，而不是提示词里写"请先询问用户"。
4. **团队标准化与可观测性**：统一的图抽象 + LangSmith 追踪，比每人一套自制循环更可维护。

**循环（pi/tau 式）的真实胜场**——共同点是"模型的自主性就是产品力"：
1. **coding agent**：探索路径无法预画成图（Anthropic 自己也说 coding 不适合多 agent 编排）；
2. **上下文精确控制**：逐 token 掌控输入、KV-cache 前缀纪律、<1k 开销；
3. **嵌入自己的产品**：8 个依赖 vs 一个生态，供应链审计面完全不同；
4. **快速跟进模型演进**："每次新模型发布就删代码"——层越薄，删得越快。

### 11.6 务实结论：混合，而不是站队

生产系统里最常见的成熟形态是**两层各取所长**：

```text
外层（工程可靠性）：LangGraph / Temporal —— 编排、暂停、审批、重试、审计
   └── 内层（模型自主性）：pi/tau 式薄 harness —— 图节点里那个"会写代码的工人"
```

Anthropic 的多 agent 研究系统实际就是这个形状：orchestrator 是工程代码，workers 是各自带干净上下文的 agent 循环。具体的接线方式现成就有：pi 的 `--mode rpc`（30+ 命令经 stdin/stdout 驱动）或 SDK 可以直接把一个完整 coding agent 挂进任何编排器的节点里；Claude Agent SDK 同理。

**学习顺序上的不对称**：先精通循环（第 9 章亲手造一个），再学 LangGraph 只需要半天——你会立刻认出"图节点里还是我那 10 行"；反过来，先学框架的人往往要花更久才能看穿抽象、建立第 4 章那些不变量的直觉。这就是本教程从 pi/tau 入手的原因。

### 11.7 决策清单

按顺序回答，通常问到第 3 题就有答案了：

1. 任务是**开放探索**（修 bug、研究、运维排查）还是**预定义阶段**（审批流、内容管道）？——前者循环，后者图。
2. 流程需要**跨小时/天暂停等人**吗？——需要 → checkpointer 系（LangGraph/Temporal）。
3. 你需要**逐 token 控制**进入模型的上下文吗？——需要 → 薄 harness。
4. 接受**绑定单一模型厂商**换取开箱能力吗？——接受 → Claude Agent SDK。
5. 主要负载是**多 agent 客服/路由**？——OpenAI Agents SDK 的 handoffs 最顺手。
6. 团队规模与治理要求？——个人/小团队偏薄 harness；大团队标准化偏框架。
7. 还拿不准？——按第 9 章花两周造一个 mini。造完你对这张清单的每一行都会有自己的判断，这本身就是本章的真正目的。

---

## 12. 延伸样本：rust-ai-agent（Rust）和 pi/tau 一样吗？

> 有读者问：GitHub 上的 [`solenovex/rust-ai-agent`](https://github.com/solenovex/rust-ai-agent)（B 站 UP 主「软件工艺师」的视频系列《用 Rust 构建 AI Agent》配套代码）和 pi/tau 是一类东西吗？
>
> **简答：genre 相同（都是教学项目），但 shape 不同——它当前不是 coding-agent harness，甚至不是"循环式 agent"，而是"增强 LLM + 结构化输出 + 评测驱动"的另一种范式。** 它恰好是本文档最好的一个反例样本：帮你看清"AI Agent"这个词覆盖的范围有多宽，也正好补上 pi/tau 缺的那一块（评测）。
>
> 分析基于 2026-07-13 快照（约 24 star、6 个 commit、按集数打 tag `ep01…ep04`、edition 2024、MIT 前提待核）。**这是一个早期、随视频推进的教学仓库，后续集数可能长出工具循环——本节结论限定在当前快照。** 未逐文件精读，架构判断来自 Cargo.toml + 目录结构 + `gaia/solver.rs` 摘要。

### 12.1 它是什么

`async-openai` SDK + `tokio` + `reqwest` + `schemars`（从 Rust 结构体 derive JSON Schema）+ `backon`（指数退避重试）搭起来的教学工程。目录透露了它的骨架：

- **`src/llm/`** —— LLM 交互层，但组织维度是**交互模式**而非 provider：`complete.rs`（非流式）、`stream.rs`（流式）、`structured.rs` + `structured_ds.rs`（结构化输出 + schema 约束）、`semaphore.rs`（并发/限流控制）。注意这里没有"多 provider 中立层"——它直接吃 `async-openai` 的 OpenAI 兼容 wire 格式。
- **`src/gaia/`** —— 全盘围绕 **GAIA 基准**组织（GAIA = General AI Assistants，Meta + HuggingFace 2023 年提出的通用助手评测集，题目需要网页检索、文件解析、数学、多模态）：`dataset.rs`（加载数据集）、`solver.rs`（求解一道题）、`evaluator.rs`（给答案打分）、`models.rs`。
- **`src/bin/gaia.rs`** —— 可运行入口。

**最关键的一点**：`solver.rs` 的 `solve_problem()` 是**单次 LLM 调用**——系统提示词 + 用户题目 → 强制 JSON 结构化输出（`GaiaOutput` 由 schemars 生成 schema）→ 反序列化 → 用 `backon` 重试。**没有 `while` 循环、没有工具调用、没有把工具结果喂回模型。** 这不是 agent 循环，是"增强 LLM"直接答题，外面套一个数据集评测器。

### 12.2 三条轴上和 pi/tau 的定位

用本文档一直在用的坐标系来放它：

| 轴 | rust-ai-agent（当前快照） | pi / tau |
|---|---|---|
| **意图 genre** | ✅ 教学项目（和 tau 同类——"为学习而写"） | tau 教学 / pi 生产 |
| **控制流范式**（§2.1、§11.1） | **增强 LLM / workflow 端**：单次调用 + 结构化输出，无循环 | **agent 端**：模型驱动的 tool-use 循环 |
| **领域** | 通用助手 / 跑基准（GAIA answer-only） | 终端 coding（read/write/edit/bash + 会话 + TUI） |
| **provider 层** | 单一，直接用 `async-openai` SDK | 自建中立层（tau 5 适配器 / pi 9 协议）+ 事件流 |
| **工具 schema** | `schemars` 从 Rust 类型 **derive**（第三种流派） | tau 手写 dict / pi TypeBox |
| **有没有 agent 循环** | ❌ 当前没有 | ✅ 核心就是循环 |
| **有没有系统评测** | ✅ **有**（`evaluator.rs` 对 GAIA 数据集打分） | ❌ 两者都缺（见 §5.2） |

一句话：**它和 tau 共享"教学"的灵魂，但站在 Anthropic《Building Effective Agents》光谱的另一端**——pi/tau 在"agent"（模型自主循环），rust-ai-agent 在"workflow / 增强 LLM"（预定义的单步 + 结构化输出）。这不是谁高级，是两种建造块（§2.1）。

### 12.3 为什么它对学习反而有价值：三个互补点

正因为不一样，它填的是 pi/tau 教不了的空白：

1. **它是"增强 LLM"建造块的干净样本。** §2.1 讲过 workflow 和 agent 的区别；rust-ai-agent 让你看见"没有循环的 AI 应用"长什么样——很多生产系统其实就停在这里，一次结构化调用足矣（Anthropic 的第一条建议："能用单次调用就别上 agent"）。
2. **它有 pi/tau 都缺的评测脊椎。** §5.2 专门标注过：pi/tau 都没有系统化 evals。而 rust-ai-agent 的整个 `gaia/` 就是"数据集 → solver → evaluator 打分"的评测循环——这正是《Writing effective tools for agents》反复强调的"从真实任务建 eval"。**想给你的 mini（第 9 章）补 M10 评测扩展，这就是现成的参照结构。**
3. **它示范了 Rust 的结构化输出流派。** `schemars` 从类型 derive schema，是继 tau 手写 dict、pi TypeBox 之后的第三种工具/输出 schema 做法，类型安全最强。想理解"schema 从哪来"的三种权衡，三个项目正好凑齐。

### 12.4 如果你想把它变成"真 agent"

它现在缺的，恰好是第 9 章 M3–M8 教的东西。把它升级成 pi/tau 那样的循环式 agent，路线图就是：

- **加循环（M3）**：把 `solve_problem()` 的单次调用包进 `while`，读 `tool_calls`（`async-openai` 原生支持 function calling）→ 执行 → 结果回填 → 重复。四大守卫照搬。
- **加工具（M4）**：GAIA 需要网页检索/文件解析——正好给它 web-search、read-file、python-exec 工具（GAIA 的典型工具面），而不是 coding 的 edit/bash。
- **加会话（M7）**：多步求解要留痕，追加式 JSONL 条目树同样适用。
- 它已有的 `evaluator.rs` 反而是 pi/tau 要补的——**双向取长补短**。

> 顺带一提：如果你找的是"Rust 版的 pi"（真正对标的 coding-agent harness），社区里有 [`Dicklesworthstone/pi_agent_rust`](https://github.com/Dicklesworthstone/pi_agent_rust)（自称"零 unsafe 的高性能 Rust coding agent CLI"）更接近；Rust 原生 agent 框架生态另有 Rig、AutoAgents、OpenFANG 等（对应第 6 章光谱的"框架"档）。rust-ai-agent 与它们都不同——它是**教你从头写**的视频教程，不是拿来即用的框架。这一点上，它和 tau 的定位最像，只是选了"评测驱动的通用助手"而非"终端 coding"作为教学载体。

### 12.5 结论

「和 pi/tau 一样吗？」——**教学初心一样，技术形态不一样**。把三者并排，你得到的是一张更完整的地图：

- **tau**：教你写 *coding-agent 循环*（Python，agent 端）
- **pi**：同一套设计的 *生产形态*（TypeScript，agent 端，带扩展/多 provider/会话全家桶）
- **rust-ai-agent**：教你写 *增强-LLM + 评测*（Rust，workflow 端，结构化输出 + GAIA 打分）

学习建议：**主线仍是先 tau 后 pi**（第 8 章）建立 agent 循环的完整直觉；rust-ai-agent 作为**支线**看两样东西——「没有循环的 AI 应用」的样子，以及「评测驱动开发」怎么组织。等你做第 9 章的 mini 时，把它的 `evaluator.rs` 思路借过来做 M10。

---

## 13. 参考资料

**项目本体**
- pi：仓库 `~/workspace/code/pi` · https://pi.dev · https://github.com/earendil-works/pi
- tau：仓库 `~/workspace/code/tau` · https://twotimespi.dev · https://github.com/alejandro-ao/tau · PyPI `tau-ai`

**必读文章（按学习顺序）**
1. Thorsten Ball, *How to Build an Agent*（2025-04）— https://ampcode.com/how-to-build-an-agent
2. Philip Zeyliger, *The Unreasonable Effectiveness of an LLM Agent Loop with Tool Use*（2025-05）— https://sketch.dev/blog/agent-loop
3. Anthropic, *Building Effective Agents*（2024-12）— https://www.anthropic.com/engineering/building-effective-agents
4. Mario Zechner, *pi: a minimal coding agent harness*（2025-11-30）— https://mariozechner.at/posts/2025-11-30-pi-coding-agent/
5. Anthropic, *Writing effective tools for agents*（2025-09）— https://www.anthropic.com/engineering/writing-tools-for-agents
6. Anthropic, *Effective context engineering for AI agents*（2025-09）— https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
7. 12-Factor Agents — https://github.com/humanlayer/12-factor-agents
8. Manus, *Context Engineering for AI Agents: Lessons from Building Manus*（2025-07）— https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus
9. Anthropic, *How we built our multi-agent research system*（2025-06）— https://www.anthropic.com/engineering/multi-agent-research-system
10. Armin Ronacher, *Pi*（2026-01）— https://lucumr.pocoo.org/2026/1/31/pi/
11. Pragmatic Engineer, *How Claude Code is built*（2025-09）— https://newsletter.pragmaticengineer.com/p/how-claude-code-is-built
12. Anthropic, *Claude Code sandboxing*（2025-10）— https://www.anthropic.com/engineering/claude-code-sandboxing
13. Chroma, *Context Rot*（2025-07）— https://www.trychroma.com/research/context-rot

**基准与生态**
- Terminal-Bench 2.0 — https://www.tbench.ai/ · SWE-bench Verified · MCP — https://modelcontextprotocol.io/
- GAIA 基准（通用助手评测）— Meta + HuggingFace, 2023
- 框架官方文档：Claude Agent SDK（code.claude.com/docs）· OpenAI Agents SDK · LangGraph · smolagents · PydanticAI · Vercel AI SDK · Google ADK

**第 12 章延伸样本**
- rust-ai-agent（教学）— https://github.com/solenovex/rust-ai-agent · B 站《用 Rust 构建 AI Agent》/ UP 主「软件工艺师」
- pi_agent_rust（对标 pi 的 Rust coding agent）— https://github.com/Dicklesworthstone/pi_agent_rust
- Rust 原生 agent 框架：Rig · AutoAgents · OpenFANG

**本目录**
- `sources/pi-architecture-notes.md` — pi 代码级分析（英文，含 file:line 出处）
- `sources/tau-architecture-notes.md` — tau 代码级分析（英文，含 file:line 出处）
- `sources/best-practices-research.md` — 最佳实践调研原始笔记（英文，25+ 来源全链接）
