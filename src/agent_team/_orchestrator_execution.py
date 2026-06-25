"""ExecutionDelegate — 任务认领、执行、心跳、工作分配。

从 orchestrator.py 中提取的回调模式任务执行引擎。
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from ._orchestrator_models import AgentState, ExecutionResult
from .tasks import Task, TaskStatus

logger = logging.getLogger(__name__)

MAX_IDLE_ROUNDS = 3


class ExecutionDelegate:
    """管理回调模式的任务执行：心跳、认领、执行、结果记录、工作分配。"""

    def __init__(self, agents: dict, task_manager, results: list):
        self._agents = agents
        self._task_manager = task_manager
        self._results = results
        self._lock = asyncio.Lock()

    async def heartbeat(self, agent_id: str, state: AgentState = AgentState.IDLE,
                        current_task_id: Optional[str] = None,
                        error_message: str = "") -> bool:
        """记录智能体心跳。"""
        async with self._lock:
            agent = self._agents.get(agent_id)
            if not agent:
                return False
            agent.last_heartbeat = datetime.now(timezone.utc)
            agent.state = state
            agent.current_task_id = current_task_id
            agent.error_message = error_message
            return True

    async def claim_task(self, agent_id: str) -> Optional[Task]:
        """为智能体认领可用任务。"""
        async with self._lock:
            agent = self._agents.get(agent_id)
            if not agent:
                return None

            available = self._task_manager.get_available_tasks(agent_id)
            if not available:
                return None

            for task in available:
                if self._task_manager.claim_task(task.id, agent_id):
                    agent.state = AgentState.BUSY
                    agent.current_task_id = task.id
                    logger.info(f"智能体 {agent_id} 认领任务 {task.id}")
                    return task

            return None

    async def execute_task(self, agent_id: str, task_id: str,
                           callbacks: dict) -> ExecutionResult:
        """执行任务（调用已注册的回调）。"""
        agent = self._agents.get(agent_id)
        task = self._task_manager.get_task(task_id)

        if not agent or not task:
            return ExecutionResult(
                task_id=task_id, agent_id=agent_id,
                status=TaskStatus.FAILED, error="智能体或任务不存在"
            )

        try:
            callback = None
            for capability in agent.capabilities:
                if capability in callbacks:
                    callback = callbacks[capability]
                    break

            if not callback and 'default' in callbacks:
                callback = callbacks['default']

            if not callback:
                raise ValueError(f"没有可用的执行回调: {agent.capabilities}")

            logger.info(f"执行任务 {task_id} 使用智能体 {agent_id}")
            output = await callback(task) if asyncio.iscoroutinefunction(callback) else callback(task)

            self._task_manager.update_task_status(task_id, TaskStatus.COMPLETED, str(output))

            result = ExecutionResult(
                task_id=task_id, agent_id=agent_id,
                status=TaskStatus.COMPLETED, output=str(output),
            )

            agent.completed_tasks += 1
            agent.state = AgentState.IDLE
            agent.current_task_id = None

            return result

        except Exception as e:
            logger.error(f"任务执行失败: {e}")
            self._task_manager.update_task_status(task_id, TaskStatus.FAILED)

            result = ExecutionResult(
                task_id=task_id, agent_id=agent_id,
                status=TaskStatus.FAILED, error=str(e),
            )

            agent.failed_tasks += 1
            agent.state = AgentState.ERROR
            agent.error_message = str(e)

            return result

    async def process_results(self, result: ExecutionResult) -> None:
        """处理和存储任务结果。"""
        async with self._lock:
            self._results.append(result)
            logger.info(f"结果已记录，任务 {result.task_id}: {result.status.value}")

    async def distribute_work(self, max_concurrent: int = 5) -> None:
        """持续向可用智能体分配工作，当所有任务完成时自动退出。"""
        active_tasks: set[str] = set()
        idle_rounds = 0

        while True:
            for task_id in list(active_tasks):
                task = self._task_manager.get_task(task_id)
                if task and task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                    active_tasks.discard(task_id)

            pending = self._task_manager.list_tasks(
                status=TaskStatus.PENDING, order_by="priority DESC, created_time ASC"
            )
            pending = [t for t in pending if not t.assigned_to
                       or t.assigned_to in self._agents]

            if pending and len(active_tasks) < max_concurrent:
                idle_agents = [a for a in self._agents.values() if a.state == AgentState.IDLE]
                for agent in idle_agents:
                    if len(active_tasks) >= max_concurrent:
                        break
                    task = await self.claim_task(agent.id)
                    if task:
                        active_tasks.add(task.id)
                        asyncio.create_task(self._execute_and_record(agent.id, task.id))

            if not active_tasks and not pending:
                idle_rounds += 1
                if idle_rounds >= MAX_IDLE_ROUNDS:
                    logger.info("所有任务已完成，工作分配结束")
                    return
            else:
                idle_rounds = 0

            await asyncio.sleep(0.5)

    async def _execute_and_record(self, agent_id: str, task_id: str) -> None:
        """执行任务并记录结果。"""
        result = await self.execute_task(agent_id, task_id,
                                         callbacks={})  # callbacks 由调用方传入
        await self.process_results(result)
