"""⚠️ 剧透警告：M3 循环的参考实现。

先自己写！卡住超过 2 小时、且对照过 tau 的 src/tau_agent/loop.py 之后再看。
验证方式：把本文件内容复制到 src/mini_agent/loop.py，然后
    MINI_MILESTONE=3 uv run pytest tests/test_loop_spec.py -v
（本参考实现已通过全部 5 条规格测试。）
"""

from collections.abc import AsyncIterator, Callable

from mini_agent.events import (
    AgentEndEvent,
    AgentEvent,
    AgentStartEvent,
    ErrorEvent,
    MessageDeltaEvent,
    MessageEndEvent,
    MessageStartEvent,
    ToolExecutionEndEvent,
    ToolExecutionStartEvent,
    TurnEndEvent,
    TurnStartEvent,
)
from mini_agent.messages import (
    AgentMessage,
    AssistantMessage,
    ToolResultMessage,
    UserMessage,
)
from mini_agent.tools import AgentTool, AgentToolResult
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
    yield AgentStartEvent()
    tool_map = {tool.name: tool for tool in tools}
    turn = 0
    while max_turns is None or turn < max_turns:
        # 守卫④（一半）：轮与轮之间检查取消
        if signal is not None and signal.is_cancelled():
            yield ErrorEvent(message="Agent run cancelled", recoverable=True)
            break

        yield TurnStartEvent(turn=turn)

        # ── 步骤 3：流式请求，provider 事件 1:1 翻译 ────────────────────
        assistant: AssistantMessage | None = None
        provider_errored = False
        async for pe in provider.stream_response(
            model=model, system=system, messages=messages, tools=tools, signal=signal
        ):
            if pe.type == "response_start":
                yield MessageStartEvent(role="assistant")
            elif pe.type == "text_delta":
                yield MessageDeltaEvent(delta=pe.delta)
            elif pe.type == "response_end":
                assistant = pe.message
                messages.append(assistant)
                yield MessageEndEvent(message=assistant)
            elif pe.type == "error":
                provider_errored = True
                yield ErrorEvent(message=pe.message, recoverable=False)
            # "tool_call" / "retry" 事件：完整调用已在 response_end 消息里；重试仅供 UI 展示

        # ── 步骤 4：流断了却没有消息 ───────────────────────────────────
        if assistant is None:
            yield TurnEndEvent(turn=turn)
            if not provider_errored:
                yield ErrorEvent(
                    message="Provider stream ended without an assistant message",
                    recoverable=False,
                )
            break

        if assistant.finish_reason == "length" and assistant.tool_calls:
            # ── 守卫①：截断的工具调用绝不执行 ──────────────────────────
            for call in assistant.tool_calls:
                messages.append(
                    ToolResultMessage(
                        tool_call_id=call.id,
                        name=call.name,
                        content=(
                            "Tool call not executed: assistant output was truncated "
                            "(finish_reason=length), so arguments may be incomplete."
                        ),
                        ok=False,
                    )
                )
        elif assistant.tool_calls:
            # ── 步骤 6：串行执行工具批次 ───────────────────────────────
            cancelled = False
            for call in assistant.tool_calls:
                yield ToolExecutionStartEvent(tool_call=call)
                if cancelled or (signal is not None and signal.is_cancelled()):
                    # 守卫④：取消后剩余调用补合成结果，保 transcript 合法
                    cancelled = True
                    result = AgentToolResult(content="Tool call cancelled", ok=False)
                else:
                    tool = tool_map.get(call.name)
                    if tool is None:
                        # 守卫②：未知工具名
                        result = AgentToolResult(content=f"Unknown tool: {call.name}", ok=False)
                    else:
                        try:
                            result = await tool.executor(call)
                        except Exception as exc:  # noqa: BLE001 —— 守卫③：工具是隔离边界
                            result = AgentToolResult(
                                content=f"Tool execution failed: {exc}", ok=False
                            )
                messages.append(
                    ToolResultMessage(
                        tool_call_id=call.id,
                        name=call.name,
                        content=result.content,
                        ok=result.ok,
                        data=dict(result.data),
                    )
                )
                yield ToolExecutionEndEvent(tool_call_id=call.id, result=result)
        else:
            # ── 步骤 7：没有工具调用 —— 排空队列或结束 ──────────────────
            yield TurnEndEvent(turn=turn)
            pending = _drain(drain_steering) or _drain(drain_follow_up)
            if not pending:
                break
            for text in pending:
                user_message = UserMessage(content=text)
                messages.append(user_message)
                yield MessageStartEvent(role="user")
                yield MessageEndEvent(message=user_message)
            turn += 1
            continue

        # ── 步骤 8：工具批次之后 —— steering 边界 ──────────────────────
        yield TurnEndEvent(turn=turn)
        for text in _drain(drain_steering):
            user_message = UserMessage(content=text)
            messages.append(user_message)
            yield MessageStartEvent(role="user")
            yield MessageEndEvent(message=user_message)
        turn += 1
    else:
        yield ErrorEvent(message=f"max_turns ({max_turns}) reached", recoverable=True)

    yield AgentEndEvent()


def _drain(drain: Callable[[], list[str]] | None) -> list[str]:
    return drain() if drain is not None else []
