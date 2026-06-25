"""团队配置与智能体定义数据模型。

支持用户自定义智能体团队。
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4


@dataclass
class AgentConfig:
    """单个智能体的配置定义。
        在 UI 中自由编辑这些字段，定义每个智能体的行为和能力。
    """
    # 标识
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""                              # 名称
    role: str = "executor"                      # executor | coordinator | reviewer | specialist
    capabilities: List[str] = field(default_factory=list)  # 能力标签列表

    # LLM 配置
    system_prompt: str = ""                     # 完整系统提示词（用户可编辑）
    model: str = ""                             # 使用的LLM模型，空=使用默认
    max_tokens: int = 4096                      # 最大输出token

    # 行为控制
    require_plan_approval: bool = False         # 是否需要人工审批计划才能执行
    allow_fork: bool = False                    # 是否允许fork子智能体
    fork_limit: int = 3                         # 最多fork数量
    tools_allowlist: List[str] = field(default_factory=list)  # 可用工具（空=全部可用）

    # 团队角色
    is_leader: bool = False                     # 是否是团队Leader，对接用户
    can_publish_tasks: bool = False             # 能否向任务池发布新任务
    # Leader自动获得publish权限，在TeamConfig验证时强制设置

    # 关系
    parent_agent_id: Optional[str] = None       # 如果是fork出来的，指向父智能体ID

    # 扩展
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role,
            "capabilities": self.capabilities,
            "system_prompt": self.system_prompt,
            "model": self.model,
            "max_tokens": self.max_tokens,
            "require_plan_approval": self.require_plan_approval,
            "allow_fork": self.allow_fork,
            "fork_limit": self.fork_limit,
            "tools_allowlist": self.tools_allowlist,
            "is_leader": self.is_leader,
            "can_publish_tasks": self.can_publish_tasks,
            "parent_agent_id": self.parent_agent_id,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AgentConfig":
        return cls(
            id=data.get("id", str(uuid4())),
            name=data.get("name", ""),
            role=data.get("role", "executor"),
            capabilities=data.get("capabilities", []),
            system_prompt=data.get("system_prompt", ""),
            model=data.get("model", ""),
            max_tokens=data.get("max_tokens", 4096),
            require_plan_approval=data.get("require_plan_approval", False),
            allow_fork=data.get("allow_fork", False),
            fork_limit=data.get("fork_limit", 3),
            tools_allowlist=data.get("tools_allowlist", []),
            is_leader=data.get("is_leader", False),
            can_publish_tasks=data.get("can_publish_tasks", False),
            parent_agent_id=data.get("parent_agent_id"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class TeamConfig:
    """团队配置，智能体的定义和通信规则。可保存为模板以便复用。
    """
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""                              # 团队名称
    description: str = ""                       # 描述
    agents: List[AgentConfig] = field(default_factory=list)  # 智能体列表
    leader_agent_id: str = ""                   # Leader智能体ID（用户接口人）
    communication_rules: dict = field(default_factory=dict)   # 通信规则
    fork_policy: dict = field(default_factory=dict)           # Fork策略
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "agents": [a.to_dict() for a in self.agents],
            "leader_agent_id": self.leader_agent_id,
            "communication_rules": self.communication_rules,
            "fork_policy": self.fork_policy,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TeamConfig":
        agents_data = data.get("agents", [])
        agents = [AgentConfig.from_dict(a) for a in agents_data]
        return cls(
            id=data.get("id", str(uuid4())),
            name=data.get("name", ""),
            description=data.get("description", ""),
            agents=agents,
            leader_agent_id=data.get("leader_agent_id", ""),
            communication_rules=data.get("communication_rules", {}),
            fork_policy=data.get("fork_policy", {}),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            updated_at=data.get("updated_at", datetime.now(timezone.utc).isoformat()),
        )

    def add_agent(self, agent: AgentConfig) -> None:
        """添加智能体到团队。"""
        self.agents.append(agent)

    def remove_agent(self, agent_id: str) -> bool:
        """从团队中移除智能体。"""
        for i, a in enumerate(self.agents):
            if a.id == agent_id:
                del self.agents[i]
                return True
        return False

    def get_agent(self, agent_id: str) -> Optional[AgentConfig]:
        """按 ID 获取智能体。"""
        for a in self.agents:
            if a.id == agent_id:
                return a
        return None
