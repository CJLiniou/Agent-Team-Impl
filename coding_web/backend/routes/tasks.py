"""任务 CRUD API 路由。"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ..dependencies import get_task_service, get_sandbox_service
from ..models.task import CodingTaskCreate

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/tasks", status_code=201)
async def create_task(req: CodingTaskCreate):
    """
    创建新的编码任务，立即在后台开始执行。

    """
    try:
        service = get_task_service()
        task = await service.create_and_run(req)
        return task.to_dict()
    except RuntimeError as exc:
        raise HTTPException(status_code=429, detail=str(exc))
    except Exception as exc:
        logger.exception("Failed to create task")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/tasks/recover")
async def recover_orphan_tasks():
    """从沙盒目录恢复没有 DB 记录的任务（用于 DB 迁移后恢复）。"""
    import json as _json
    from pathlib import Path as _Path
    service = get_task_service()
    sandbox = get_sandbox_service()

    recovered = []
    if sandbox.sandbox_root.exists():
        for d in sorted(sandbox.sandbox_root.iterdir(), reverse=True):
            if not d.is_dir():
                continue
            task_id = d.name
            # 跳过已有 DB 记录的任务
            existing = service.get_task(task_id)
            if existing:
                continue

            # 从 TEAM.md 和 problem.txt 恢复基本信息
            team_md = d / "TEAM.md"
            problem_txt = d / "problem.txt"
            title = task_id[:8]
            description = ""
            if problem_txt.exists():
                description = problem_txt.read_text(encoding="utf-8")[:200]
            elif team_md.exists():
                content = team_md.read_text(encoding="utf-8")
                for line in content.split("\n"):
                    if "Language:" in line:
                        pass
                description = content[:200]

            # 创建恢复记录
            from ..models.task import CodingTask, CodingTaskStatus
            task = CodingTask(
                id=task_id,
                title=f"[Recovered] {title}",
                description=description,
                status=CodingTaskStatus.COMPLETED.value,
                sandbox_path=str(d),
                result="(从沙盒恢复 — 无运行历史)",
            )
            service._db.create(task)
            recovered.append(task.to_dict())

    return {"recovered": len(recovered), "tasks": recovered}


@router.get("/tasks")
async def list_tasks(status: Optional[str] = Query(None, description="按状态过滤：pending|running|completed|failed|cancelled")):
    """列出所有编码任务。"""
    service = get_task_service()
    tasks = service.list_tasks(status=status or "")
    return [t.to_dict() for t in tasks]


@router.get("/tasks/{task_id}")
async def get_task(task_id: str):
    """获取单个编码任务详情。"""
    service = get_task_service()
    task = service.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task.to_dict()


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    """取消并删除任务（及其沙盒）。"""
    service = get_task_service()
    success = await service.delete_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "deleted", "task_id": task_id}


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    """取消正在运行的任务。"""
    service = get_task_service()
    success = await service.cancel_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found or not running")
    return {"status": "cancelled", "task_id": task_id}


@router.post("/tasks/{task_id}/continue", status_code=201)
async def continue_task(task_id: str, req: dict):
    """从已完成/失败的任务创建新任务继续编辑。

    新任务会复用原任务的沙盒文件，AI 智能体可以看到已有代码并在此基础上修改。

    请求体示例:
    ```json
    {
        "instructions": "请为所有函数添加错误处理和单元测试"
    }
    ```
    """
    try:
        service = get_task_service()
        new_instructions = req.get("instructions", "")
        if not new_instructions.strip():
            raise HTTPException(status_code=400, detail="instructions is required")
        task = await service.continue_task(task_id, new_instructions)
        return task.to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=429, detail=str(exc))
    except Exception as exc:
        logger.exception("Failed to continue task")
        raise HTTPException(status_code=500, detail=str(exc))
