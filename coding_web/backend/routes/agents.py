"""智能体状态查询 API 路由。"""

from fastapi import APIRouter, HTTPException

from ..dependencies import get_event_bridge, get_task_service
from ..models.agent import AgentStateResponse

router = APIRouter()


@router.get("/tasks/{task_id}/agents")
async def get_task_agents(task_id: str):
    """获取指定任务的所有智能体当前状态。

    Returns:
        智能体状态列表，每个包含id、name、role、state、current_action等
    """
    service = get_task_service()
    task = service.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    bridge = get_event_bridge()
    agent_states = bridge.get_agent_states(task_id)

    # EventBridge 为空时回退到 DB 中的 run_history
    if not agent_states:
        import json
        history = json.loads(task.run_history_json or "{}")
        return history.get("agents", [])

    return [
        AgentStateResponse(
            id=a.id,
            name=a.name,
            role=a.role,
            state=a.state,
            current_task_id=a.current_task_id,
            current_action=a.current_action,
            completed_tasks=a.completed_tasks,
            failed_tasks=a.failed_tasks,
            error_message=a.error_message,
        ).__dict__
        for a in agent_states
    ]
