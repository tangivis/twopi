"""ProviderEvent：provider 适配器的统一输出词汇（第 9 章 M2，✅ 提供）。

简化取舍（tau 式）：ToolCall 事件携带**完整**工具调用，不向消费者流式输出
参数增量——适配器内部自己攒分片 JSON，攒齐了再发一个事件。
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from mini_agent.messages import AssistantMessage, ToolCall


class _Ev(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProviderResponseStartEvent(_Ev):
    type: Literal["response_start"] = "response_start"


class ProviderTextDeltaEvent(_Ev):
    type: Literal["text_delta"] = "text_delta"
    delta: str


class ProviderToolCallEvent(_Ev):
    type: Literal["tool_call"] = "tool_call"
    tool_call: ToolCall


class ProviderResponseEndEvent(_Ev):
    type: Literal["response_end"] = "response_end"
    message: AssistantMessage


class ProviderRetryEvent(_Ev):
    type: Literal["retry"] = "retry"
    attempt: int
    delay_seconds: float
    reason: str


class ProviderErrorEvent(_Ev):
    type: Literal["error"] = "error"
    message: str


type ProviderEvent = (
    ProviderResponseStartEvent
    | ProviderTextDeltaEvent
    | ProviderToolCallEvent
    | ProviderResponseEndEvent
    | ProviderRetryEvent
    | ProviderErrorEvent
)
