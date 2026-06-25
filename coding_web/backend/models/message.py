"""消息数据模型（API 响应）。"""

from dataclasses import dataclass, field


@dataclass
class AgentMessageResponse:
    """API 返回的智能体间消息。"""
    id: str
    sender: str
    recipient: str           # 空字符串 = 广播
    subject: str
    content: str
    status: str              # sent | delivered | read | failed
    created_at: str

    @staticmethod
    def from_dict(d: dict) -> "AgentMessageResponse":
        return AgentMessageResponse(
            id=d.get("id", ""),
            sender=d.get("sender", ""),
            recipient=d.get("recipient", ""),
            subject=d.get("subject", ""),
            content=d.get("content", ""),
            status=d.get("status", "sent"),
            created_at=d.get("created_at", ""),
        )
