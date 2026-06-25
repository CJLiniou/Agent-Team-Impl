"""沙盒文件浏览 API 路由。"""

from fastapi import APIRouter, HTTPException

from ..dependencies import get_task_service, get_sandbox_service

router = APIRouter()


@router.get("/tasks/{task_id}/files")
async def get_file_tree(task_id: str):
    """获取沙盒文件树结构。

    Returns:
        文件树节点列表，每个节点有 name、path、type（file/dir）、children
    """
    service = get_task_service()
    task = service.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    sandbox = get_sandbox_service()
    tree = sandbox.get_file_tree(task_id)
    return tree


@router.get("/tasks/{task_id}/files/{file_path:path}")
async def get_file_content(task_id: str, file_path: str):
    """读取沙盒中指定文件的内容。
    Args:
        task_id: 编码任务 ID
        file_path: 文件相对路径（如 "project/src/main.py"）
    Returns:
        文件内容
    """
    service = get_task_service()
    task = service.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    sandbox = get_sandbox_service()
    content = sandbox.read_file(task_id, file_path)
    if content is None:
        raise HTTPException(status_code=404, detail="File not found")

    return {
        "path": file_path,
        "content": content,
        "task_id": task_id,
    }
