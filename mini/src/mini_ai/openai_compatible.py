"""OpenAICompatibleProvider —— 你的 M2 练习：一个适配器吃遍 90% 的模型。

┌─ 练习说明（对照指南 9.3 与 10.2）────────────────────────────────────┐
│ 目标：实现 /v1/chat/completions 的流式适配器，把 OpenAI wire 格式    │
│ 翻译成 mini_ai.events 里的 6 种 ProviderEvent。                      │
│ 完成后：uv run python scripts/smoke_provider.py 手动冒烟             │
│ （云端 key 或本地 Ollama: base_url=http://localhost:11434/v1）       │
│ 参考答案：tau 的 src/tau_ai/openai_compatible.py（先自己写！）        │
└──────────────────────────────────────────────────────────────────┘

实现要点（全部来自指南 9.3 的清单）：
1. 请求体：{"model", "messages", "tools", "stream": true}
   - 消息翻译：UserMessage→{role:"user"}；AssistantMessage→{role:"assistant",
     tool_calls:[{id, type:"function", function:{name, arguments: JSON字符串}}]}；
     ToolResultMessage→{role:"tool", tool_call_id, content}；system 放 messages[0]。
   - 工具翻译：AgentTool→{type:"function", function:{name, description,
     parameters: input_schema}}。
2. SSE 解析：按行读（httpx 的 aiter_lines），只认 "data: " 前缀，
   "data: [DONE]" 收尾；每行剩余部分是一个 JSON chunk。
3. 增量组装：chunk["choices"][0]["delta"] 里 content 是文本增量（发
   ProviderTextDeltaEvent）；tool_calls 是参数分片（按 index 攒 name/arguments
   字符串，流结束后 json.loads，攒齐发 ProviderToolCallEvent）。
4. finish_reason 映射：stop→"stop"，tool_calls→"tool_use"，length→"length"。
   最后发 ProviderResponseEndEvent(message=攒好的 AssistantMessage)。
5. 铁律之四：**永不 throw**——网络错误/HTTP 4xx/5xx 全部 yield
   ProviderErrorEvent(message=...) 后 return。
6. 重试：只在"尚未产出任何事件"时重试网络错误与 408/429/5xx，
   指数退避 min(max_delay, 0.25 * 2**attempt)，先 yield ProviderRetryEvent。
"""

from collections.abc import AsyncIterator

from mini_agent.messages import AgentMessage
from mini_agent.tools import AgentTool
from mini_ai.events import ProviderEvent
from mini_ai.provider import CancellationToken


class OpenAICompatibleProvider:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str = "",
        max_retries: int = 2,
        timeout_seconds: float = 120.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._max_retries = max_retries
        self._timeout_seconds = timeout_seconds

    async def stream_response(
        self,
        *,
        model: str,
        system: str,
        messages: list[AgentMessage],
        tools: list[AgentTool],
        signal: CancellationToken | None = None,
    ) -> AsyncIterator[ProviderEvent]:
        # TODO(M2): 按模块 docstring 的 6 个要点实现。
        # 提示：async with httpx.AsyncClient() ... client.stream("POST", url, ...)
        raise NotImplementedError("M2 练习：实现 OpenAI 兼容适配器（见模块 docstring）")
        yield  # pragma: no cover —— 使本函数成为 async generator，保持调用方语义
