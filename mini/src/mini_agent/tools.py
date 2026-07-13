"""工具即普通函数 + 手写 JSON Schema（第 9 章 M1，✅ 参考实现）。

没有装饰器、没有注册框架、没有魔法——tau README 原话：
"Tools are ordinary typed functions"。

input_schema 是手写的 JSON Schema 字典而非从 pydantic 派生：
工具 schema 是给模型读的提示词，值得逐字打磨（指南 9.0 技术选型表）。
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

from mini_agent.messages import ToolCall


@dataclass(frozen=True, slots=True)
class AgentToolResult:
    content: str  # 给模型看的
    ok: bool = True
    data: dict[str, Any] = field(default_factory=dict)  # 给 UI 看的


class ToolExecutor(Protocol):
    async def __call__(self, call: ToolCall) -> AgentToolResult: ...


@dataclass(frozen=True, slots=True)
class AgentTool:
    name: str
    description: str
    input_schema: Mapping[str, Any]
    executor: ToolExecutor
    prompt_snippet: str = ""  # 它在系统提示词里的那一行（M6 用）
