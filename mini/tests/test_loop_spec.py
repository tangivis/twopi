"""M3 循环规格测试 —— 这个文件就是 run_agent_loop 的验收契约。

启用方式：
    MINI_MILESTONE=3 uv run pytest tests/test_loop_spec.py -v

默认跳过，所以 check.sh 在你动手前保持全绿；实现循环时把它当规格书逐条攻克。
契约的精确定义都写在各测试的断言里——先读完再动手（指南 9.4）。
"""

import os

import pytest

from mini_agent.messages import (
    AssistantMessage,
    ToolCall,
    ToolResultMessage,
    UserMessage,
)
from mini_agent.tools import AgentTool, AgentToolResult
from mini_ai.events import (
    ProviderEvent,
    ProviderResponseEndEvent,
    ProviderResponseStartEvent,
    ProviderTextDeltaEvent,
)
from mini_ai.fake import FakeProvider

MILESTONE = int(os.environ.get("MINI_MILESTONE", "1"))
pytestmark = [
    pytest.mark.anyio,
    pytest.mark.skipif(MILESTONE < 3, reason="设 MINI_MILESTONE=3 启用 M3 循环规格测试"),
]


def text_script(text: str) -> list[ProviderEvent]:
    """一段纯文本响应：start → 每字符一个 delta → end。"""
    deltas: list[ProviderEvent] = [ProviderTextDeltaEvent(delta=ch) for ch in text]
    return [
        ProviderResponseStartEvent(),
        *deltas,
        ProviderResponseEndEvent(message=AssistantMessage(content=text)),
    ]


def toolcall_script(
    call: ToolCall, *, finish_reason: str = "tool_use", content: str = ""
) -> list[ProviderEvent]:
    """一段以工具调用收尾的响应。"""
    message = AssistantMessage.model_validate(
        {"content": content, "tool_calls": [call.model_dump()], "finish_reason": finish_reason}
    )
    return [ProviderResponseStartEvent(), ProviderResponseEndEvent(message=message)]


class EchoRecorder:
    """echo 工具：记录执行次数，返回 'echo:<text>'。"""

    def __init__(self) -> None:
        self.executed = 0

    async def __call__(self, call: ToolCall) -> AgentToolResult:
        self.executed += 1
        return AgentToolResult(content=f"echo:{call.arguments.get('text', '')}")


def echo_tool(executor: EchoRecorder) -> AgentTool:
    return AgentTool(
        name="echo",
        description="Echo the given text back.",
        input_schema={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        executor=executor,
    )


async def run(provider: FakeProvider, tools: list[AgentTool], prompt: str = "go"):
    from mini_agent.loop import run_agent_loop

    messages = [UserMessage(content=prompt)]
    events = [
        e
        async for e in run_agent_loop(
            provider=provider, model="m", system="s", messages=messages, tools=tools
        )
    ]
    return events, messages


# ── 契约 1：纯文本回合的精确事件序列 ─────────────────────────────────────


async def test_text_only_event_sequence() -> None:
    fake = FakeProvider(scripts=[text_script("ok")])
    events, messages = await run(fake, tools=[])
    assert [e.type for e in events] == [
        "agent_start",
        "turn_start",
        "message_start",
        "message_delta",
        "message_delta",
        "message_end",
        "turn_end",
        "agent_end",
    ]
    # 循环把 assistant 消息 append 进了调用者的 messages（调用者拥有 transcript）
    assert [m.role for m in messages] == ["user", "assistant"]
    assert isinstance(messages[-1], AssistantMessage) and messages[-1].content == "ok"


# ── 契约 2：工具回合 —— 执行、回填、进入下一轮 ───────────────────────────


async def test_tool_round_trip() -> None:
    recorder = EchoRecorder()
    call = ToolCall(id="c1", name="echo", arguments={"text": "hi"})
    fake = FakeProvider(scripts=[toolcall_script(call), text_script("done")])
    events, messages = await run(fake, tools=[echo_tool(recorder)])

    assert recorder.executed == 1
    types = [e.type for e in events]
    # 工具事件成对出现，且第二轮真实发生
    assert types.count("tool_execution_start") == 1
    assert types.count("tool_execution_end") == 1
    assert types.count("turn_start") == 2
    assert types[0] == "agent_start" and types[-1] == "agent_end"
    # transcript 顺序：user → assistant(带调用) → tool 结果 → assistant
    assert [m.role for m in messages] == ["user", "assistant", "tool", "assistant"]
    tool_msg = messages[2]
    assert isinstance(tool_msg, ToolResultMessage)
    assert tool_msg.tool_call_id == "c1" and tool_msg.ok and tool_msg.content == "echo:hi"
    # 第二次 LLM 调用必须能"看见"工具结果（铁律之一：transcript 始终合法）
    assert any(
        isinstance(m, ToolResultMessage) and m.tool_call_id == "c1"
        for m in fake.calls[1]["messages"]
    )


# ── 契约 3（守卫①）：截断的工具调用绝不执行 ─────────────────────────────


async def test_truncation_guard_never_executes() -> None:
    recorder = EchoRecorder()
    call = ToolCall(id="c1", name="echo", arguments={"text": "hi"})
    fake = FakeProvider(
        scripts=[toolcall_script(call, finish_reason="length"), text_script("recovered")]
    )
    events, messages = await run(fake, tools=[echo_tool(recorder)])

    assert recorder.executed == 0, "finish_reason=length 时参数可能不完整，绝不执行"
    failed = [m for m in messages if isinstance(m, ToolResultMessage)]
    assert len(failed) == 1 and failed[0].ok is False and failed[0].tool_call_id == "c1"
    assert [e.type for e in events][-1] == "agent_end"


# ── 契约 4（守卫②）：未知工具名 → 失败结果，不许崩溃 ─────────────────────


async def test_unknown_tool_yields_failure_result() -> None:
    call = ToolCall(id="c1", name="does_not_exist", arguments={})
    fake = FakeProvider(scripts=[toolcall_script(call), text_script("done")])
    events, messages = await run(fake, tools=[])

    failed = [m for m in messages if isinstance(m, ToolResultMessage)]
    assert len(failed) == 1 and failed[0].ok is False
    assert [e.type for e in events][-1] == "agent_end"


# ── 契约 5（守卫③）：executor 异常 → ok=False 结果，循环继续 ─────────────


class Exploder:
    async def __call__(self, call: ToolCall) -> AgentToolResult:
        raise ValueError("boom")


async def test_tool_exception_becomes_failure_result() -> None:
    call = ToolCall(id="c1", name="echo", arguments={"text": "hi"})
    tool = AgentTool(name="echo", description="x", input_schema={}, executor=Exploder())
    fake = FakeProvider(scripts=[toolcall_script(call), text_script("done")])
    events, messages = await run(fake, tools=[tool])

    failed = [m for m in messages if isinstance(m, ToolResultMessage)]
    assert len(failed) == 1 and failed[0].ok is False
    assert "boom" in failed[0].content, "异常文本要进 content——错误属于模型的输入（铁律之五）"
    assert [e.type for e in events][-1] == "agent_end"
