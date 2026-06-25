"""工具处理器工厂函数 — 从 create_default_registry() 闭包中提取。

每个工厂函数接收依赖和 AgentContext，返回可注册到 ToolRegistry 的 handler。
"""

import logging
import os

from .registry import AgentContext

logger = logging.getLogger(__name__)

# ── 角色文件类型限制常量 ─────────────────────────────────────────────

CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs",
    ".cpp", ".c", ".h", ".hpp", ".cs", ".rb", ".php", ".swift",
    ".html", ".css", ".scss", ".less", ".vue", ".svelte",
}

ROLE_RESTRICTED_EXTENSIONS = {
    "coordinator": CODE_EXTENSIONS,
    "reviewer":    CODE_EXTENSIONS,
}

# ── 处理器工厂函数 ───────────────────────────────────────────────────


def make_claim_task_handler(task_manager, context: AgentContext, agents_dict: dict = None):
    """创建 claim_task 处理器。"""
    def _claim_task(task_id: str = "") -> str:
        agent_id = context.agent_id or context.agent_name
        if task_id:
            task = task_manager.get_task(task_id)
            if not task:
                return f"错误: 任务 {task_id} 不存在"
            if task.assigned_to and task.assigned_to != agent_id:
                return f"无法认领 {task_id} — 分配给 {task.assigned_to}，不是你"
            ok = task_manager.claim_task(task_id, agent_id)
            if ok:
                context.current_task_id = task_id
                desc = (task_manager.get_task(task_id) or task).description or ""
                return f"已认领任务 {task_id}\n\n任务描述:\n{desc}"
            return f"无法认领任务 {task_id}（可能已被认领或依赖未满足）"

        available = task_manager.get_available_tasks(agent_id)
        if not available:
            all_tasks = task_manager.list_tasks()
            blocked = [t for t in all_tasks if t.status.value == "blocked" and
                       (not t.assigned_to or t.assigned_to == agent_id)]
            if blocked:
                names = ", ".join(f"{t.name}(依赖未满足)" for t in blocked[:3])
                return f"有 {len(blocked)} 个任务等待依赖完成:\n{names}\n等依赖完成后即可认领。"
            return "当前没有可认领的任务。等待新任务发布。"
        task = available[0]
        ok = task_manager.claim_task(task.id, agent_id)
        if ok:
            context.current_task_id = task.id
            return f"已认领任务: {task.name} ({task.id})\n\n任务描述:\n{task.description}"
        return "认领失败"
    return _claim_task


def make_complete_task_handler(task_manager, context: AgentContext):
    """创建 complete_task 处理器。"""
    async def _complete_task(task_id: str, result: str) -> str:
        from agent_team.tasks import TaskStatus
        task = task_manager.get_task(task_id)
        if not task:
            return f"错误: 任务 {task_id} 不存在"
        if task.status != TaskStatus.IN_PROGRESS:
            return (
                f"⛔ 任务 '{task.name}' 状态是 '{task.status.value}'，不能直接完成。\n"
                f"请先用 claim_task 认领此任务，再 complete_task。"
            )
        agent_name = context.agent_name
        all_tasks = task_manager.list_tasks()
        outstanding = [
            t for t in all_tasks
            if t.description and f"由 {agent_name} 发布:" in (t.description or "")
            and t.status.value in ("pending", "in_progress")
        ]
        if outstanding:
            names = ", ".join(f"{t.name}({t.status.value})" for t in outstanding)
            return (
                f"⚠️ 你还有 {len(outstanding)} 个未完成的已发布子任务:\n{names}\n"
                f"等它们完成后用 list_tasks 确认，再 complete_task。"
            )
        ok = task_manager.update_task_status(task_id, TaskStatus.COMPLETED, result)
        if ok:
            context.current_task_id = ""
            return f"任务 {task_id} 已标记为完成"
        return f"无法完成任务 {task_id}"
    return _complete_task


