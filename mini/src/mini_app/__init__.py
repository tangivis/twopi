"""mini_app —— 产品层：从 M4 起这里是你的地盘。

按指南第 9 章依次落地：
- M4 tools.py：read / write / edit / bash（坑最密集的一站，验收清单见 9.5）
- M5 harness.py：AgentHarness——双队列、取消、transcript 修复
- M6 system_prompt.py：机械拼装（日期放末尾！）
- M7 session/：JSONL 追加式条目树 + resume
- M8 cli.py：print 模式——用它修一个真 bug
- M9 compaction：压缩与溢出恢复

本包可以 import mini_agent 与 mini_ai；反方向被 tests/test_boundaries.py 禁止。
"""
