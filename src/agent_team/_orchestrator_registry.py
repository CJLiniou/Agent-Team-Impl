"""AgentRegistry — 智能体注册、查询、回调管理。

从 orchestrator.py 中提取。拥有 self._agents dict。
"""

import logging
from typing import Optional, Callable, Any

from ._orchestrator_models import Agent, AgentRole, AgentState
from .tasks import Task

logger = logging.getLogger(__name__)


class AgentRegistry:
    """管理智能体注册表：CRUD、回调注册、工作目录。"""

    def __init__(self):
        self._agents: dict[str, Agent] = {}
        self._callbacks: dict[str, Callable] = {}
        self._work_dir: str = "."

    def register(self, agent_id: str, name: str, role: AgentRole,
                 capabilities: Optional[list[str]] = None,
                 metadata: Optional[dict] = None) -> Agent:
        """注册新智能体。"""
        agent = Agent(
            id=agent_id, name=name, role=role,
            capabilities=capabilities or [], metadata=metadata or {},
        )
        self._agents[agent_id] = agent
        logger.info(f"智能体已注册: {name} ({agent_id}) - {role}")
        return agent

    def unregister(self, agent_id: str) -> bool:
        """注销智能体。"""
        if agent_id in self._agents:
            del self._agents[agent_id]
            logger.info(f"智能体已注销: {agent_id}")
            return True
        return False

    def get(self, agent_id: str) -> Optional[Agent]:
        """根据 ID 获取智能体。"""
        return self._agents.get(agent_id)

    def list(self, role: Optional[AgentRole] = None,
             state: Optional[AgentState] = None) -> list[Agent]:
        """列出智能体，支持可选过滤。"""
        agents = list(self._agents.values())
        if role:
            agents = [a for a in agents if a.role == role]
        if state:
            agents = [a for a in agents if a.state == state]
        return agents

    def set_callback(self, capability: str, callback: Callable[[Task], Any]) -> None:
        """注册执行回调。"""
        self._callbacks[capability] = callback
        logger.info(f"Execution callback registered: {capability}")

    def set_work_dir(self, path: str) -> None:
        """设置工作目录。"""
        self._work_dir = path

    def get_work_dir(self) -> str:
        """获取工作目录。"""
        return self._work_dir

    def get_stats(self, agent_id: str) -> Optional[dict]:
        """获取特定智能体的统计。"""
        agent = self._agents.get(agent_id)
        if not agent:
            return None
        total = agent.completed_tasks + agent.failed_tasks
        return {
            'id': agent.id,
            'name': agent.name,
            'role': agent.role.value,
            'state': agent.state.value,
            'completed_tasks': agent.completed_tasks,
            'failed_tasks': agent.failed_tasks,
            'success_rate': agent.completed_tasks / total if total > 0 else 0,
            'last_heartbeat': agent.last_heartbeat.isoformat()
        }

    # ── 兼容属性 ──────────────────────────────────────────────────

    @property
    def items(self):
        return self._agents.items()

    @property
    def values(self):
        return self._agents.values()

    @property
    def agents(self) -> dict:
        return self._agents

    @property
    def callbacks(self) -> dict:
        return self._callbacks
