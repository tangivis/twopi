"""AgentEvent：前端唯一契约（第 9 章 M1，✅ 参考实现）。

铁律之二：前端（print 渲染器、未来的 TUI、你的 Web UI）只消费这里的事件，
不碰 harness 内部状态。事件够用就好——先 10 种，缺了再加。
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from mini_agent.messages import AgentMessage, ToolCall
from mini_agent.tools import AgentToolResult


class _Ev(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AgentStartEvent(_Ev):
    type: Literal["agent_start"] = "agent_start"


class AgentEndEvent(_Ev):
    type: Literal["agent_end"] = "agent_end"


class TurnStartEvent(_Ev):
    type: Literal["turn_start"] = "turn_start"
    turn: int


class TurnEndEvent(_Ev):
    type: Literal["turn_end"] = "turn_end"
    turn: int


class MessageStartEvent(_Ev):
    type: Literal["message_start"] = "message_start"
    role: Literal["user", "assistant"]


class MessageDeltaEvent(_Ev):
    type: Literal["message_delta"] = "message_delta"
    delta: str


class MessageEndEvent(_Ev):
    type: Literal["message_end"] = "message_end"
    message: AgentMessage


class ToolExecutionStartEvent(_Ev):
    type: Literal["tool_execution_start"] = "tool_execution_start"
    tool_call: ToolCall


class ToolExecutionEndEvent(_Ev):
    type: Literal["tool_execution_end"] = "tool_execution_end"
    tool_call_id: str
    result: AgentToolResult


class ErrorEvent(_Ev):
    type: Literal["error"] = "error"
    message: str
    recoverable: bool = False


type AgentEvent = (
    AgentStartEvent
    | AgentEndEvent
    | TurnStartEvent
    | TurnEndEvent
    | MessageStartEvent
    | MessageDeltaEvent
    | MessageEndEvent
    | ToolExecutionStartEvent
    | ToolExecutionEndEvent
    | ErrorEvent
)
