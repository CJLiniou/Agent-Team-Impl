"""任务服务 — 编码任务的生命周期管理。

负责创建、启动、取消、删除编码任务。
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from ..config import get_settings
from ..models.task import CodingTask, CodingTaskCreate, TaskDB, CodingTaskStatus
from ..models.events import make_error_event, make_run_completed_event
from ..services.event_bridge import EventBridge
from ..services.sandbox_service import SandboxService
from ..worker.runner import CodingRunner

logger = logging.getLogger(__name__)


class TaskService:
    """编码任务生命周期管理。

    维护运行中的 asyncio Task 映射，支持取消操作。
    """

    def __init__(
        self,
        db: TaskDB,
        event_bridge: EventBridge,
        sandbox_service: SandboxService,
    ):
        self._db = db
        self._event_bridge = event_bridge
        self._sandbox_service = sandbox_service
        self._running: dict[str, asyncio.Task] = {}
        self._runners: dict[str, CodingRunner] = {}

    @property
    def db(self) -> TaskDB:
        """暴露 TaskDB 供其他服务（如团队配置）使用。"""
        return self._db

    # ── 任务创建 ─────────────────────────────────────────────

    async def create_and_run(self, create_req: CodingTaskCreate) -> CodingTask:
        """创建编码任务并开始后台执行。

        Args:
            create_req: 任务创建请求

        Returns:
            创建好的 CodingTask

        Raises:
            RuntimeError: 如果并发沙盒数已达上限
        """
        settings = get_settings()

        # 检查并发限制
        if len(self._running) >= settings.max_sandboxes:
            raise RuntimeError(
                f"已达到最大并发沙盒数（{settings.max_sandboxes}）。请等待其他任务完成后再试。"
            )

        # 创建任务实体
        task = CodingTask(
            title=create_req.title,
            description=create_req.description,
            language=create_req.language or "general",
            mode=create_req.mode or "team",
            num_coders=max(1, min(create_req.num_coders, settings.max_coders)),
            status=CodingTaskStatus.PENDING.value,
            model=create_req.model or settings.llm_model,
            max_tokens=create_req.max_tokens or settings.llm_max_tokens,
            team_config_json=create_req.team_config_json or "",
        )
        self._db.create(task)

        # 后台启动执行
        asyncio_task = asyncio.create_task(self._execute_task(task))
        self._running[task.id] = asyncio_task

        logger.info(f"Task {task.id} created: '{task.title}' (mode={task.mode}, language={task.language})")
        return task

    # ── 任务查询 ─────────────────────────────────────────────

    def get_task(self, task_id: str) -> Optional[CodingTask]:
        """获取单个任务详情。"""
        return self._db.get(task_id)

    def list_tasks(self, status: str = "") -> list[CodingTask]:
        """列出所有任务，可按状态过滤。"""
        return self._db.list_all(status=status)

    # ── 任务取消 ─────────────────────────────────────────────

    async def cancel_task(self, task_id: str) -> bool:
        """取消正在运行的任务。"""
        task = self._db.get(task_id)
        if task is None:
            return False

        if task.status not in (CodingTaskStatus.PENDING.value, CodingTaskStatus.RUNNING.value):
            logger.warning(f"Task {task_id} cannot be cancelled (status={task.status})")
            return False

        # 1. 通知 Runner 关停（force 模式，5s 超时）
        runner = self._runners.get(task_id)
        if runner:
            try:
                await asyncio.wait_for(runner.cancel(), timeout=5.0)
            except (asyncio.TimeoutError, Exception):
                logger.warning(f"Runner cancel timeout for {task_id}")

        # 2. 直接强制关闭 orchestrator 的所有 agent task（兜底）
        from ..orch_registry import get as get_orch
        orch = get_orch(task_id)
        if orch:
            try:
                await asyncio.wait_for(orch.shutdown_all(force=True), timeout=3.0)
            except (asyncio.TimeoutError, Exception):
                pass

        # 3. 取消 asyncio Task（强制中断 _execute_task）
        asyncio_task = self._running.get(task_id)
        if asyncio_task and not asyncio_task.done():
            asyncio_task.cancel()
            try:
                await asyncio_task
            except asyncio.CancelledError:
                pass

        # 3. 注销 orchestrator（停止 WebSocket push loop）
        from ..orch_registry import unregister as unregister_orch
        unregister_orch(task_id)

        # 4. 更新状态
        task.status = CodingTaskStatus.CANCELLED.value
        task.completed_at = datetime.now(timezone.utc).isoformat()
        self._db.update(task)

        # 5. 广播完成事件
        self._event_bridge.publish(
            task_id,
            make_run_completed_event(task_id, "cancelled", "用户取消了任务。"),
        )

        await self._cleanup(task_id)
        logger.info(f"Task {task_id} cancelled")
        return True

    # ── 任务删除 ─────────────────────────────────────────────

    async def delete_task(self, task_id: str) -> bool:
        """删除任务及其沙盒。

        Args:
            task_id: 任务 ID

        Returns:
            是否成功删除
        """
        task = self._db.get(task_id)
        if task is None:
            return False

        # 如果正在运行，先取消
        if task.status == CodingTaskStatus.RUNNING.value:
            await self.cancel_task(task_id)

        # 删除 Docker 容器和沙盒文件
        try:
            from ..services.docker_sandbox import get_docker_sandbox
            get_docker_sandbox().remove_container(task_id)
        except Exception:
            pass
        self._sandbox_service.delete_sandbox(task_id)

        # 清理事件缓存
        self._event_bridge.clear_task(task_id)

        # 从运行列表移除
        self._running.pop(task_id, None)
        self._runners.pop(task_id, None)

        # 删除 DB 记录
        return self._db.delete(task_id)

    # ── 继续编辑 ───────────────────────────────────────────

    async def continue_task(self, source_task_id: str, new_instructions: str) -> CodingTask:
        """从已完成/失败的任务创建新任务，复用已有沙盒文件。

        Args:
            source_task_id: 源任务 ID
            new_instructions: 新的修改需求

        Returns:
            新创建的 CodingTask

        Raises:
            ValueError: 源任务不存在
            RuntimeError: 并发沙盒数达上限
        """
        settings = get_settings()

        # 检查并发限制
        if len(self._running) >= settings.max_sandboxes:
            raise RuntimeError(
                f"已达到最大并发沙盒数（{settings.max_sandboxes}）。请等待其他任务完成后再试。"
            )

        # 读取源任务
        source_task = self._db.get(source_task_id)
        if source_task is None:
            raise ValueError(f"源任务不存在: {source_task_id}")

        # 组合描述：原始需求 + 新指令
        combined_description = (
            f"## 原始需求\n{source_task.description}\n\n"
            f"## 新增修改需求\n{new_instructions}\n\n"
            f"注意：项目文件已存在于 project/ 目录中，请在现有代码基础上进行修改，不要重新创建项目结构。"
        )

        # 创建新任务，继承源任务的所有配置
        new_title = f"{source_task.title} [继续编辑]"
        task = CodingTask(
            title=new_title,
            description=combined_description,
            language=source_task.language,
            mode=source_task.mode,
            num_coders=source_task.num_coders,
            status=CodingTaskStatus.PENDING.value,
            model=source_task.model or settings.llm_model,
            max_tokens=source_task.max_tokens or settings.llm_max_tokens,
            team_config_json=source_task.team_config_json or "",
            continue_from_task_id=source_task_id,
        )
        self._db.create(task)

        # 后台启动执行
        asyncio_task = asyncio.create_task(self._execute_task(task))
        self._running[task.id] = asyncio_task

        logger.info(
            f"Task {task.id} created (continue from {source_task_id}): "
            f"'{new_title}' (mode={task.mode}, language={task.language})"
        )
        return task

    # ── 内部方法 ─────────────────────────────────────────────

    async def _execute_task(self, task: CodingTask) -> None:
        """内部：在后台执行编码任务。"""
        task_id = task.id

        try:
            # 标记为运行中
            task.status = CodingTaskStatus.RUNNING.value
            task.started_at = datetime.now(timezone.utc).isoformat()
            self._db.update(task)

            # 解析可选的自定义团队配置
            team_config = None
            if task.team_config_json and task.team_config_json != "{}":
                try:
                    from ..models.team_config import TeamConfig
                    team_config = TeamConfig.from_dict(
                        __import__("json").loads(task.team_config_json)
                    )
                except Exception:
                    logger.warning("Failed to parse team_config_json — ignoring custom team")

            # 创建 Runner 并执行
            runner = CodingRunner(
                task_id=task_id,
                task_title=task.title,
                problem_description=task.description,
                language=task.language,
                mode=task.mode,
                num_coders=task.num_coders,
                model=task.model,
                max_tokens=task.max_tokens,
                event_bridge=self._event_bridge,
                sandbox_service=self._sandbox_service,
                team_config=team_config,
                continue_from_task_id=task.continue_from_task_id,
            )
            self._runners[task_id] = runner

            result = await runner.run()

            # 更新任务为已完成
            task.status = CodingTaskStatus.COMPLETED.value if result["success"] else CodingTaskStatus.FAILED.value
            task.result = result.get("answer", "")
            task.error_message = result.get("error", "")
            task.stats_json = __import__("json").dumps(result.get("stats", {}))
            # 持久化运行历史（agents, tasks, messages, logs）
            task.run_history_json = self._serialize_run_history(task_id)
            task.completed_at = datetime.now(timezone.utc).isoformat()
            self._db.update(task)

            # DB 更新后再推送最终快照 + 注销 orchestrator
            runner = self._runners.get(task_id)
            if runner:
                await runner._waiter.push_final_snapshot()
                from ..orch_registry import unregister as unregister_orch
                unregister_orch(task_id)

        except asyncio.CancelledError:
            task.status = CodingTaskStatus.CANCELLED.value
            task.completed_at = datetime.now(timezone.utc).isoformat()
            self._db.update(task)
            self._event_bridge.publish(
                task_id,
                make_run_completed_event(task_id, "cancelled", "Task was cancelled."),
            )

        except Exception as exc:
            logger.exception(f"Task {task_id} failed with exception")
            task.status = CodingTaskStatus.FAILED.value
            task.error_message = str(exc)
            task.completed_at = datetime.now(timezone.utc).isoformat()
            self._db.update(task)
            self._event_bridge.publish(
                task_id,
                make_error_event(task_id, str(exc), source="runner"),
            )

        finally:
            await self._cleanup(task_id)

    def _serialize_run_history(self, task_id: str) -> str:
        """将 EventBridge 中缓存的运行历史序列化为 JSON。"""
        import json as _json
        agents = self._event_bridge.get_agent_states(task_id)
        tasks = self._event_bridge.get_task_states(task_id)
        messages = self._event_bridge.get_messages(task_id)
        logs_raw = self._event_bridge.get_buffer(task_id)

        history = {
            "agents": [
                {
                    "id": a.id, "name": a.name, "role": a.role,
                    "state": a.state, "current_task_id": a.current_task_id,
                    "current_action": a.current_action,
                    "completed_tasks": a.completed_tasks,
                    "failed_tasks": a.failed_tasks,
                }
                for a in agents
            ],
            "task_queue": [
                {
                    "id": t.id, "name": t.name, "description": t.description[:200],
                    "status": t.status, "assigned_to": t.assigned_to,
                    "priority": t.priority, "result": t.result[:500],
                }
                for t in tasks
            ],
            "messages": messages,
            "logs": [
                {"level": e.data.get("level", "info"),
                 "message": e.data.get("message", ""),
                 "name": e.data.get("name", ""),
                 "timestamp": e.timestamp}
                for e in logs_raw
                if e.type in ("log_entry", "agent_step", "tool_call")
            ][-100:],
        }
        return _json.dumps(history, ensure_ascii=False)

    async def _cleanup(self, task_id: str) -> None:
        """清理运行中的任务资源。"""
        self._running.pop(task_id, None)
        self._runners.pop(task_id, None)
        logger.info(f"Task {task_id} cleaned up")
