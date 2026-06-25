"""LLMAgent — 由 Anthropic Claude 驱动的自主智能体。

每个 LLMAgent 在独立的异步循环中运行：
1. 检查邮箱中的新消息（通过 NotificationBus 推送）
2. [Plan 模式] 制定执行计划 → 提交审批 → 等待 leader 决策
3. [Execute 模式] 使用 LLM 推理 + 工具调用来执行任务
4. 完成后通过 TokenTracker 记录用量
"""

import asyncio
import logging
from typing import Optional

from .orchestrator import Agent, AgentState
from .tools import ToolRegistry

logger = logging.getLogger(__name__)

# ── Tool allowlists for plan/execute modes ───────────────────────────

PLAN_MODE_TOOLS = {
    "read_file", "read_task", "list_tasks", "list_agents",
    "submit_plan", "check_plan_status",
    "check_mailbox", "send_message",
    "respond_to_shutdown",
}

EXECUTE_MODE_TOOLS = {
    "claim_task", "complete_task", "fail_task",
    "send_message", "check_mailbox",
    "list_agents", "list_tasks",
    "read_file", "read_task", "write_file",
    "respond_to_shutdown", "fork_agent", "publish_task",
    "execute_code", "glob", "grep",
}

# ── System prompt template ───────────────────────────────────────────

SYSTEM_PROMPT_BASE = """你是团队 "{team_name}" 中的 AI 智能体，名称为 {name}，角色为 {role}。
你与 {team_size} 个其他智能体协作完成任务。

你的能力: {capabilities}

## 工作流程

1. claim_task 认领任务 → 执行 → complete_task 完成
2. 任务用 list_tasks 看，消息用 check_mailbox 看（仅在有未读提示时）

## 规则

- 一次一个任务，write_file 后立刻 complete_task
- 用 list_agents 了解队友角色后再分派任务或发消息
- prompt 提示有未读消息时才 check_mailbox。没任务时 list_tasks 查看
- send_message 后最多等 2 轮，没回复就自己做决定
- 已完成 complete_task 后不要再干涉——保持空闲，不要反复提醒队友
- read_file 只读具体文件，不要读目录('.' 'project/')
- 阻塞时用 fail_task 说明原因

工作目录: {work_dir}
"""

PLAN_MODE_PROMPT = """
## 规划模式

你处于规划模式，必须先提交计划并获得**用户（人类）**批准才能执行。

⚠️ 审批来自用户，不是队友。不要广播计划请队友审批——他们没权限。

步骤:
1. 用 read_file / list_tasks 了解任务
2. 创建详细计划: 技术栈、文件结构、接口设计
3. 调用 submit_plan 提交计划 → 用户在前端看到并审批
4. 用 check_plan_status 等待（用户可能不在线，耐心等）
5. 批准后执行；驳回后修改重提交

在用户批准之前，只能 read_file/list_tasks/submit_plan/check_plan_status。
不要 write_file、不要 complete_task、不要广播计划给队友。
"""


# ── LLMAgent ──────────────────────────────────────────────────────────

