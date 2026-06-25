from dataclasses import dataclass, field


@dataclass
class AgentStateResponse:
    """API 返回的智能体状态。"""
    id: str
    name: str
    role: str            # executor | coordinator | reviewer | specialist
    state: str           # idle | busy | waiting | error
    current_task_id: str = ""
    current_action: str = ""     # 当前正在做什么的描述
    completed_tasks: int = 0
    failed_tasks: int = 0
    error_message: str = ""
    last_heartbeat: str = ""

    @staticmethod
    def from_agent_dict(d: dict) -> "AgentStateResponse":
        return AgentStateResponse(
            id=d.get("id", ""),
            name=d.get("name", ""),
            role=d.get("role", ""),
            state=d.get("state", "idle"),
            current_task_id=d.get("current_task_id", ""),
            current_action=d.get("current_action", ""),
            completed_tasks=d.get("completed_tasks", 0),
            failed_tasks=d.get("failed_tasks", 0),
            error_message=d.get("error_message", ""),
            last_heartbeat=d.get("last_heartbeat", ""),
        )
