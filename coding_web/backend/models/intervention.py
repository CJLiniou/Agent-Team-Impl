"""人工介入记录数据模型。"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4


class InterventionType(str, Enum):
    """介入类型枚举。"""
    MESSAGE = "message"            # 向智能体注入消息
    PLAN_REVIEW = "plan_review"    # 审批计划（批准/驳回）
    REDIRECT = "redirect"          # 重新分配任务
    PAUSE = "pause"                # 暂停
    RESUME = "resume"              # 恢复


@dataclass
class InterventionRecord:
    """单次人工介入记录。"""
    id: str = field(default_factory=lambda: str(uuid4()))
    task_id: str = ""                           # 所属任务 ID
    agent_id: str = ""                          # 目标智能体 ID（空=广播给所有智能体）
    type: str = "message"                       # InterventionType
    content: str = ""                           # 介入内容（消息文本 / 审批原因等）
    response: str = ""                          # 智能体响应（如有）
    metadata: str = "{}"                        # JSON 扩展字段
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    processed_at: str = ""

    def to_dict(self) -> dict:
        import json
        return {
            "id": self.id,
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "type": self.type,
            "content": self.content,
            "response": self.response,
            "metadata": json.loads(self.metadata) if self.metadata else {},
            "created_at": self.created_at,
            "processed_at": self.processed_at,
        }

    @classmethod
    def from_row(cls, row: tuple) -> "InterventionRecord":
        """从 SQLite 行创建记录。"""
        return cls(
            id=row[0],
            task_id=row[1],
            agent_id=row[2],
            type=row[3],
            content=row[4],
            response=row[5],
            metadata=row[6] if len(row) > 6 else "{}",
            created_at=row[7] if len(row) > 7 else "",
            processed_at=row[8] if len(row) > 8 else "",
        )
