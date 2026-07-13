"""M2 完成后的手动冒烟（不进测试套件——测试套件永不打真 API）。

用法：
    # 本地 Ollama
    OPENAI_BASE_URL=http://localhost:11434/v1 MINI_MODEL=qwen3:32b \
        uv run python scripts/smoke_provider.py

    # 云端 OpenAI 兼容端点
    OPENAI_BASE_URL=https://api.deepseek.com/v1 OPENAI_API_KEY=sk-... \
        MINI_MODEL=deepseek-chat uv run python scripts/smoke_provider.py
"""

import os
import sys

import anyio

from mini_agent.messages import UserMessage
from mini_ai.openai_compatible import OpenAICompatibleProvider


async def main() -> None:
    base_url = os.environ.get("OPENAI_BASE_URL", "http://localhost:11434/v1")
    provider = OpenAICompatibleProvider(
        base_url=base_url, api_key=os.environ.get("OPENAI_API_KEY", "placeholder")
    )
    model = os.environ.get("MINI_MODEL", "qwen3:32b")
    print(f"→ {base_url} / {model}", file=sys.stderr)
    async for event in provider.stream_response(
        model=model,
        system="You are a helpful assistant. Be brief.",
        messages=[UserMessage(content="Say hello in one short sentence.")],
        tools=[],
    ):
        print(event.model_dump_json())


if __name__ == "__main__":
    anyio.run(main)
