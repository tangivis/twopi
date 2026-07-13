"""ModelProvider Protocol：循环唯一认识的 provider 形状（第 9 章 M2，✅ 提供）。

结构化类型（Protocol），无基类——任何实现了 stream_response 的对象都是 provider。
硬契约（铁律之四）：stream_response **永不 throw**，一切失败编码为流内
ProviderErrorEvent。循环因此只需要处理一种错误形状。
"""

from collections.abc import AsyncIterator
from typing import Protocol

from mini_agent.messages import AgentMessage
from mini_agent.tools import AgentTool
from mini_ai.events import ProviderEvent


class CancellationToken(Protocol):
    """协作式取消：实现方轮询 is_cancelled()，不依赖 asyncio 任务取消魔法。"""

    def is_cancelled(self) -> bool: ...


class ModelProvider(Protocol):
    def stream_response(
        self,
        *,
        model: str,
        system: str,
        messages: list[AgentMessage],
        tools: list[AgentTool],
        signal: CancellationToken | None = None,
    ) -> AsyncIterator[ProviderEvent]: ...
