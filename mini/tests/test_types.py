"""M1 核心类型验收：round-trip 序列化 + extra="forbid" 生效（指南 9.2）。"""

import pytest
from pydantic import TypeAdapter, ValidationError

from mini_agent.messages import (
    AgentMessage,
    AssistantMessage,
    ToolCall,
    ToolResultMessage,
    UserMessage,
)

MESSAGE_ADAPTER: TypeAdapter[AgentMessage] = TypeAdapter(AgentMessage)


def test_round_trip_each_message_type() -> None:
    samples: list[AgentMessage] = [
        UserMessage(content="fix the failing test"),
        AssistantMessage(
            content="running tests",
            tool_calls=[ToolCall(id="c1", name="bash", arguments={"command": "pytest -q"})],
            finish_reason="tool_use",
        ),
        ToolResultMessage(
            tool_call_id="c1", name="bash", content="1 failed", ok=False, data={"exit_code": 1}
        ),
    ]
    for message in samples:
        dumped = message.model_dump_json()
        restored = MESSAGE_ADAPTER.validate_json(dumped)
        assert restored == message


def test_extra_fields_rejected() -> None:
    with pytest.raises(ValidationError):
        UserMessage(content="hi", secret="nope")  # type: ignore[call-arg]


def test_assistant_defaults() -> None:
    message = AssistantMessage()
    assert message.content == ""
    assert message.tool_calls == []
    assert message.finish_reason == "stop"
