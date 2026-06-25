"""代码执行 API 路由 — 在沙盒中运行代码。"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..dependencies import get_task_service
from ..services.docker_sandbox import get_docker_sandbox

logger = logging.getLogger(__name__)

router = APIRouter()


class ExecuteRequest(BaseModel):
    command: str = Field(..., description="要执行的命令，如 'python main.py'")
    workdir: str = Field(default="/workspace", description="工作目录")
    timeout: int = Field(default=30, ge=1, le=120, description="超时秒数")


class ExecutePresetRequest(BaseModel):
    script: str = Field(default="run", description="预设脚本名：run/test/lint/build")


@router.post("/tasks/{task_id}/execute")
async def execute_code(task_id: str, req: ExecuteRequest):
    """在沙盒中执行任意命令。

    Docker 可用时在容器中运行，否则回退到本地进程。
    """
    service = get_task_service()
    task = service.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    ds = get_docker_sandbox()
    result = await ds.execute(task_id, req.command, req.workdir, req.timeout)
    return result


@router.post("/tasks/{task_id}/execute/{script_name}")
async def execute_preset(task_id: str, script_name: str):
    """执行预设验证脚本。

    script_name 可选值：run, test, lint, build
    """
    service = get_task_service()
    task = service.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    ds = get_docker_sandbox()
    result = await ds.run_preset(task_id, task.language, script_name)
    return result


@router.get("/tasks/{task_id}/presets")
async def get_presets(task_id: str):
    """获取该任务语言可用的预设脚本列表。"""
    service = get_task_service()
    task = service.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    ds = get_docker_sandbox()
    return ds.get_preset_scripts(task.language)
