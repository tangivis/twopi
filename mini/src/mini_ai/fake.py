"""FakeProvider：回放脚本化事件流，记录收到的请求（第 9 章 M2，✅ 提供）。

这是从现在到最后所有测试的地基——pi/tau 的共同实践：
**永远不要让测试套件打真 API**。循环/harness 的测试全部用它写。
"""

from collections.abc import AsyncIterator
from typing import Any

from mini_agent.messages import AgentMessage
from mini_agent.tools import AgentTool
from mini_ai.events import ProviderEvent
from mini_ai.provider import CancellationToken


class FakeProvider:
    """第 N 次调用回放 scripts[N]；每次调用的入参记录在 self.calls。"""

    def __init__(self, scripts: list[list[ProviderEvent]]) -> None:
        self._scripts = [list(s) for s in scripts]
        self.calls: list[dict[str, Any]] = []

    async def stream_response(
        self,
        *,
        model: str,
        system: str,
        messages: list[AgentMessage],
        tools: list[AgentTool],
        signal: CancellationToken | None = None,
    ) -> AsyncIterator[ProviderEvent]:
        self.calls.append(
            {
                "model": model,
                "system": system,
                "messages": list(messages),  # 快照：调用方随后会继续 append
                "tools": [t.name for t in tools],
            }
        )
        index = len(self.calls) - 1
        if index >= len(self._scripts):
            raise AssertionError(
                f"FakeProvider 只准备了 {len(self._scripts)} 段脚本，"
                f"却收到了第 {index + 1} 次调用——检查你的循环是否多转了一圈。"
            )
        for event in self._scripts[index]:
            yield event
