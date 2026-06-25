"""PlanDelegate — 计划审批：提交、批准、拒绝、LLM 审查。

从 orchestrator.py 中提取的窄接口计划管理。
"""

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class PlanDelegate:
    """管理计划审批流程：批准、拒绝、列出待处理、LLM 自动审查。"""

    def __init__(self, plan_manager, notification_bus, task_manager=None):
        self._plan_manager = plan_manager
        self._notification_bus = notification_bus
        self._task_manager = task_manager

    def approve(self, plan_id: str, feedback: str = "") -> bool:
        """批准一个待处理的计划。"""
        ok = self._plan_manager.approve(plan_id, feedback)
        if ok:
            plan = self._plan_manager.get(plan_id)
            if plan and self._notification_bus:
                asyncio.create_task(
                    self._notification_bus.publish(
                        plan.agent_id, "plan_approved",
                        {"plan_id": plan_id, "feedback": feedback}
                    )
                )
        return ok

    def reject(self, plan_id: str, reason: str) -> bool:
        """拒绝一个待处理的计划。"""
        ok = self._plan_manager.reject(plan_id, reason)
        if ok:
            plan = self._plan_manager.get(plan_id)
            if plan and self._notification_bus:
                asyncio.create_task(
                    self._notification_bus.publish(
                        plan.agent_id, "plan_rejected",
                        {"plan_id": plan_id, "reason": reason}
                    )
                )
        return ok

    def list_pending(self) -> list:
        """列出所有待审批的计划。"""
        return self._plan_manager.list_pending()

    async def review_with_llm(self, plan, criteria: str) -> Optional[str]:
        """使用 LLM 审查计划。返回 None 表示批准，返回字符串表示拒绝原因。"""
        if not self._task_manager:
            return None  # 无 task_manager 时退化为手动审批

        task = self._task_manager.get_task(plan.task_id)
        task_name = task.name if task else "Unknown"
        task_desc = task.description if task else ""

        review_prompt = f"""你是团队 Leader，正在审查智能体 "{plan.agent_name}" 的执行计划。

任务: {task_name}
任务描述: {task_desc}

智能体的计划:
---
{plan.plan_text}
---

审查标准:
{criteria}

评估此计划是否满足标准。只回复以下两种格式之一:

APPROVE: <批准理由（一行）>
REJECT: <驳回原因，附带具体的改进建议>

不要输出其他内容。回复以 APPROVE 或 REJECT 开头。"""

        try:
            from .llm_provider import create_provider
            provider = create_provider(model="claude-haiku-4-5-20251001")
            response = await provider.create_message(
                model="claude-haiku-4-5-20251001",
                system_prompt="",
                messages=[{"role": "user", "content": review_prompt}],
                max_tokens=512,
            )
            text = response.content[0]
            if not isinstance(text, str):
                text = str(text)
            text = text.strip()

            if text.startswith("APPROVE"):
                reason = text[len("APPROVE:"):].strip() if ":" in text else text[len("APPROVE"):].strip()
                logger.info(f"Plan {plan.id} APPROVED by LLM: {reason}")
                return None
            elif text.startswith("REJECT"):
                reason = text[len("REJECT:"):].strip() if ":" in text else text[len("REJECT"):].strip()
                logger.info(f"Plan {plan.id} REJECTED by LLM: {reason}")
                return reason
            else:
                logger.warning(f"LLM review response unclear, auto-approving: {text[:100]}")
                return None
        except Exception as exc:
            logger.error(f"LLM plan review failed: {exc}, auto-approving")
            return None
