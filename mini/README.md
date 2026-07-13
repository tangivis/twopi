# mini —— 从零复刻 agent harness 的练习工程

配套《pi-vs-tau 架构对比学习指南》**第 9 章「从零复刻」**。M0/M1 已完成，从 M2 开始是你的练习——每个里程碑都有验收测试，全绿才进下一关。

## 快速开始

```bash
cd agent-study/mini
uv sync            # 安装依赖（含 dev 组）
./check.sh         # lint + mypy strict + pytest 三连，开箱即绿
```

## 现状地图

| 里程碑 | 状态 | 文件 | 验收 |
|---|---|---|---|
| M0 骨架 + 依赖方向守卫 | ✅ 已完成 | `pyproject.toml`、`tests/test_boundaries.py` | `./check.sh` 全绿 |
| M1 核心类型 | ✅ 参考实现 | `mini_agent/messages.py` `tools.py` `events.py` | `tests/test_types.py` |
| M2 Provider 层 | ✅ Protocol/事件/Fake 已提供；**真适配器是练习** | 练习：`mini_ai/openai_compatible.py`（TODO 骨架 + 要点清单） | `uv run python scripts/smoke_provider.py`（本地 Ollama 或任意 OpenAI 兼容端点） |
| M3 循环 | 🔧 **练习** | `mini_agent/loop.py`（9 步 TODO） | `MINI_MILESTONE=3 uv run pytest tests/test_loop_spec.py -v` 全绿 |
| M4–M9 | ⬜ 你的地盘 | `mini_app/`（模块清单见其 `__init__.py`） | 按指南 9.5–9.10 的验收清单**自己写测试**（写测试本身就是练习） |

## 玩法规则

1. **先读规格测试再写代码**：`tests/test_loop_spec.py` 的断言就是循环的精确契约。
2. **里程碑机制**：未来里程碑的规格测试默认跳过（不弄红你的 `check.sh`）；
   动手时用 `MINI_MILESTONE=3` 启用，全绿即通关，然后 `git tag m3`。
3. **测试永不打真 API**：一切用 `mini_ai/fake.py` 的 FakeProvider（pi/tau 共同实践）；
   真模型只用 `scripts/smoke_provider.py` 手动冒烟。
4. **卡住超过 2 小时**：先对照 tau 的答案纸（`tau/src/tau_agent/loop.py`，276 行），
   还不行再看 `solutions/`（有剧透警告）。
5. 五条铁律贴在 `mini_agent/__init__.py` 和指南 9.0——违反任何一条，后面都会返工。

## 与两个参考项目的对照

| mini | tau（Python 教学版） | pi（TS 生产版） |
|---|---|---|
| `mini_ai/` | `src/tau_ai/` | `packages/ai/` |
| `mini_agent/` | `src/tau_agent/` | `packages/agent/` |
| `mini_app/` | `src/tau_coding/` | `packages/coding-agent/` |
