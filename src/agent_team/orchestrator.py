"""智能体团队编排和协调。

TeamOrchestrator 作为 facade，将 agent 注册、计划审批、回调执行、状态导出
委托给专门的类。LLM 生命周期方法（spawn/fork/shutdown/run）保留在此处作为 hub。
"""

import asyncio
import json
import logging
import shutil
from pathlib import Path
from typing import Optional, Callable, Any, Dict, List
from uuid import uuid4

from .tasks import TaskManager, Task, TaskStatus
from .mailbox import AgentMailbox
from .hooks import HookRegistry
from .planning import PlanManager
from .notifications import NotificationBus
from .token_tracker import TokenTracker
from .profiles import ProfileRegistry, AgentProfile
from .observability import TeamConsole
from ._orchestrator_models import AgentRole, AgentState, Agent, ExecutionResult
from ._orchestrator_registry import AgentRegistry
from ._orchestrator_plan import PlanDelegate
from ._orchestrator_execution import ExecutionDelegate
from ._orchestrator_state import StateSnapshot

logger = logging.getLogger(__name__)


class TeamOrchestrator:
    """编排智能体团队工作（facade，委托给 4 个专门类）。"""

    def __init__(self, db_path: Path, team_name: str = "default",
                 mailbox_path: Optional[Path] = None):
        self.team_name = team_name
        self.hook_registry = HookRegistry()
        self.task_manager = TaskManager(db_path, hook_registry=self.hook_registry)
        self.mailbox_path = mailbox_path or (db_path.parent / f"{team_name}_mailbox.db")
        self.mailbox = AgentMailbox(self.mailbox_path)
        self.plan_manager = PlanManager()
        self.notification_bus = NotificationBus()
        self.token_tracker = TokenTracker()
        self.profile_registry = ProfileRegistry()
        self.console = TeamConsole()

        # 委托对象
        self._registry = AgentRegistry()
        self._plan = PlanDelegate(self.plan_manager, self.notification_bus, self.task_manager)
        self._exec = ExecutionDelegate(self._registry.agents, self.task_manager, self.results if False else [])
        self._state = StateSnapshot(team_name)

        # Internal state（LLM hub）
        self.results: List[ExecutionResult] = []
        self._exec._results = self.results  # share list reference
        self._llm_agent_tasks: Dict[str, asyncio.Task] = {}
        self._llm_agents: Dict[str, Any] = {}

        # 事件路由
        self.mailbox.set_notify_callback(self._on_new_message)
        self.task_manager.set_notify_callback(self._on_task_unblocked)

    # ── 兼容属性（保持旧 API）───────────────────────────────────────

    @property
    def agents(self) -> dict:
        return self._registry.agents

    @agents.setter
    def agents(self, value):
        self._registry._agents = value

    @property
    def execution_callbacks(self) -> dict:
        return self._registry.callbacks

    # ── Agent 注册（委托）─────────────────────────────────────────────

    def register_agent(self, agent_id: str, name: str, role: AgentRole,
                       capabilities: Optional[list[str]] = None,
                       metadata: Optional[dict] = None) -> Agent:
        return self._registry.register(agent_id, name, role, capabilities, metadata)

    def unregister_agent(self, agent_id: str) -> bool:
        return self._registry.unregister(agent_id)

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        return self._registry.get(agent_id)

    def list_agents(self, role: Optional[AgentRole] = None,
                    state: Optional[AgentState] = None) -> list[Agent]:
        return self._registry.list(role, state)

    def set_execution_callback(self, capability: str,
                               callback: Callable[[Task], Any]) -> None:
        self._registry.set_callback(capability, callback)

    def set_work_dir(self, path: str) -> None:
        self._registry.set_work_dir(path)

    # ── Agent 统计 ────────────────────────────────────────────────────

    def get_agent_stats(self, agent_id: str) -> Optional[dict]:
        return self._registry.get_stats(agent_id)

    # ── 计划审批（委托）───────────────────────────────────────────────

    def approve_plan(self, plan_id: str, feedback: str = "") -> bool:
        return self._plan.approve(plan_id, feedback)

    def reject_plan(self, plan_id: str, reason: str) -> bool:
        return self._plan.reject(plan_id, reason)

    def list_pending_plans(self) -> list:
        return self._plan.list_pending()

    async def _review_plan_with_llm(self, plan, criteria: str) -> Optional[str]:
        return await self._plan.review_with_llm(plan, criteria)

    # ── 回调执行（委托）───────────────────────────────────────────────

    async def heartbeat(self, agent_id: str, state: AgentState = AgentState.IDLE,
                        current_task_id: Optional[str] = None,
                        error_message: str = "") -> bool:
        return await self._exec.heartbeat(agent_id, state, current_task_id, error_message)

    async def claim_task(self, agent_id: str) -> Optional[Task]:
        return await self._exec.claim_task(agent_id)

    async def execute_task(self, agent_id: str, task_id: str) -> ExecutionResult:
        return await self._exec.execute_task(agent_id, task_id, self.execution_callbacks)

    async def process_results(self, result: ExecutionResult) -> None:
        await self._exec.process_results(result)

    async def distribute_work(self, max_concurrent: int = 5) -> None:
        await self._exec.distribute_work(max_concurrent)

    async def _execute_and_record(self, agent_id: str, task_id: str) -> None:
        result = await self._exec.execute_task(agent_id, task_id, self.execution_callbacks)
        await self._exec.process_results(result)

    # ── 状态查询（委托）───────────────────────────────────────────────

    def get_team_stats(self) -> dict:
        return self._state.get_team_stats(
            self._registry.agents, self.task_manager, self.token_tracker, self.results,
        )

    def get_results(self, task_id: Optional[str] = None,
                    agent_id: Optional[str] = None,
                    status: Optional[TaskStatus] = None) -> list[ExecutionResult]:
        return self._state.get_results(self.results, task_id, agent_id, status)

    def export_state(self) -> dict:
        return self._state.export_state(self._registry.agents, self.results, self.task_manager)

    def import_state(self, state: dict) -> None:
        self._state.import_state(self._registry.agents, state)

    # ── Event callbacks ───────────────────────────────────────────────

    async def _on_task_unblocked(self, agent_name: str, task_name: str) -> None:
        await self.notification_bus.publish(
            agent_name, "task_unblocked", {"task_name": task_name},
        )

    async def _on_new_message(self, recipient: str, sender: str) -> None:
        if recipient == "__broadcast__":
            await self.notification_bus.broadcast("new_message", {"sender": sender})
        else:
            target_id = None
            for aid, agent in self.agents.items():
                if agent.name == recipient:
                    target_id = aid
                    break
            if target_id:
                await self.notification_bus.publish(target_id, "new_message", {"sender": sender})

    # ══════════════════════════════════════════════════════════════════
    # Hub 方法 — 保留在 TeamOrchestrator（接线中心）
    # ══════════════════════════════════════════════════════════════════

    def spawn_from_profile(self, profile_name: str, agent_id: str,
                           model: str = "", require_plan_approval: bool = False) -> asyncio.Task:
        """从 AgentProfile 创建并启动 LLM agent。"""
        profile = self.profile_registry.get(profile_name)
        if not profile:
            raise ValueError(
                f"Profile '{profile_name}' not found. "
                f"Available: {self.profile_registry.list()}"
            )
        role = AgentRole(profile.role)
        self.register_agent(
            agent_id=agent_id, name=profile.name, role=role,
            capabilities=profile.capabilities,
            metadata={"profile": profile_name, **profile.metadata},
        )
        return self.spawn_llm_agent(
            agent_id, model=model or profile.model,
            system_prompt_extra=profile.system_prompt_extra,
            require_plan_approval=require_plan_approval,
        )

    async def create_from_description(self, description: str,
                                       model: str = "claude-sonnet-4-6",
                                       provider=None) -> "TeamOrchestrator":
        """从自然语言描述创建团队（调用 LLM 解析）。"""
        if provider is None:
            from .llm_provider import create_provider
            provider = create_provider(model=model)

        parse_prompt = f"""将以下团队描述解析为 JSON，包含 "agents" 和 "tasks" 数组。

团队描述: {description}

只输出合法的 JSON:
{{
  "agents": [
    {{"id": "agent-1", "name": "...", "role": "executor|coordinator|reviewer|specialist", "capabilities": ["..."]}}
  ],
  "tasks": [
    {{"name": "...", "description": "...", "priority": 0|1|2, "depends_on": []}}
  ]
}}

规则:
- 使用唯一 ID，如 "agent-1", "agent-2"
- 角色: executor(执行者), coordinator(协调者), reviewer(审查者), specialist(专家)
- depends_on: 必须先行完成的任务索引列表（从0开始）
- 建议 3-5 个智能体和 3-8 个任务"""

        response = await provider.create_message(
            model=model, system_prompt="",
            messages=[{"role": "user", "content": parse_prompt}],
            max_tokens=2048,
        )
        text = response.content[0] if isinstance(response.content[0], str) else str(response.content[0])
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]

        config = json.loads(text)
        task_map = {}
        for a in config.get("agents", []):
            self.register_agent(
                agent_id=a["id"], name=a["name"],
                role=AgentRole(a.get("role", "executor")),
                capabilities=a.get("capabilities", []),
            )
        for i, t in enumerate(config.get("tasks", [])):
            deps = [task_map[idx] for idx in t.get("depends_on", []) if idx in task_map]
            created = self.task_manager.create_task(
                name=t["name"], description=t.get("description", ""),
                priority=t.get("priority", 0), depends_on=deps,
            )
            task_map[i] = created.id

        logger.info(f"Team created from description: {len(self.agents)} agents")
        return self

    def spawn_llm_agent(self, agent_id: str, model: str = "claude-sonnet-4-6",
                        system_prompt_extra: str = "",
                        require_plan_approval: bool = False,
                        provider=None, extra_body: dict | None = None,
                        max_tokens: int = 4096) -> asyncio.Task:
        """创建并启动 LLM agent（hub 方法 — 接线所有子系统）。"""
        if agent_id not in self._registry.agents:
            raise ValueError(f"Agent {agent_id} not registered")

        from .tools import create_default_registry, set_agent_context
        from .llm_agent import LLMAgent

        if provider is None:
            from .llm_provider import create_provider
            provider = create_provider(model=model)

        async def _fork_cb(parent_agent_id, parent_agent_name, name, role, reason):
            return await self.fork_agent(parent_agent_id, parent_agent_name, name, role, reason)

        agent = self.agents[agent_id]
        capabilities = agent.capabilities or []
        explicit_allowlist = agent.metadata.get("tools_allowlist", None)
        if explicit_allowlist and isinstance(explicit_allowlist, str):
            explicit_allowlist = [t.strip() for t in explicit_allowlist.split(",") if t.strip()]

        from .tools import compute_tools_allowlist, build_system_prompt
        agent_role_str = agent.role.value if hasattr(agent.role, 'value') else str(agent.role)
        computed_allowlist = compute_tools_allowlist(capabilities, agent_role_str, explicit_allowlist)

        can_publish = agent.metadata.get("can_publish_tasks") or agent.metadata.get("is_leader")
        if can_publish and computed_allowlist is not None:
            computed_allowlist.add("publish_task")

        is_leader = bool(agent.metadata.get("is_leader"))
        user_extra = agent.metadata.get("system_prompt_extra", "") or system_prompt_extra or ""
        if not system_prompt_extra or is_leader or capabilities:
            system_prompt_extra = build_system_prompt(
                role=agent_role_str,
                capabilities=capabilities if capabilities else None,
                is_leader=is_leader, user_extra=user_extra,
            )

        registry = create_default_registry(
            self.task_manager, self.mailbox, self.agents, self._registry._work_dir,
            plan_manager=self.plan_manager, notification_bus=self.notification_bus,
            fork_callback=_fork_cb, tools_allowlist=computed_allowlist,
        )
        set_agent_context(registry, agent.name, agent_id, agent_role_str)

        llm_agent = LLMAgent(
            agent=agent,
            tool_registry=registry,
            task_manager=self.task_manager,
            mailbox=self.mailbox,
            team_name=self.team_name,
            work_dir=self._registry._work_dir,
            model=model,
            require_plan_approval=require_plan_approval,
            plan_manager=self.plan_manager,
            notification_bus=self.notification_bus,
            token_tracker=self.token_tracker,
            hook_registry=self.hook_registry,
            provider=provider,
            console=self.console,
            extra_body=extra_body,
            max_tokens=max_tokens,
            system_prompt_extra=system_prompt_extra,
        )

        task = asyncio.create_task(
            llm_agent.run(agent_count=len(self.agents)),
            name=f"llm_agent_{agent_id}",
        )
        self._llm_agent_tasks[agent_id] = task
        self._llm_agents[agent_id] = llm_agent
        self.agents[agent_id].metadata["llm_model"] = model
        self.agents[agent_id].metadata["require_plan_approval"] = require_plan_approval
        return task

    async def run_llm_team(self, model: str = "claude-sonnet-4-6",
                           poll_interval: float = 5.0,
                           require_plan_approval: bool = False,
                           plan_review_criteria: Optional[str] = None,
                           provider=None, extra_body: dict | None = None,
                           max_tokens: int = 4096) -> None:
        """以 LLM 模式运行所有 agent。"""
        if provider is None:
            from .llm_provider import create_provider
            provider = create_provider(model=model)

        for agent_id in self.agents:
            self.spawn_llm_agent(
                agent_id, model=model, require_plan_approval=require_plan_approval,
                provider=provider, extra_body=extra_body, max_tokens=max_tokens,
            )

        if require_plan_approval:
            if plan_review_criteria is None:
                logger.info("Plan review: MANUAL — use approve_plan()/reject_plan()")
            elif plan_review_criteria == "auto":
                self.plan_manager.on_plan_submitted(lambda p: None)
                logger.info("Plan review: AUTO-APPROVE")
            else:
                orch = self

                async def llm_review_callback(plan):
                    return await orch._review_plan_with_llm(plan, plan_review_criteria)

                self.plan_manager.on_plan_submitted(llm_review_callback)
                logger.info(f"Plan review: LLM — criteria: {plan_review_criteria}")

        self.console.leader_tick(f"LLM team started with {len(self.agents)} agents")
        self.console.team_dashboard(self.agents, self.task_manager.list_tasks())
        self.notification_bus.register("__leader__")

        dash_interval = 15
        last_dash = 0
        while True:
            stats = self.task_manager.get_task_stats()
            pending_tasks = stats.get('pending', 0)
            in_progress = stats.get('in_progress', 0)
            pending_plans = len(self.plan_manager.list_pending())

            if pending_tasks == 0 and in_progress == 0 and pending_plans == 0:
                self.console.leader_tick("All tasks completed")
                break

            import time as _time
            now = _time.time()
            if now - last_dash > dash_interval:
                self.console.team_dashboard(self.agents, self.task_manager.list_tasks())
                last_dash = now

            await self.notification_bus.consume("__leader__", timeout=poll_interval)

        await self.shutdown_all()

    async def fork_agent(self, parent_agent_id: str, parent_agent_name: str,
                         name: str, role: str, reason: str,
                         memory_export: dict | None = None) -> str:
        """Fork 一个子智能体。"""
        parent = self.agents.get(parent_agent_id)
        if not parent:
            return f"错误: 父智能体 {parent_agent_id} 不存在"

        if not parent.metadata.get("allow_fork", False):
            return "错误: 此智能体没有 fork 权限"

        fork_limit = parent.metadata.get("fork_limit", 3)
        fork_count = sum(
            1 for a in self.agents.values()
            if a.metadata.get("parent_agent_id") == parent_agent_id
        )
        if fork_count >= fork_limit:
            return f"错误: 已达到 fork 上限 ({fork_limit})"

        child_id = str(uuid4())
        role_map = {
            "executor": AgentRole.EXECUTOR, "reviewer": AgentRole.REVIEWER,
            "specialist": AgentRole.SPECIALIST, "coordinator": AgentRole.COORDINATOR,
        }
        agent_role = role_map.get(role, AgentRole.EXECUTOR)

        child_meta = {
            "parent_agent_id": parent_agent_id,
            "parent_agent_name": parent_agent_name,
            "fork_reason": reason,
            "allow_fork": False,
            "fork_limit": 0,
        }

        self.register_agent(
            agent_id=child_id, name=name, role=agent_role,
            capabilities=parent.capabilities.copy(), metadata=child_meta,
        )

        child_task = self.task_manager.create_task(
            name=f"Fork: {name}",
            description=(
                f"你被 {parent_agent_name} fork 来处理以下子任务:\n\n{reason}\n\n"
                f"完成此子任务后，用 send_message 向 {parent_agent_name} 汇报结果，"
                f"然后用 complete_task 标记完成。"
            ),
            priority=2,
        )

        provider = None
        if self._llm_agents:
            first_agent = next(iter(self._llm_agents.values()))
            provider = first_agent.provider

        model = parent.metadata.get("llm_model", "claude-sonnet-4-6")
        fork_system_prompt = (
            f"你由 {parent_agent_name} fork 创建，任务: {reason}\n\n"
            f"专注于这个具体任务，完成后向 {parent_agent_name} 汇报。"
        )

        self.spawn_llm_agent(child_id, model=model, system_prompt_extra=fork_system_prompt,
                             provider=provider)
        self.task_manager.claim_task(child_task, child_id)

        if self.console and hasattr(self.console, 'agent_forked'):
            self.console.agent_forked(parent_agent_name, name, reason)

        logger.info(f"Agent forked: {name} ({child_id[:8]}) by {parent_agent_name}")
        return (
            f"子智能体 {name} ({child_id[:8]}) 已创建。\n"
            f"角色: {role}\n任务: {child_task}\n\n"
            f"子智能体会自动开始工作。你可以继续你的工作，"
            f"等待子智能体通过 send_message 向你汇报结果。"
        )

    async def shutdown_agent(self, agent_id: str, force: bool = False,
                             timeout: float = 30.0) -> tuple[bool, str]:
        """向 agent 发送关闭请求。"""
        if agent_id not in self._llm_agent_tasks:
            return False, "Agent not found"

        if force:
            task = self._llm_agent_tasks.pop(agent_id, None)
            self._llm_agents.pop(agent_id, None)
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            self.agents[agent_id].state = AgentState.IDLE
            logger.info(f"Agent {agent_id} force-stopped")
            return True, "Force-stopped"

        llm_agent = self._llm_agents.get(agent_id)
        if not llm_agent:
            return False, "Agent instance not found"

        llm_agent.request_shutdown()
        if self.notification_bus:
            await self.notification_bus.publish(agent_id, "shutdown_request")

        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            response = llm_agent.get_shutdown_response()
            if response is not None:
                accept, reason = response
                if accept:
                    task = self._llm_agent_tasks.get(agent_id)
                    if task:
                        try:
                            await asyncio.wait_for(task, timeout=10)
                        except (asyncio.TimeoutError, asyncio.CancelledError):
                            task.cancel()
                    self._llm_agent_tasks.pop(agent_id, None)
                    self._llm_agents.pop(agent_id, None)
                    self.agents[agent_id].state = AgentState.IDLE
                    logger.info(f"Agent {agent_id} shut down gracefully: {reason}")
                    return True, reason
                else:
                    return False, reason
            await asyncio.sleep(0.5)

        logger.warning(f"Agent {agent_id} did not respond to shutdown, force-stopping")
        return await self.shutdown_agent(agent_id, force=True)

    async def shutdown_all(self, force: bool = False, timeout: float = 3.0) -> None:
        """关闭所有 agent。"""
        for agent_id in list(self._llm_agent_tasks):
            try:
                if force:
                    await self.shutdown_agent(agent_id, force=True)
                else:
                    ok, reason = await self.shutdown_agent(agent_id, timeout=timeout)
                    if not ok:
                        logger.warning(f"Force-stopping {agent_id}: {reason}")
                        await self.shutdown_agent(agent_id, force=True)
            except Exception:
                try:
                    await self.shutdown_agent(agent_id, force=True)
                except Exception:
                    pass

    def cleanup_team(self, remove_data: bool = False) -> None:
        """清理团队数据。"""
        lock_dir = self.task_manager._lock_dir
        if lock_dir.exists() and remove_data:
            shutil.rmtree(lock_dir, ignore_errors=True)
        if remove_data:
            for path in [self.task_manager.db_path, self.mailbox.db_path]:
                try:
                    if path.exists():
                        path.unlink()
                except PermissionError:
                    pass
            logger.info(f"Team '{self.team_name}' data cleaned up")
