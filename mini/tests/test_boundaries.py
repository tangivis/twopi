"""M0 依赖方向守卫：架构规则用测试强制执行，而不是靠自觉。

规则（指南 9.1）：mini_agent 与 mini_ai 的任何模块都不许 import mini_app。
（mini_ai ↔ mini_agent 之间允许类型引用——tau 同款布局，见指南第 3 章。）
"""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
FORBIDDEN: dict[str, set[str]] = {
    "mini_agent": {"mini_app"},
    "mini_ai": {"mini_app"},
}


def iter_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


def test_dependency_direction() -> None:
    violations: list[str] = []
    for package, banned in FORBIDDEN.items():
        for path in (SRC / package).rglob("*.py"):
            hit = iter_imports(path) & banned
            if hit:
                violations.append(f"{path.relative_to(SRC)} imports {sorted(hit)}")
    assert not violations, "依赖方向违规（大脑层/Provider 层不许知道产品层）：\n" + "\n".join(
        violations
    )
