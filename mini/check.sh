#!/usr/bin/env bash
# 质量门三连：lint + type + test。每个里程碑结束前必须全绿（指南 9.0 节奏纪律）。
set -euo pipefail
cd "$(dirname "$0")"

uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy
uv run pytest -q

echo
echo "✅ 全绿。进入下一个里程碑前记得: git tag m<N>"
echo "   启用 M3 循环规格测试: MINI_MILESTONE=3 uv run pytest tests/test_loop_spec.py -v"
