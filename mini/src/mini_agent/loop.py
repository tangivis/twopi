"""run_agent_loop —— 你的 M3 练习：全项目最重要的 ~130 行。

┌─ 练习说明 ────────────────────────────────────────────────────────┐
│ 规格测试就是你的验收标准：                                          │
│     MINI_MILESTONE=3 uv run pytest tests/test_loop_spec.py -v      │
│ 全绿 = 通关。测试的 docstring 定义了精确契约，先读测试再动手。        │
│ 对照答案：tau 的 src/tau_agent/loop.py（276 行）；                   │
│ 卡住超过 2 小时再看 solutions/m3_loop.py。                          │
└──────────────────────────────────────────────────────────────────┘

实现步骤（指南 9.4 的骨架，逐条对应）：
1. yield AgentStartEvent()；turn = 0；进入 while（max_turns=None 表示无上限）。
2. 每轮：若 signal.is_cancelled() → ErrorEvent(recoverable=True) 后 break；
   yield TurnStartEvent(turn)。
3. 迭代 provider.stream_response(...)，把 ProviderEvent 1:1 翻译成 AgentEvent：
   response_start→MessageStartEvent(role="assistant")；text_delta→MessageDeltaEvent；
   response_end→把 AssistantMessage append 进 messages + MessageEndEvent；
   error→ErrorEvent(recoverable=False)。tool_call 事件可忽略（完整调用已在
   response_end 的消息里）。
4. 流结束却没有 assistant 消息 → TurnEndEvent + ErrorEvent 后 break。
5. 四大守卫（规格测试逐一验收）：
   ① 截断守卫：finish_reason=="length" 时**不执行任何工具调用**，
      为每个 tool_call 直接 append 一条 ok=False 的 ToolResultMessage；
   ② 未知工具：模型幻觉出的工具名 → ok=False 结果，不许 KeyError；
   ③ 异常边界：executor 抛异常 → 捕获转 ok=False 结果（把异常文本放进
      content），循环继续；
   ④ 取消补齐：中途取消 → 剩余 tool_call 补合成 "cancelled" 结果，
      保证 transcript 里每个 tool_call 都有 tool_result（铁律之一）。
6. 工具串行执行：每个调用 yield ToolExecutionStartEvent → 执行 →
   append ToolResultMessage → yield ToolExecutionEndEvent。
7. 没有工具调用时：TurnEndEvent → 先 drain_steering() 再 drain_follow_up()，
   把排到的消息 append 为 UserMessage 并经 MessageStart/End(role="user") 回显，
   有消息则继续循环，否则 break。
8. 有工具调用时：批次结束后 TurnEndEvent → 只 drain_steering() → turn += 1。
9. 循环退出后 yield AgentEndEvent()（无论哪条路径，最后一定发它）。
"""

from collections.abc import AsyncIterator, Callable

from mini_agent.events import AgentEvent
from mini_agent.messages import AgentMessage
from mini_agent.tools import AgentTool
from mini_ai.provider import CancellationToken, ModelProvider


async def run_agent_loop(
    *,
    provider: ModelProvider,
    model: str,
    system: str,
    messages: list[AgentMessage],
    tools: list[AgentTool],
    drain_steering: Callable[[], list[str]] | None = None,
    drain_follow_up: Callable[[], list[str]] | None = None,
    signal: CancellationToken | None = None,
    max_turns: int | None = None,
) -> AsyncIterator[AgentEvent]:
    """纯 async generator：无状态，调用者拥有 messages，本函数只向里 append。"""
    # TODO(M3): 按模块 docstring 的 9 个步骤实现。
    raise NotImplementedError("M3 练习：实现 agent 循环（先读 tests/test_loop_spec.py）")
    yield  # pragma: no cover —— 使本函数成为 async generator，保持调用方语义