class LLMAgent:
    """由 LLM 驱动的自主智能体，支持 Plan 审批、推送通知和 Token 追踪。"""

    def __init__(
        self,
        agent: Agent,
        tool_registry: ToolRegistry,
        task_manager,
        mailbox,
        team_name: str = "",
        work_dir: str = ".",
        model: str = "claude-sonnet-4-6",
        require_plan_approval: bool = False,
        plan_manager=None,
        notification_bus=None,
        token_tracker=None,
        hook_registry=None,
        provider=None,
        console=None,
        extra_body=None,
        max_tokens: int = 4096,
        system_prompt_extra: str = "",
    ):
        self.agent = agent
        self.provider = provider  # LLMProvider instance
        self.console = console
        self.extra_body = extra_body  # 模型特定参数，如 {"enable_thinking": False}
        self.max_tokens = max_tokens  # 模型最大输出 token 数
        self.tool_registry = tool_registry
        self.task_manager = task_manager
        self.mailbox = mailbox
        self.team_name = team_name
        self.work_dir = work_dir
        self.model = model

        # 新系统集成
        self.require_plan_approval = require_plan_approval
        self.plan_manager = plan_manager
        self.notification_bus = notification_bus
        self.token_tracker = token_tracker
        self.hook_registry = hook_registry

        self._running = False
        self._paused = False
        self._intervention_message: Optional[str] = None
        self._stop_event = asyncio.Event()
        self._plan_mode = require_plan_approval  # true = planning, false = executing
        self._plan_id: Optional[str] = None
        self._shutdown_requested = False
        self._shutdown_response: Optional[tuple[bool, str]] = None
        self._rate_limit_retries = 0
        self._recent_actions: list[str] = []  # 最近几步的动作摘要
        self._last_error: str = ""            # 上一步的工具错误信息
        self._memory_provider = None          # callable: () -> str，返回持久记忆摘要
        self._system_prompt_extra = system_prompt_extra  # 角色+能力+Leader 追加提示词

    def _get_provider(self):
        if self.provider is None:
            from .llm_provider import create_provider
            self.provider = create_provider(model=self.model)
        return self.provider

    def _build_system_prompt(self, agent_count: int) -> str:
        capabilities = ", ".join(self.agent.capabilities) if self.agent.capabilities else "general task execution"
        prompt = SYSTEM_PROMPT_BASE.format(
            name=self.agent.name, role=self.agent.role.value,
            team_name=self.team_name, team_size=agent_count,
            capabilities=capabilities, work_dir=self.work_dir,
        )

        # 自动加载 TEAM.md（项目上下文）
        team_md = self._load_team_md()
        if team_md:
            prompt += f"\n\n## Project context (TEAM.md)\n\n{team_md}"

        # 附加角色提示词（coordinator/executor/reviewer/specialist 的行为准则）
        if self._system_prompt_extra:
            prompt += "\n\n" + self._system_prompt_extra

        if self._plan_mode:
            prompt += PLAN_MODE_PROMPT
        return prompt

    def _load_team_md(self) -> str:
        """从工作目录加载 TEAM.md 文件。"""
        import os
        md_path = os.path.join(self.work_dir, "TEAM.md")
        try:
            with open(md_path, encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return ""
        except Exception:
            logger.warning(f"Failed to read TEAM.md from {md_path}")
            return ""

    def _get_active_schemas(self) -> list[dict]:
        """返回当前模式下的工具 schema。"""
        allowlist = PLAN_MODE_TOOLS if self._plan_mode else EXECUTE_MODE_TOOLS
        all_schemas = self.tool_registry.get_schemas()
        return [s for s in all_schemas if s["name"] in allowlist]

    async def run(self, agent_count: int = 1, poll_interval: float = 2.0) -> None:
        """启动自主代理循环。"""
        self._running = True
        self._stop_event.clear()
        system_prompt = self._build_system_prompt(agent_count)

        if self.notification_bus:
            self.notification_bus.register(self.agent.id)

        # 随机启动延迟，避免多 Agent 同时请求触发限流
        stagger = __import__('random').uniform(0.3, 1.5)
        await asyncio.sleep(stagger)

        if self.console:
            self.console.agent_start(self.agent.name, self.model)

        logger.info(f"LLMAgent {self.agent.name} started (plan_mode={self._plan_mode})")

        while self._running and not self._stop_event.is_set():
            try:
                # 暂停检查 — 被 supervisor 暂停时跳过推理
                if self._paused:
                    await self._wait_for_next_event(fallback_timeout=5.0)
                    continue

                # 检查计划审批状态
                await self._check_plan_decision()

                # 基于任务池状态决定是否需要 LLM 推理
                timeout = self._compute_idle_timeout()
                should_reason, timeout = self._should_enter_reasoning(timeout)

                if should_reason:
                    # 执行推理步骤
                    await self._step(system_prompt, agent_count)
                elif self.console:
                    self.console.agent_idle(self.agent.name)

                # 检查 shutdown 响应
                if self._shutdown_requested:
                    ctx = self.tool_registry.context
                    if ctx.shutdown_response is not None:
                        accept, reason = ctx.shutdown_response
                        self._shutdown_response = (accept, reason)
                        ctx.shutdown_response = None
                        if accept:
                            logger.info(f"{self.agent.name} accepted shutdown: {reason}")
                            break
                        else:
                            logger.info(f"{self.agent.name} rejected shutdown: {reason}")
                            self._shutdown_requested = False
                    # 如果 agent 空闲且没有回复（没有 task），自动接受
                    elif not ctx.current_task_id:
                        self._shutdown_response = (True, "Agent is idle")
                        logger.info(f"{self.agent.name} auto-accepted shutdown (idle)")
                        break

                # 触发 TEAMMATE_IDLE 钩子
                if self.hook_registry:
                    if not self.tool_registry.context.current_task_id:
                        from .hooks import HookEvent, HookContext
                        allowed, reason = await self.hook_registry.trigger(
                            HookEvent.TEAMMATE_IDLE,
                            HookContext(event=HookEvent.TEAMMATE_IDLE,
                                        agent_id=self.agent.id,
                                        agent_name=self.agent.name),
                        )
                        if not allowed:
                            self.agent.state = AgentState.BUSY
                            continue

            except Exception as exc:
                from .tasks import TaskStatus

                # 永久性错误 — 标记当前任务失败，不重试
                permanent = self._is_permanent_error(exc)
                if permanent:
                    current = self.tool_registry.context.current_task_id
                    if current:
                        self.task_manager.update_task_status(
                            current, TaskStatus.FAILED, f"Permanent error: {exc}"
                        )
                        self.tool_registry.context.current_task_id = ""
                    self.agent.state = AgentState.IDLE
                    if self.console:
                        self.console.error(self.agent.name, str(exc))
                    logger.error(f"Agent {self.agent.name} permanent error, task failed: {exc}")
                    if self._shutdown_requested:
                        self._shutdown_response = (True, "Shutting down after error")
                        break
                    break  # 永久错误直接退出

                # 429 限流 — 指数退避 + 随机 jitter + 上限
                is_rate_limit = "429" in str(exc) or "rate" in str(exc).lower()
                if is_rate_limit:
                    retry_count = getattr(self, '_rate_limit_retries', 0) + 1
                    self._rate_limit_retries = retry_count
                    import random
                    # 上限: 6 次重试后放弃，标记任务失败
                    if retry_count > 6:
                        if self.console:
                            self.console.error(self.agent.name, "Rate limit exceeded 6 retries, giving up")
                        logger.error(f"Agent {self.agent.name} rate limited {retry_count} times, giving up")
                        current = self.tool_registry.context.current_task_id
                        if current:
                            self.task_manager.update_task_status(
                                current, TaskStatus.FAILED, "Rate limit exceeded after 6 retries"
                            )
                            self.tool_registry.context.current_task_id = ""
                        self.agent.state = AgentState.IDLE
                        self._rate_limit_retries = 0
                        break
                    base = min(5 * (2 ** retry_count), 120)
                    delay = base + random.uniform(0, base * 0.3)  # jitter 防止 agent 同步
                    if self.console:
                        self.console.rate_limited(self.agent.name, retry_count, delay)
                    logger.warning(
                        f"Agent {self.agent.name} rate limited, retry #{retry_count} in {delay:.0f}s"
                    )
                else:
                    self._rate_limit_retries = 0
                    delay = 10
                    if self.console:
                        self.console.error(self.agent.name, str(exc))
                    logger.exception(f"Agent {self.agent.name} error, retrying")

                if self._shutdown_requested:
                    self._shutdown_response = (True, "Shutting down after error")
                    break

                await asyncio.sleep(delay)

            # 等待下一个事件或超时（超时由任务池状态决定）
            await self._wait_for_next_event(timeout)

        logger.info(f"LLMAgent {self.agent.name} stopped")

    @staticmethod
    def _is_permanent_error(exc: Exception) -> bool:
        """判断是否是永久性错误（不应重试）。"""
        name = type(exc).__name__
        msg = str(exc).lower()
        # OpenAI / DashScope 错误码
        permanent_names = {"PermissionDeniedError", "AuthenticationError", "BadRequestError"}
        if name in permanent_names:
            return True
        # HTTP 状态码
        for code in ["403", "401", "400"]:
            if f"error code: {code}" in msg or f"status code: {code}" in msg:
                return True
        # 配额相关
        if "quota" in msg or "exhausted" in msg or "free tier" in msg:
            return True
        return False

    def _compute_idle_timeout(self) -> float:
        """根据当前任务池状态计算休眠时长（零 LLM 调用）。

        有任务 → 5-10s（活跃检查），无任务 → 30-60s（低频等待）。
        """
        ctx = self.tool_registry.context

        # 有活跃任务 → 短间隔
        if ctx.current_task_id:
            return 10.0

        # 有可认领的任务 → 短间隔
        available = self.task_manager.get_available_tasks(self.agent.name)
        if available:
            return 5.0

        # 有 blocked 的任务 → 中等间隔（等依赖完成）
        all_tasks = self.task_manager.list_tasks()
        blocked = [t for t in all_tasks if t.status.value == "blocked"]
        if blocked:
            return 20.0

        # 完全空闲 → 长间隔
        return 60.0

    def _should_enter_reasoning(self, timeout: float) -> tuple[bool, float]:
        """判断是否应该进入 LLM 推理，还是直接跳过继续休眠。

        无需 LLM 调用 — 全部基于 task_manager 的本地 SQLite 查询。

        Returns: (should_reason: bool, adjusted_timeout: float)
        """
        ctx = self.tool_registry.context

        # 有干预消息、计划变更或 shutdown → 必须推理
        if self._intervention_message:
            return True, timeout
        if self._shutdown_requested:
            return True, timeout
        if self._last_error:
            return True, timeout
        # 有计划被驳回 → 必须推理
        if self._plan_id and self.plan_manager:
            plan = self.plan_manager.get(self._plan_id)
            if plan and plan.status.value == "rejected":
                return True, timeout

        # 正在执行任务 → 推理
        if ctx.current_task_id:
            return True, timeout

        # 有可认领的任务 → 推理
        available = self.task_manager.get_available_tasks(self.agent.name)
        if available:
            return True, timeout

        # 有新消息 → 推理
        unread = self.mailbox.get_unread_count(self.agent.name)
        if unread > 0:
            return True, timeout

        # 无任何需要处理的事件 — 跳过推理，直接继续等待
        return False, timeout

    async def _wait_for_next_event(self, fallback_timeout: float) -> None:
        """等待通知总线事件或超时。"""
        if self.notification_bus:
            notif = await self.notification_bus.consume(
                self.agent.id, timeout=fallback_timeout
            )
            if notif:
                logger.debug(f"{self.agent.name} woke by: {notif.type}")
                if notif.type == "shutdown_request":
                    self._shutdown_requested = True
                elif notif.type == "task_unblocked":
                    pass  # 任务可用，下一步 claim_task 会认领
                elif notif.type == "new_message":
                    # 有新消息 → 立即唤醒不做额外动作，下一步 _build_turn_prompt 会提示未读
                    pass
                elif notif.type == "pause":
                    self._paused = True
                    logger.info(f"{self.agent.name} paused by supervisor")
                elif notif.type == "resume":
                    self._paused = False
                    logger.info(f"{self.agent.name} resumed by supervisor")
                elif notif.type == "intervention":
                    self._intervention_message = notif.data.get("content", "")
                    logger.info(f"{self.agent.name} received supervisor intervention")

    async def _check_plan_decision(self) -> None:
        """检查是否有计划被审批/拒绝。"""
        if not self.plan_manager or not self._plan_id:
            return

        plan = self.plan_manager.get(self._plan_id)
        if not plan:
            return

        if plan.status.value == "approved":
            self._plan_mode = False
            self._plan_id = None
            logger.info(f"{self.agent.name} plan approved, entering execute mode")
        elif plan.status.value == "rejected":
            # 保持 plan mode，在下一个 step 中包含拒绝反馈
            logger.info(f"{self.agent.name} plan rejected: {plan.feedback}")

    async def _step(self, system_prompt: str, agent_count: int = 1) -> None:
        """执行一个推理步骤。"""
        from .llm_provider import ToolUseBlock

        provider = self._get_provider()
        prompt = self._build_turn_prompt()

        messages = [{"role": "user", "content": prompt}]
        schemas = self._get_active_schemas()
        tools = schemas if schemas else None

        response = await provider.create_message(
            model=self.model,
            system_prompt=system_prompt,
            messages=messages,
            tools=tools or None,
            max_tokens=self.max_tokens,
            extra_body=self.extra_body,
        )

        # 记录 token 用量
        if self.token_tracker:
            self.token_tracker.record(
                self.agent.id, self.agent.name, self.model,
                response.usage.input_tokens, response.usage.output_tokens,
            )

        # 处理工具调用循环（限制轮数，防止空转）
        max_tool_rounds = 3
        for _ in range(max_tool_rounds):
            if response.stop_reason == "end_turn":
                if self.console:
                    thought = ""
                    for b in response.content:
                        if isinstance(b, str):
                            thought = b
                            break
                    if thought:
                        self.console.agent_step(self.agent.name, thought)
                break

            if response.stop_reason == "tool_use":
                tool_blocks = [b for b in response.content if isinstance(b, ToolUseBlock)]
                if not tool_blocks:
                    break

                tool_results = []
                for block in tool_blocks:
                    logger.info(f"{self.agent.name} tool: {block.name}({block.input})")
                    result = await self.tool_registry.execute(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

                    if self.console:
                        self.console.tool_call(self.agent.name, block.name, block.input, result)

                    # 检测工具错误
                    is_error = str(result).startswith(("⛔", "错误", "⚠️", "无法", "收件人"))
                    if is_error:
                        self._last_error = f"{block.name}: {str(result)[:200]}"

                    # 记录最近动作（防重复）
                    action_summary = f"- {block.name}: "
                    if is_error:
                        action_summary += "❌ "
                    if block.name == "publish_task":
                        action_summary += f"发布「{block.input.get('name', '?')}」"
                    elif block.name == "complete_task":
                        action_summary += f"完成 — {str(block.input.get('result', ''))[:60]}"
                    elif block.name == "claim_task":
                        action_summary += f"认领 {block.input.get('task_id', '?')}"
                    elif block.name == "write_file":
                        action_summary += f"写入 {block.input.get('path', '?')}"
                    elif block.name == "read_file":
                        p = block.input.get('path', '?')
                        action_summary += f"读取 {p} ✓"
                    elif block.name == "send_message":
                        rcpt = block.input.get('recipient', '') or '全体'
                        action_summary += f"→ {rcpt}: {str(block.input.get('subject', ''))[:50]}"
                    elif block.name == "list_tasks":
                        action_summary += f"查看任务列表"
                    elif block.name == "check_mailbox":
                        action_summary += f"查收件箱"
                    else:
                        action_summary += str(block.input)[:60]
                    self._recent_actions.append(action_summary)
                    if len(self._recent_actions) > 30:
                        self._recent_actions = self._recent_actions[-30:]

                    # 如果调用了 submit_plan，设置 plan 等待状态
                    if block.name == "submit_plan":
                        self._plan_id = self.tool_registry.context.current_plan_id or None

                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})

                response = await provider.create_message(
                    model=self.model,
                    system_prompt=system_prompt,
                    messages=messages,
                    tools=tools or None,
                    max_tokens=self.max_tokens,
                    extra_body=self.extra_body,
                )

                if self.token_tracker:
                    self.token_tracker.record(
                        self.agent.id, self.agent.name, self.model,
                        response.usage.input_tokens, response.usage.output_tokens,
                    )
            else:
                break

        # 更新 agent 状态
        self._update_state()

    def _update_state(self) -> None:
        current_task_id = self.tool_registry.context.current_task_id
        if current_task_id:
            self.agent.state = AgentState.BUSY
            self.agent.current_task_id = current_task_id
        else:
            self.agent.state = AgentState.IDLE
            self.agent.current_task_id = None

    def _build_turn_prompt(self) -> str:
        current_task_id = self.tool_registry.context.current_task_id

        parts = []

        # 上一步工具错误 → 反思提示
        if self._last_error:
            parts.append(
                f"## ⚠️ 上一步操作失败，需要修正\n{self._last_error}\n"
                f"请根据错误信息调整参数，重新尝试。不要忽略错误继续其他操作。"
            )
            self._last_error = ""

        # 最近动作（防重复）
        if self._recent_actions:
            recent = self._recent_actions[-15:]
            parts.append("## 已完成的操作（不要重复！）\n" + "\n".join(recent) +
                        "\n\n⚠️ 上面已完成的不要再做。读过的文件不要再读。直接下一步决策。")

        # 持久记忆注入
        if self._memory_provider:
            mem_text = self._memory_provider()
            if mem_text:
                parts.append(f"## 你的历史记忆\n{mem_text}")

        # 人工介入消息
        if self._intervention_message:
            parts.append(f"## 管理员消息\n**{self._intervention_message}**\n请据此调整工作。")
            self._intervention_message = None

        if current_task_id:
            task = self.task_manager.get_task(current_task_id)
            if task:
                desc = task.description or '无'
                if len(desc) > 2000:
                    desc = desc[:2000] + "\n...(截断，用 read_task 看完整)"
                parts.append(
                    f"## 当前任务: {task.name} ({task.id})\n{desc}\n"
                )
                if self._plan_mode:
                    parts.append("规划模式: 先 submit_plan，批准后再执行。")
                else:
                    parts.append("执行此任务，完成后 complete_task。")
            else:
                parts.append("当前任务已移除，寻找新任务。")
        else:
            parts.append("## 状态: 空闲\n你当前没有任务。用 claim_task 认领，或用 list_tasks 查看。")

        # Plan 拒绝
        if self._plan_id and self.plan_manager:
            plan = self.plan_manager.get(self._plan_id)
            if plan and plan.status.value == "rejected":
                parts.append(f"\n计划被驳回: {plan.feedback}\n修改后重新 submit_plan。")
                self._plan_id = None

        # 未读消息
        unread = self.mailbox.get_unread_count(self.agent.name)
        if unread > 0:
            parts.append(f"\n{unread} 条未读消息，用 check_mailbox 查看。")

        # Shutdown 请求
        if self._shutdown_requested:
            parts.append(
                "\n## 关闭请求\n"
                "Leader 请求关闭。空闲/可停止 → respond_to_shutdown(accept=true)\n"
                "正在关键任务 → respond_to_shutdown(accept=false)"
            )

        return "\n\n".join(parts)

    def request_shutdown(self) -> None:
        """Leader 调用此方法发起关闭请求。Agent 会在下一个推理步骤中处理。"""
        self._shutdown_requested = True
        logger.info(f"Shutdown requested for {self.agent.name}")

    def get_shutdown_response(self) -> Optional[tuple[bool, str]]:
        """获取 agent 对关闭请求的响应。(accepted, reason) 或 None（尚未响应）。"""
        return self._shutdown_response

    async def shutdown(self) -> None:
        """优雅关闭 agent。"""
        self._running = False
        self._stop_event.set()
        if self.notification_bus:
            self.notification_bus.unregister(self.agent.id)
        logger.info(f"LLMAgent {self.agent.name} shutting down")
