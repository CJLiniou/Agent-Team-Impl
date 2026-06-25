"""团队配置 API 路由 — 管理智能体团队模板。"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ..dependencies import get_task_service
from ..models.team_config import TeamConfig, AgentConfig
from ..services.team_config_service import TeamConfigService

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_service() -> TeamConfigService:
    """从全局任务服务获取 TeamConfigService 实例。"""
    ts = get_task_service()
    return TeamConfigService(ts.db)

@router.post("/teams", status_code=201)
async def create_team(config: TeamConfig):
    """创建团队模板。

    请求体为 TeamConfig JSON，其中 agents 为 AgentConfig 列表。
    """
    svc = _get_service()
    return svc.create(config).to_dict()


@router.get("/teams")
async def list_teams():
    """列出所有团队模板。"""
    svc = _get_service()
    templates = svc.list_all()
    return [t.to_dict() for t in templates]


@router.get("/teams/{template_id}")
async def get_team(template_id: str):
    """获取单个团队模板详情。"""
    svc = _get_service()
    config = svc.get(template_id)
    if config is None:
        raise HTTPException(status_code=404, detail="团队模板不存在")
    return config.to_dict()


@router.put("/teams/{template_id}")
async def update_team(template_id: str, config: TeamConfig):
    """更新团队模板。"""
    svc = _get_service()
    updated = svc.update(template_id, config)
    if updated is None:
        raise HTTPException(status_code=404, detail="团队模板不存在")
    return updated.to_dict()


@router.delete("/teams/{template_id}", status_code=204)
async def delete_team(template_id: str):
    """删除团队模板。"""
    svc = _get_service()
    if not svc.delete(template_id):
        raise HTTPException(status_code=404, detail="团队模板不存在")
    return None
