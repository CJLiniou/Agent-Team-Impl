"""人工介入服务 — 支持暂停/恢复/消息注入/计划审批。

通过 NotificationBus 向智能体推送介入事件，通过 EventBridge 推送 WebSocket 事件。
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from ..models.task import TaskDB
from ..models.intervention import InterventionRecord, InterventionType
from ..models.events import ServerEvent

logger = logging.getLogger(__name__)


class InterventionService:
    """管理人工介入逻辑。

    依赖：
    - TaskDB: 持久化介入记录
    - NotificationBus: 向智能体推送事件
    - EventBridge: 向前端推送 WebSocket 事件
    - orch_registry: 查找运行中的 Orchestrator
    """

    def __init__(self, db: TaskDB, event_bridge, orch_registry_module):
        self._db = db
        self._bridge = event_bridge
        self._get_orch = orch_registry_module.get  # 按需获取 orchestrator

    # ── 消息注入 ──────────────────────────────────────────

    async def inject_message(self, task_id: str, agent_id: str,
                             content: str) -> InterventionRecord:
        """向指定智能体注入消息。agent_id 为空则广播给所有智能体。"""
        now = datetime.now(timezone.utc).isoformat()
        record = InterventionRecord(
            id=str(uuid4()),
            task_id=task_id,
            agent_id=agent_id,
            type=InterventionType.MESSAGE.value,
            content=content,
            created_at=now,
        )
        self._db.create_intervention(record)

        orch = self._get_orch(task_id)
        if orch and orch.notification_bus:
            data = {"content": content, "intervention_id": record.id}
            if agent_id:
                await orch.notification_bus.publish(agent_id, "intervention", data)
            else:
                await orch.notification_bus.broadcast("intervention", data)

        # 推送 WebSocket 事件
        self._push_event(task_id, "intervention_received", {
            "intervention_id": record.id,
            "agent_id": agent_id or "*",
            "type": "message",
            "content": content,
        })

        logger.info(f"Intervention [{record.id[:8]}] -> task={task_id[:8]} agent={agent_id or 'ALL'}")
        return record

    # ── 暂停 / 恢复 ────────────────────────────────────────

    async def pause(self, task_id: str) -> InterventionRecord:
        """暂停指定任务的所有智能体。"""
        now = datetime.now(timezone.utc).isoformat()
        record = InterventionRecord(
            id=str(uuid4()),
            task_id=task_id,
            type=InterventionType.PAUSE.value,
            content="管理员暂停了任务",
            created_at=now,
        )
        self._db.create_intervention(record)

        orch = self._get_orch(task_id)
        if orch and orch.notification_bus:
            await orch.notification_bus.broadcast("pause", {"intervention_id": record.id})

        self._push_event(task_id, "task_paused", {
            "intervention_id": record.id,
            "reason": "手动暂停",
        })

        logger.info(f"Task {task_id[:8]} paused")
        return record

    async def resume(self, task_id: str) -> InterventionRecord:
        """恢复指定任务的所有智能体。"""
        now = datetime.now(timezone.utc).isoformat()
        record = InterventionRecord(
            id=str(uuid4()),
            task_id=task_id,
            type=InterventionType.RESUME.value,
            content="管理员恢复了任务",
            created_at=now,
        )
        self._db.create_intervention(record)

        orch = self._get_orch(task_id)
        if orch and orch.notification_bus:
            await orch.notification_bus.broadcast("resume", {"intervention_id": record.id})

        self._push_event(task_id, "task_resumed", {
            "intervention_id": record.id,
        })

        logger.info(f"Task {task_id[:8]} resumed")
        return record

    # ── 计划审批 ──────────────────────────────────────────

    async def review_plan(self, task_id: str, plan_id: str, approved: bool,
                          reason: str = "") -> Optional[dict]:
        """批准或驳回智能体提交的计划。"""
        orch = self._get_orch(task_id)
        if not orch or not orch.plan_manager:
            logger.warning(f"No orchestrator/plan_manager for task {task_id[:8]}")
            return None

        if approved:
            orch.plan_manager.approve(plan_id)
            # 通知智能体计划已批准
            if orch.notification_bus:
                plan = orch.plan_manager.get(plan_id)
                if plan:
                    await orch.notification_bus.publish(
                        plan.agent_id, "plan_approved",
                        {"plan_id": plan_id, "reason": reason}
                    )
        else:
            orch.plan_manager.reject(plan_id, reason)
            if orch.notification_bus:
                plan = orch.plan_manager.get(plan_id)
                if plan:
                    await orch.notification_bus.publish(
                        plan.agent_id, "plan_rejected",
                        {"plan_id": plan_id, "reason": reason}
                    )

        # 记录介入
        now = datetime.now(timezone.utc).isoformat()
        record = InterventionRecord(
            id=str(uuid4()),
            task_id=task_id,
            type=InterventionType.PLAN_REVIEW.value,
            content=json.dumps({
                "plan_id": plan_id,
                "approved": approved,
                "reason": reason,
            }),
            created_at=now,
        )
        self._db.create_intervention(record)

        # 推送 WebSocket
        self._push_event(task_id, "intervention_received", {
            "intervention_id": record.id,
            "type": "plan_review",
            "plan_id": plan_id,
            "approved": approved,
            "reason": reason,
        })

        return {"plan_id": plan_id, "approved": approved, "reason": reason}

    # ── 查询 ──────────────────────────────────────────────

    def list_interventions(self, task_id: str) -> list[dict]:
        """列出任务的所有介入记录。"""
        records = self._db.list_interventions(task_id)
        return [r.to_dict() for r in records]

    def get_pending_plans(self, task_id: str) -> list[dict]:
        """列出任务中所有待审批的计划。"""
        orch = self._get_orch(task_id)
        if not orch or not orch.plan_manager:
            return []
        pending = orch.plan_manager.list_pending()
        return [
            {
                "id": p.id,
                "agent_id": p.agent_id,
                "task_id": p.task_id,
                "content": p.plan_text,
                "status": p.status.value,
                "created_at": p.created_at,
            }
            for p in pending
        ]

    # ── 内部方法 ──────────────────────────────────────────

    def _push_event(self, task_id: str, event_type: str, data: dict) -> None:
        """推送 WebSocket 事件。"""
        try:
            self._bridge.publish(
                task_id,
                ServerEvent(
                    type=event_type,
                    task_id=task_id,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    data=data,
                ),
            )
        except Exception:
            logger.exception("Failed to push intervention event")
