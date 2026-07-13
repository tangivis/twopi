"""FakeProvider 自检：脚本回放 + 请求记录（它是后续一切测试的地基）。"""

import pytest

from mini_agent.messages import AssistantMessage, UserMessage
from mini_ai.events import (
    ProviderResponseEndEvent,
    ProviderResponseStartEvent,
    ProviderTextDeltaEvent,
)
from mini_ai.fake import FakeProvider

pytestmark = pytest.mark.anyio


async def test_fake_replays_script_and_records_calls() -> None:
    script = [
        ProviderResponseStartEvent(),
        ProviderTextDeltaEvent(delta="hi"),
        ProviderResponseEndEvent(message=AssistantMessage(content="hi")),
    ]
    fake = FakeProvider(scripts=[script])
    events = [
        e
        async for e in fake.stream_response(
            model="m", system="s", messages=[UserMessage(content="hello")], tools=[]
        )
    ]
    assert [e.type for e in events] == ["response_start", "text_delta", "response_end"]
    assert len(fake.calls) == 1
    assert fake.calls[0]["model"] == "m"
    assert fake.calls[0]["tools"] == []


async def test_fake_raises_when_script_exhausted() -> None:
    fake = FakeProvider(scripts=[])
    with pytest.raises(AssertionError, match="脚本"):
        async for _ in fake.stream_response(model="m", system="s", messages=[], tools=[]):
            pass
