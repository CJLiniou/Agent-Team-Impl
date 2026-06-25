"""依赖注入和全局服务引用。

将所有全局服务放在独立模块中，避免 main.py ↔ routes 循环导入。
"""

from typing import Optional

from .services.event_bridge import EventBridge
from .services.sandbox_service import SandboxService
from .services.task_service import TaskService
from .websocket.manager import ConnectionManager

# ── 全局服务实例（由 lifespan 初始化）─────────────────────

_event_bridge: Optional[EventBridge] = None
_sandbox_service: Optional[SandboxService] = None
_task_service: Optional[TaskService] = None
_ws_manager: Optional[ConnectionManager] = None


def init_services(
    event_bridge: EventBridge,
    sandbox_service: SandboxService,
    task_service: TaskService,
    ws_manager: ConnectionManager,
) -> None:
    """在 lifespan 启动时初始化所有全局服务。"""
    global _event_bridge, _sandbox_service, _task_service, _ws_manager
    _event_bridge = event_bridge
    _sandbox_service = sandbox_service
    _task_service = task_service
    _ws_manager = ws_manager


def clear_services() -> None:
    """在 lifespan 关闭时清理全局服务。"""
    global _event_bridge, _sandbox_service, _task_service, _ws_manager
    _event_bridge = None
    _sandbox_service = None
    _task_service = None
    _ws_manager = None


# ── 依赖注入函数（供路由使用）─────────────────────────────

def get_task_service() -> TaskService:
    assert _task_service is not None, "TaskService not initialized"
    return _task_service


def get_sandbox_service() -> SandboxService:
    assert _sandbox_service is not None, "SandboxService not initialized"
    return _sandbox_service


def get_event_bridge() -> EventBridge:
    assert _event_bridge is not None, "EventBridge not initialized"
    return _event_bridge


def get_ws_manager() -> ConnectionManager:
    assert _ws_manager is not None, "ConnectionManager not initialized"
    return _ws_manager


# ── Orchestrator 注册表（委托给 orch_registry 模块避免循环导入）──

from .orch_registry import register as register_orchestrator
from .orch_registry import unregister as unregister_orchestrator
from .orch_registry import get as get_orchestrator
