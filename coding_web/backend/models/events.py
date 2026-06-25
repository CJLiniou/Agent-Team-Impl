from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class EventType(str, Enum):
    """事件类型枚举。"""
    SNAPSHOT = "snapshot"
    AGENT_STATE_CHANGED = "agent_state_changed"
    AGENT_STEP = "agent_step"
    TASK_STATUS_CHANGED = "task_status_changed"
    MESSAGE_SENT = "message_sent"
    TOOL_CALL = "tool_call"
    SANDBOX_FILE_CHANGED = "sandbox_file_changed"
    LOG_ENTRY = "log_entry"
    RUN_COMPLETED = "run_completed"
    ERROR = "error"
    INTERVENTION_RECEIVED = "intervention_received"
    AGENT_FORKED = "agent_forked"
    TASK_PAUSED = "task_paused"
    TASK_RESUMED = "task_resumed"


# ── Agent 快照（用于 snapshot 事件）──────────────────────────

@dataclass
class AgentSnapshot:
    id: str
    name: str
    role: str
    state: str          # idle | busy | waiting | error
    current_task_id: str = ""
    current_action: str = ""
    completed_tasks: int = 0
    failed_tasks: int = 0
    error_message: str = ""
    parent_agent_name: str = ""  # 如果是 fork 出来的，父智能体名称
    allow_fork: bool = False     # 是否允许 fork


# ── Task 快照（用于 snapshot 事件）───────────────────────────

@dataclass
class TaskSnapshot:
    id: str
    name: str
    description: str
    status: str         # pending | in_progress | completed | failed | blocked
    assigned_to: str = ""
    priority: int = 0
    result: str = ""


# ── 事件数据结构 ─────────────────────────────────────────────

@dataclass
class ServerEvent:
    """服务端推送到客户端的 WebSocket 消息。"""
    type: str                                     # EventType 值
    task_id: str                                  # 所属编码任务 ID
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "taskId": self.task_id,
            "timestamp": self.timestamp,
            "data": self.data,
        }


# ── 事件工厂函数 ────────────────────────────────────────────

def make_snapshot_event(
    task_id: str,
    agents: list[AgentSnapshot],
    tasks: list[TaskSnapshot],
    messages: list[dict],
    logs: list[dict],
) -> ServerEvent:
    return ServerEvent(
        type=EventType.SNAPSHOT.value,
        task_id=task_id,
        data={
            "agents": [a.__dict__ for a in agents],
            "tasks": [t.__dict__ for t in tasks],
            "messages": messages,
            "logs": logs,
        },
    )


def make_agent_state_event(task_id: str, agent: AgentSnapshot) -> ServerEvent:
    return ServerEvent(
        type=EventType.AGENT_STATE_CHANGED.value,
        task_id=task_id,
        data={"agent": agent.__dict__},
    )


def make_agent_step_event(task_id: str, name: str, action: str) -> ServerEvent:
    return ServerEvent(
        type=EventType.AGENT_STEP.value,
        task_id=task_id,
        data={"name": name, "action": action},
    )


def make_task_status_event(task_id: str, task: TaskSnapshot) -> ServerEvent:
    return ServerEvent(
        type=EventType.TASK_STATUS_CHANGED.value,
        task_id=task_id,
        data={"task": task.__dict__},
    )


def make_message_event(task_id: str, msg: dict) -> ServerEvent:
    return ServerEvent(
        type=EventType.MESSAGE_SENT.value,
        task_id=task_id,
        data={"message": msg},
    )


def make_tool_call_event(
    task_id: str, name: str, tool: str, args: dict, result: str = ""
) -> ServerEvent:
    return ServerEvent(
        type=EventType.TOOL_CALL.value,
        task_id=task_id,
        data={
            "name": name,
            "tool": tool,
            "args": args,
            "result": result,
        },
    )


def make_sandbox_file_event(task_id: str, path: str, action: str) -> ServerEvent:
    return ServerEvent(
        type=EventType.SANDBOX_FILE_CHANGED.value,
        task_id=task_id,
        data={"path": path, "action": action},
    )


def make_log_event(task_id: str, level: str, message: str, name: str = "") -> ServerEvent:
    return ServerEvent(
        type=EventType.LOG_ENTRY.value,
        task_id=task_id,
        data={"level": level, "message": message, "name": name},
    )


def make_run_completed_event(
    task_id: str, status: str, result: str = "", stats: Optional[dict] = None
) -> ServerEvent:
    return ServerEvent(
        type=EventType.RUN_COMPLETED.value,
        task_id=task_id,
        data={"status": status, "result": result, "stats": stats or {}},
    )


def make_error_event(task_id: str, error: str, source: str = "") -> ServerEvent:
    return ServerEvent(
        type=EventType.ERROR.value,
        task_id=task_id,
        data={"error": error, "source": source},
    )