def make_fail_task_handler(task_manager, context: AgentContext):
    """创建 fail_task 处理器。"""
    def _fail_task(task_id: str, reason: str) -> str:
        from agent_team.tasks import TaskStatus
        ok = task_manager.update_task_status(task_id, TaskStatus.FAILED, reason)
        if ok:
            context.current_task_id = ""
            return f"任务 {task_id} 已标记为失败: {reason}"
        return f"无法将任务 {task_id} 标记为失败"
    return _fail_task


def make_send_message_handler(mailbox, context: AgentContext, agents_dict: dict = None):
    """创建 send_message 处理器。"""
    def _send_message(subject: str, content: str, recipient: str = "") -> str:
        if recipient.strip():
            known_names = {a.name for a in (agents_dict or {}).values()}
            if recipient.strip() not in known_names:
                name_list = ", ".join(sorted(known_names)) if known_names else "(无)"
                return (
                    f"⛔ 收件人 '{recipient}' 不存在。可用收件人: {name_list}\n"
                    f"请用 list_agents 查看正确的名称后重新发送。"
                )
            msg = mailbox.send(context.agent_name, recipient.strip(), subject, content)
            return f"消息已发送给 {recipient} (id: {msg.id})"
        else:
            msg = mailbox.broadcast(context.agent_name, subject, content)
            return f"已广播给全体成员 (id: {msg.id})"
    return _send_message


def make_check_mailbox_handler(mailbox, context: AgentContext):
    """创建 check_mailbox 处理器。"""
    def _check_mailbox() -> str:
        msgs = mailbox.receive(context.agent_name, limit=10, unread_only=True)
        if not msgs:
            return "没有未读消息"
        lines = []
        for m in msgs:
            lines.append(f"[{m.sender}] {m.subject}: {m.content}")
            mailbox.mark_read(m.id)
        return "\n".join(lines)
    return _check_mailbox


def make_list_agents_handler(agents_dict: dict):
    """创建 list_agents 处理器。"""
    def _list_agents() -> str:
        if not agents_dict:
            return "团队中没有 agent"
        lines = []
        for a in agents_dict.values():
            lines.append(f"- {a.name} ({a.id}): role={a.role.value}, state={a.state.value}")
        return "\n".join(lines)
    return _list_agents


def make_list_tasks_handler(task_manager):
    """创建 list_tasks 处理器。"""
    def _list_tasks(status: str = "") -> str:
        from agent_team.tasks import TaskStatus
        st = None
        if status and status not in ("all", "All", "ALL"):
            try:
                st = TaskStatus(status)
            except ValueError:
                pass
        tasks = task_manager.list_tasks(status=st)
        if not tasks:
            return "没有任务"
        lines = []
        for t in tasks:
            deps = f" (依赖: {', '.join(t.depends_on)})" if t.depends_on else ""
            lines.append(
                f"- [{t.status.value}] {t.name} ({t.id}) 优先级={t.priority}"
                f" 分配给={t.assigned_to or '无人'}{deps}"
            )
            if t.status.value == "completed" and t.result:
                lines.append(f"  结果: {t.result[:800]}")
        return "\n".join(lines)
    return _list_tasks


