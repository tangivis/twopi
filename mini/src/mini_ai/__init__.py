"""mini_ai —— Provider 层：把各厂商私有协议翻译成中立事件流。

规则：本包不许 import mini_app。中立数据模型（messages/tools）住在 mini_agent，
本包只 import 它的子模块来做适配（tau 的同款布局，见指南第 3 章的"放法"讨论）。

约定：一律从子模块导入，本 __init__ 不做 re-export（避免包级 import 环）。
"""
