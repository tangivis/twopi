"""mini_agent —— 可移植的大脑层。

规则（第 9 章 M0 的五条铁律之二）：本包不许 import mini_app、不许出现 print、
不许知道终端/配置路径的存在。前端只消费 events.py 里的 AgentEvent。

约定：一律从子模块导入（from mini_agent.messages import ...），
不要在本 __init__ 里做 re-export——避免与 mini_ai 的类型引用形成包级 import 环。
"""