def make_read_file_handler(work_dir: str):
    """创建 read_file 处理器。"""
    def _read_file(path: str) -> str:
        if not path or not path.strip():
            return (
                "⛔ read_file 缺少 path 参数。必须指定具体文件路径，如:\n"
                "read_file(path=\"project/main.py\")\n"
                "不要用空参数或目录路径(如 '.', 'project/')调用此工具——那只会返回错误。"
            )
        full = os.path.join(work_dir, path)
        if os.path.isdir(full):
            return (
                f"⛔ '{path}' 是目录，不是文件。请指定具体文件路径。\n"
                f"如需查看目录内容，使用 glob 工具。"
            )
        try:
            with open(full, encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return f"文件不存在: {path}"
        except Exception as exc:
            return f"读取错误: {exc}"
    return _read_file


def make_write_file_handler(work_dir: str, context: AgentContext):
    """创建 write_file 处理器（带角色文件类型限制）。"""
    def _write_file(path: str, content: str) -> str:
        if not path or not path.strip():
            return (
                "⛔ write_file 缺少 path 参数。必须指定文件路径，如:\n"
                "write_file(path=\"project/main.py\", content=\"...\")\n"
                "不要用空参数调用此工具。"
            )
        if not content:
            logger.warning(f"write_file called with empty content for path={path}")
        role = context.agent_role
        if role in ROLE_RESTRICTED_EXTENSIONS:
            ext = os.path.splitext(path)[1].lower()
            if ext in ROLE_RESTRICTED_EXTENSIONS[role]:
                allowed = [e for e in [".md", ".txt", ".json", ".yaml", ".yml", ".toml"]
                          if e not in ROLE_RESTRICTED_EXTENSIONS[role]]
                return (
                    f"⛔ 你的角色({role})不能写入代码文件({ext})。\n"
                    f"你只能写入文档类文件: {', '.join(allowed)}\n"
                    f"→ 不要 fail_task 就结束！请用 publish_task 将此任务转发给 executor。\n"
                    f"→ 然后 fail_task 当前任务（标注 '已转发给 executor'）。"
                )
        full = os.path.join(work_dir, path)
        os.makedirs(os.path.dirname(full) or ".", exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)
        return f"文件已写入: {path}"
    return _write_file


def make_read_task_handler(task_manager):
    """创建 read_task 处理器。"""
    def _read_task(task_id: str) -> str:
        task = task_manager.get_task(task_id)
        if not task:
            return f"错误: 任务 {task_id} 不存在"
        return (
            f"任务: {task.name}\n"
            f"状态: {task.status.value}\n"
            f"分配: {task.assigned_to or '无人'}\n"
            f"优先级: {task.priority}\n"
            f"描述:\n{task.description}\n\n"
            f"结果:\n{task.result or '(无)'}"
        )
    return _read_task


def make_submit_plan_handler(plan_manager, context: AgentContext):
    """创建 submit_plan 处理器。"""
    def _submit_plan(task_id: str, plan: str) -> str:
        if not plan_manager:
            return "此团队未启用计划审批功能"
        plan_req = plan_manager.submit(task_id, context.agent_id, context.agent_name, plan)
        context.current_plan_id = plan_req.id
        return (
            f"计划已提交 (ID: {plan_req.id})，等待用户审批。\n\n"
            f"⚠️ 审批来自用户（人类），不是队友。不要广播计划请队友审批。\n"
            f"用户在前端介入面板中看到你的计划后会批准或驳回。\n"
            f"用 check_plan_status 定期检查审批结果。"
        )
    return _submit_plan


def make_check_plan_status_handler(plan_manager, context: AgentContext):
    """创建 check_plan_status 处理器。"""
    def _check_plan_status() -> str:
        if not plan_manager:
            return "此团队未启用计划审批"
        plan = plan_manager.get_pending_for_agent(context.agent_id)
        if not plan:
            return "没有待审批的计划。如果你之前提交了，可能已经被处理了。"
        if plan.status.value == "pending":
            return f"计划 {plan.id} 仍在等待审批。"
        elif plan.status.value == "approved":
            return f"计划 {plan.id} 已批准。反馈: {plan.feedback or '无'}。继续执行。"
        elif plan.status.value == "rejected":
            return f"计划 {plan.id} 被驳回。原因: {plan.feedback}。请修改后重新提交。"
        return f"未知的计划状态: {plan.status.value}"
    return _check_plan_status


def make_respond_to_shutdown_handler(context: AgentContext):
    """创建 respond_to_shutdown 处理器。"""
    def _respond_to_shutdown(accept: bool, reason: str) -> str:
        if context.shutdown_response is not None:
            return "已记录关闭响应，请勿重复调用。"
        context.shutdown_response = (accept, reason)
        if accept:
            return f"已同意关闭: {reason}"
        return f"已拒绝关闭: {reason}"
    return _respond_to_shutdown


def make_publish_task_handler(task_manager, context: AgentContext):
    """创建 publish_task 处理器。"""
    _published_task_ids: set = set()

    def _publish_task(name: str, description: str, priority: int = 2,
                      depends_on: list[str] | None = None) -> str:
        if len(description.strip()) < 20:
            return (
                f"⚠️ 任务描述太短（{len(description)}字），可能被截断。\n"
                f"请重新 publish_task，确保 description 包含:\n"
                f"- 该任务的具体内容和验收标准\n"
                f"- 建议由什么能力的成员认领\n"
                f"- 相关文件路径（如适用）"
            )
        truncation_warning = ""
        if description.rstrip().endswith(("...", "…", "等等", "等")) or len(description) > 1500:
            truncation_warning = (
                "⚠️ 任务描述很长(>1500字)或末尾有截断标记，建议拆分为多个更简短的任务。\n\n"
            )
        dep_ids = []
        if depends_on:
            all_tasks = task_manager.list_tasks()
            for dep_name in depends_on:
                dep_name = dep_name.strip()
                matched = None
                for t in all_tasks:
                    if t.name == dep_name:
                        matched = t
                        break
                if not matched:
                    candidates = [t for t in all_tasks if t.name.startswith(dep_name)]
                    if len(candidates) == 1:
                        matched = candidates[0]
                if not matched:
                    candidates = [t for t in all_tasks if dep_name in t.name]
                    if len(candidates) == 1:
                        matched = candidates[0]
                    elif len(candidates) > 1:
                        return (
                            f"⚠️ 依赖匹配失败: 任务名 '{dep_name}' 匹配到 {len(candidates)} 个任务。\n"
                            f"请用更精确的任务名，或先用 list_tasks 查看完整任务列表。\n"
                            f"匹配到的任务: {', '.join(t.name for t in candidates[:5])}"
                        )
                if matched:
                    dep_ids.append(matched.id)
                else:
                    return (
                        f"⚠️ 依赖匹配失败: 找不到名为 '{dep_name}' 的任务。\n"
                        f"请先用 list_tasks 查看所有任务，确认依赖任务的确切名称。"
                    )
        task = task_manager.create_task(
            name=name,
            description=(f"由 {context.agent_name} 发布:\n\n{description}"),
            priority=max(1, min(priority, 4)),
            depends_on=dep_ids if dep_ids else None,
            metadata={"published_by": context.agent_name},
        )
        _published_task_ids.add(task.id)
        context.last_published_for_task = context.current_task_id
        dep_info = f"  依赖: {', '.join(depends_on)}" if depends_on else ""
        return (
            f"{truncation_warning}"
            f"任务已发布: {task.name} ({task.id})\n"
            f"优先级: {task.priority}  |  描述: {len(description)} 字{dep_info}\n\n"
            f"💡 任务通过 list_tasks 查看（不是 check_mailbox）。\n"
            f"其他智能体用 list_tasks 看到后 claim_task 认领。"
        )
    return _publish_task


def make_fork_agent_handler(fork_callback, context: AgentContext):
    """创建 fork_agent 处理器。"""
    async def _fork_agent(name: str, role: str, reason: str) -> str:
        if not fork_callback:
            return "Fork 功能不可用 — 未配置 fork 回调。"
        try:
            result = await fork_callback(
                parent_agent_id=context.agent_id,
                parent_agent_name=context.agent_name,
                name=name,
                role=role,
                reason=reason,
            )
            return result
        except Exception as exc:
            return f"Fork 失败: {exc}"
    return _fork_agent
