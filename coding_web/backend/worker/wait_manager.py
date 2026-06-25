"""等待管理器 — 统一的等待循环、dashboard 推送、完成检测、Reviewer 重试。

从 runner.py 中提取，消除 _wait_for_agents 和 _wait_for_completion 间的重复代码。
"""

import asyncio
import logging
import time
from typing import Callable, Optional

from agent_team import AgentState

logger = logging.getLogger(__name__)

DASHBOARD_INTERVAL = 5.0  # dashboard 推送间隔（秒）


class WaitManager:
    """管理 agent 任务等待、超时检测和 Reviewer 补救逻辑。"""

    def __init__(self, task_id: str, console):
        self.task_id = task_id
        self.console = console
        self._update_task_fn = None  # 由调用方设置，用于 Reviewer 重试

    # ── 公共接口 ──────────────────────────────────────────────────

    async def wait_for_completion(
        self, orch, agent_ids: list[str], timeout: float = 300,
        cancelled: Optional[Callable[[], bool]] = None,
        max_review_retries: int = 1,
    ) -> dict:
        """等待所有 agent 的任务完成。

        Returns: {"ok": bool, "failed_tasks": [str], "timed_out": bool}
        """
        deadline = time.time() + timeout
        last_dash = -999
        review_retries = 0
        all_clear_count = 0

        while time.time() < deadline and not (cancelled and cancelled()):
            now = time.time()
            if now - last_dash >= DASHBOARD_INTERVAL:
                self._push_dashboard(orch)
                last_dash = now

            all_tasks = orch.task_manager.list_tasks()
            pending = [t for t in all_tasks if t.status.value in ("pending", "in_progress")]

            if not pending:
                all_clear_count += 1
                if all_clear_count >= 2:
                    failed = [t.name for t in all_tasks if t.status.value == "failed"]
                    if failed:
                        logger.warning(f"{len(failed)} task(s) failed: {failed}")
                    return {"ok": True, "failed_tasks": failed, "timed_out": False}
                await asyncio.sleep(3.0)
                continue
            else:
                all_clear_count = 0

            # Reviewer 超时前补救
            if self._update_task_fn:
                review_pending = [t for t in pending if "Review" in t.name]
                other_pending = [t for t in pending if "Review" not in t.name]
                remaining = deadline - time.time()
                if (review_pending and not other_pending
                        and remaining < 60 and review_retries < max_review_retries):
                    review_retries += 1
                    for rt in review_pending:
                        logger.warning(
                            f"Review task '{rt.name}' approaching timeout, "
                            f"retry {review_retries}/{max_review_retries}"
                        )
                        try:
                            self._update_task_fn(
                                orch.task_manager.db_path, rt.id,
                                f"⏰ 时间紧迫，快速审查:\n"
                                f"read_file 浏览主要文件 → 没问题 complete_task(\"审查通过\") → 有问题 publish_task"
                            )
                        except Exception:
                            pass
                    deadline += 90

            await asyncio.sleep(1.0)

        all_tasks = orch.task_manager.list_tasks()
        failed_names = [t.name for t in all_tasks if t.status.value in ("pending", "in_progress")]
        logger.error(f"Timeout — incomplete tasks: {failed_names}")
        return {"ok": False, "failed_tasks": failed_names, "timed_out": True}

    async def wait_for_agents(
        self, orch, agent_ids: list[str],
        task_prefix: str = "", timeout: float = 300,
        cancelled: Optional[Callable[[], bool]] = None,
    ) -> bool:
        """等待指定 agent 的任务完成。返回 True 表示全部完成。"""
        deadline = time.time() + timeout
        pending = set(agent_ids)
        last_dash = -999

        while pending and time.time() < deadline and not (cancelled and cancelled()):
            now = time.time()
            if now - last_dash >= DASHBOARD_INTERVAL:
                self._push_dashboard(orch)
                last_dash = now

            done = set()
            for aid in pending:
                for task in orch.task_manager.list_tasks():
                    if task.assigned_to != aid:
                        continue
                    if task_prefix and task_prefix not in task.name:
                        continue
                    if task.status.value in ("completed", "failed"):
                        done.add(aid)
                        if task.status.value == "failed":
                            logger.error(
                                f"Agent {aid} task '{task.name}' FAILED. "
                                f"Reason: {(task.result or '(no detail)')[:300]}"
                            )
                        elif task.status.value == "completed":
                            agent_obj = orch.agents.get(aid) if isinstance(orch.agents, dict) else None
                            agent_display = agent_obj.name if agent_obj else aid
                            self.console.task_completed(
                                agent_display, task.name,
                                task.result[:200] if task.result else "",
                            )
                        break

            pending -= done
            if pending:
                await asyncio.sleep(3.0)

        if pending:
            logger.error(f"Timeout waiting for agents: {pending}")
        return len(pending) == 0

    async def push_final_snapshot(self) -> None:
        """任务完成前推送最后一次快照。"""
        try:
            from ..dependencies import get_ws_manager
            ws = get_ws_manager()
            await ws.push_snapshot(self.task_id)
        except Exception:
            pass

    # ── 内部辅助 ──────────────────────────────────────────────────

    def _push_dashboard(self, orch) -> None:
        """推送当前 agent 和 task 状态的 dashboard 快照。"""
        self.console.team_dashboard(orch.agents, orch.task_manager.list_tasks())
