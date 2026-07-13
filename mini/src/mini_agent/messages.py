"""中立消息模型：整个 harness 只有这一份消息类型（第 9 章 M1，✅ 参考实现）。

设计取舍（对照指南 4.1 / 9.2）：
- content 先用纯字符串（tau 式简化）；图片等二进制放 ToolResultMessage.data。
- extra="forbid"：脏字段第一时间炸出来，而不是默默丢掉。
- finish_reason 收敛为 5 种——provider 适配器负责把各家叫法翻译成这 5 种。
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class UserMessage(_Strict):
    role: Literal["user"] = "user"
    content: str


class ToolCall(_Strict):
    id: str
    name: str
    arguments: dict[str, Any]


class AssistantMessage(_Strict):
    role: Literal["assistant"] = "assistant"
    content: str = ""
    tool_calls: list[ToolCall] = []
    finish_reason: Literal["stop", "tool_use", "length", "error", "aborted"] = "stop"


class ToolResultMessage(_Strict):
    role: Literal["tool"] = "tool"
    tool_call_id: str
    name: str
    content: str  # 给模型看的文本
    ok: bool = True
    data: dict[str, Any] = {}  # 给 UI 看的结构化数据（diff、图片 base64……）


type AgentMessage = UserMessage | AssistantMessage | ToolResultMessage
