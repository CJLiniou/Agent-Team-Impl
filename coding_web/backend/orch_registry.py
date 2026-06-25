"""Orchestrator 注册表 — 独立模块，避免循环导入。

供 WebSocket snapshot 直接读取 orchestrator 实时状态。
"""

_orchestrators: dict[str, object] = {}


def register(task_id: str, orchestrator) -> None:
    _orchestrators[task_id] = orchestrator


def unregister(task_id: str) -> None:
    _orchestrators.pop(task_id, None)


def get(task_id: str):
    return _orchestrators.get(task_id)
