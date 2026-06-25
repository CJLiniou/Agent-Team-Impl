"""人工介入 API 路由 — 暂停/恢复/消息注入/计划审批。"""

import logging

from fastapi import APIRouter, HTTPException

from ..dependencies import get_task_service, get_event_bridge
from ..services.intervention_service import InterventionService
from .. import orch_registry

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_svc() -> InterventionService:
    ts = get_task_service()
    bridge = get_event_bridge()
    return InterventionService(ts.db, bridge, orch_registry)


@router.get("/tasks/{task_id}/interventions")
async def list_interventions(task_id: str):
    """列出任务的所有介入记录。"""
    svc = _get_svc()
    return svc.list_interventions(task_id)

@router.post("/tasks/{task_id}/intervene", status_code=201)
async def intervene(task_id: str, body: dict):
    """向运行中的智能体注入消息。

    body: {"agent_id": "...", "content": "..."}
    agent_id为空则广播给所有智能体。
    """
    agent_id = body.get("agent_id", "")
    content = body.get("content", "")
    if not content.strip():
        raise HTTPException(status_code=400, detail="介入内容不能为空")

    svc = _get_svc()
    record = await svc.inject_message(task_id, agent_id, content)
    return record.to_dict()


@router.post("/tasks/{task_id}/pause", status_code=201)
async def pause_task(task_id: str):
    """暂停任务 — 所有智能体完成当前步骤后等待。"""
    svc = _get_svc()
    record = await svc.pause(task_id)
    return record.to_dict()


@router.post("/tasks/{task_id}/resume", status_code=201)
async def resume_task(task_id: str):
    """恢复已暂停的任务。"""
    svc = _get_svc()
    record = await svc.resume(task_id)
    return record.to_dict()

@router.get("/tasks/{task_id}/plans/pending")
async def list_pending_plans(task_id: str):
    """列出所有待审批的计划。"""
    svc = _get_svc()
    return svc.get_pending_plans(task_id)


@router.post("/tasks/{task_id}/complete", status_code=201)
async def complete_project(task_id: str, body: dict = None):
    """用户确认项目完成 — 通知 Leader 收尾汇总。"""
    svc = _get_svc()
    # 向 Leader 发送完成通知
    content = "## 用户确认\n"
    content += "用户已确认项目完成。"
    content += "请汇总最终结果，列出所有交付物，"
    content += "然后调用 complete_task 完成你的收尾工作。"
    if body and body.get("feedback"):
        content += f"\n\n用户反馈: {body['feedback']}"

    record = await svc.inject_message(
        task_id=task_id,
        agent_id="",  # 广播给所有智能体，Leader 会看到
        content=content,
    )
    return {"status": "completion_notified", "intervention_id": record.id}


@router.post("/tasks/{task_id}/plans/{plan_id}/review")
async def review_plan(task_id: str, plan_id: str, body: dict):
    """批准或驳回计划。

    body: {"approved": true, "reason": "..."}
    """
    approved = body.get("approved", False)
    reason = body.get("reason", "")
    svc = _get_svc()
    result = await svc.review_plan(task_id, plan_id, approved, reason)
    if result is None:
        raise HTTPException(status_code=404, detail="计划不存在或任务未运行")
    return result
