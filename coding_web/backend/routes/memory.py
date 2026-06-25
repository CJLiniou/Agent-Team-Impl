"""智能体记忆 API 路由 — 读取智能体的持久化记忆。"""

import logging

from fastapi import APIRouter, HTTPException, Query
from pathlib import Path

from ..config import get_settings
from ..dependencies import get_task_service
from ..services.agent_memory_service import AgentMemoryService

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_memory_svc(task_id: str, agent_id: str) -> AgentMemoryService:
    """创建 AgentMemoryService 实例。先验证任务存在。"""
    ts = get_task_service()
    task = ts.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    sandbox_root = get_settings().sandbox_root
    return AgentMemoryService(sandbox_root, task_id, agent_id)


@router.get("/tasks/{task_id}/agents/{agent_id}/memory")
async def get_memory_summary(task_id: str, agent_id: str):
    """获取智能体记忆摘要。"""
    svc = _get_memory_svc(task_id, agent_id)
    return svc.get_memory_summary()


@router.get("/tasks/{task_id}/agents/{agent_id}/memory/conversation")
async def get_conversation(
    task_id: str,
    agent_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """获取智能体对话历史（分页）。"""
    svc = _get_memory_svc(task_id, agent_id)
    conversations = svc.get_conversation(limit=limit, offset=offset)
    total = svc.get_conversation_count()
    return {
        "items": conversations,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/tasks/{task_id}/agents/{agent_id}/memory/decisions")
async def get_decisions(task_id: str, agent_id: str, limit: int = Query(20, ge=1, le=100)):
    """获取智能体决策记录。"""
    svc = _get_memory_svc(task_id, agent_id)
    return svc.get_decisions(limit=limit)


@router.get("/tasks/{task_id}/agents/{agent_id}/memory/files")
async def get_file_changes(task_id: str, agent_id: str, limit: int = Query(30, ge=1, le=100)):
    """获取智能体文件变更记录。"""
    svc = _get_memory_svc(task_id, agent_id)
    return svc.get_file_changes(limit=limit)


@router.get("/tasks/{task_id}/agents/{agent_id}/memory/notes")
async def get_notes(task_id: str, agent_id: str):
    """获取智能体笔记。"""
    svc = _get_memory_svc(task_id, agent_id)
    return svc.get_notes()


@router.post("/tasks/{task_id}/agents/{agent_id}/memory/notes", status_code=201)
async def add_note(task_id: str, agent_id: str, body: dict):
    """为智能体添加笔记（人或智能体均可写入）。"""
    svc = _get_memory_svc(task_id, agent_id)
    content = body.get("content", "")
    tags = body.get("tags", "")
    if not content.strip():
        raise HTTPException(status_code=400, detail="笔记内容不能为空")
    note_id = svc.add_note(content, tags)
    return {"id": note_id, "status": "created"}
