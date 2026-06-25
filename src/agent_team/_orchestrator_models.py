"""TeamOrchestrator 的数据模型 — Agent, ExecutionResult, 枚举。

从 orchestrator.py 中提取，减小主文件体积。
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from .tasks import TaskStatus


class AgentRole(str, Enum):
    """团队中的智能体角色。"""
    EXECUTOR = "executor"          # 执行任务
    COORDINATOR = "coordinator"    # 协调任务流
    REVIEWER = "reviewer"          # 审核结果
    SPECIALIST = "specialist"      # 领域专家


class AgentState(str, Enum):
    """智能体执行状态。"""
    IDLE = "idle"          # 空闲
    BUSY = "busy"          # 忙碌
    WAITING = "waiting"    # 等待
    ERROR = "error"        # 错误


@dataclass
class Agent:
    """团队中的智能体。"""
    id: str
    name: str
    role: AgentRole
    capabilities: list[str] = field(default_factory=list)
    state: AgentState = AgentState.IDLE
    current_task_id: Optional[str] = None
    last_heartbeat: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    error_message: str = ""
    completed_tasks: int = 0
    failed_tasks: int = 0
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """转换为字典。"""
        return {
            'id': self.id,
            'name': self.name,
            'role': self.role.value,
            'capabilities': self.capabilities,
            'state': self.state.value,
            'current_task_id': self.current_task_id,
            'last_heartbeat': self.last_heartbeat.isoformat(),
            'error_message': self.error_message,
            'completed_tasks': self.completed_tasks,
            'failed_tasks': self.failed_tasks,
            'metadata': self.metadata
        }


@dataclass
class ExecutionResult:
    """任务执行结果。"""
    task_id: str
    agent_id: str
    status: TaskStatus
    output: str = ""
    error: str = ""
    metadata: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        """转换为字典。"""
        return {
            'task_id': self.task_id,
            'agent_id': self.agent_id,
            'status': self.status.value,
            'output': self.output,
            'error': self.error,
            'metadata': self.metadata,
            'timestamp': self.timestamp.isoformat()
        }
