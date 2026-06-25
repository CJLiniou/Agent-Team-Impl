"""消息历史查询 API 路由。"""

import json
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..dependencies import get_event_bridge, get_task_service

# 确保 agent_team 可导入
_src = Path(__file__).parent.parent.parent.parent / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from agent_team import AgentMailbox

router = APIRouter()


@router.get("/tasks/{task_id}/messages")
async def get_task_messages(task_id: str):
    """获取指定任务的智能体间消息历史。

    运行中任务从 SQLite mailbox 直接读取（与 Agent 实际收发的完全一致），
    已完成任务从 run_history_json 读取。
    """
    service = get_task_service()
    task = service.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    messages = []

    # 优先从 SQLite mailbox 读取（运行中任务）
    sandbox_root = Path(__file__).parent.parent / "sandboxes"
    db_path = sandbox_root / task_id / "team.db"
    if db_path.exists():
        try:
            mailbox = AgentMailbox(str(db_path))
            for msg in mailbox.list_messages():
                messages.append({
                    "id": msg.id,
                    "sender": msg.sender,
                    "recipient": msg.recipient,
                    "subject": msg.subject,
                    "content": msg.content,
                    "status": msg.status.value,
                    "created_at": msg.created_at.isoformat() if msg.created_at else "",
                })
        except Exception:
            pass  # DB 可能被锁，降级

    # SQLite 为空时尝试 EventBridge 内存缓存
    if not messages:
        bridge = get_event_bridge()
        eb_msgs = bridge.get_messages(task_id)
        if eb_msgs:
            messages = eb_msgs

    # 最终降级到 run_history_json
    if not messages:
        try:
            history = json.loads(task.run_history_json or "{}")
            messages = history.get("messages", [])
        except Exception:
            pass

    return messages
