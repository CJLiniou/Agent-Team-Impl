"""Agent 生命周期管理器 — 工具注册、记忆设置、安全关闭。

从 runner.py 中提取。每个方法操作单个 (orch, agent_id) 对。
"""

import asyncio
import logging

from agent_team import AgentState

logger = logging.getLogger(__name__)

# 状态查询工具（upsert——只保留最新记录，不堆积历史）
UPSERT_TOOLS = {"list_tasks", "check_mailbox", "list_agents", "check_plan_status"}

# 关键事件类型 — 在记忆上下文中展示为摘要
KEY_EVENT_TYPES = {
    "task_started", "task_completed", "task_failed",
    "task_published", "message_sent", "messages_read",
    "error", "agent_forked",
}

EVENT_ICONS = {
    "task_started": "▶", "task_completed": "✅", "task_failed": "❌",
    "task_published": "📤", "task_claimed": "📥",
    "file_read": "👁", "file_written": "✏",
    "message_sent": "💬", "messages_read": "📬",
    "waiting": "⏳", "error": "⚠", "agent_forked": "🔀",
}


class AgentLifecycleManager:
    """管理单个 Agent 的完整生命周期：工具注册、记忆、关闭。"""

    def __init__(self, task_id: str, sandbox_root):
        self.task_id = task_id
        self.sandbox_root = sandbox_root
        self._memories: dict[str, object] = {}  # agent_id → AgentMemoryService

    # ── 公共接口 ──────────────────────────────────────────────────

    def get_memory(self, agent_id: str):
        """获取已创建的 agent 记忆实例。"""
        return self._memories.get(agent_id)

    async def register_execute_tool(self, orch, agent_id: str) -> None:
        """向 agent 的工具注册表添加 execute_code 工具。"""
        from ..services.docker_sandbox import get_docker_sandbox

        llm_agent = orch._llm_agents.get(agent_id)
        if not llm_agent:
            return
        registry = llm_agent.tool_registry

        ds = get_docker_sandbox()
        project_dir = self._resolve_project_dir()
        tid = self.task_id

        if ds.docker_available and tid not in ds._containers:
            await ds.create_container(tid, project_dir)

        sandbox_root_str = str(self.sandbox_root).replace("\\", "/")
        project_dir_str = str(project_dir).replace("\\", "/")

        async def _handle_execute_code(command: str, workdir: str = "/workspace", timeout: int = 30) -> str:
            import re as _re
            sanitized = command.replace("\\", "/")
            # 去掉 Agent 传的 Windows 路径 cd 命令 — workdir 已由 ds.execute 内部设置
            sanitized = _re.sub(r'cd\s+["\']?[^;&|]+["\']?\s*(&&\s*)?', '', sanitized)
            # 路径转换：Windows 沙盒路径 → /workspace（Docker 模式）
            if ds.docker_available and tid in ds._containers:
                sanitized = sanitized.replace(project_dir_str, "/workspace")
                sanitized = sanitized.replace(sandbox_root_str + "/" + tid, "/workspace")

            result = await ds.execute(tid, sanitized, "/workspace", min(timeout, 60))
            if result["success"]:
                return (
                    f"✅ 执行成功 (exit_code={result['exit_code']}, method={result['method']})\n\n"
                    f"--- STDOUT ---\n{result['stdout']}\n"
                    f"{'--- STDERR ---\n' + result['stderr'] if result['stderr'] else ''}"
                )
            else:
                return (
                    f"❌ 执行失败 (exit_code={result['exit_code']}, method={result['method']})\n\n"
                    f"--- STDOUT ---\n{result['stdout']}\n"
                    f"--- STDERR ---\n{result['stderr']}"
                )

        registry.register(self.EXECUTE_CODE_SCHEMA, _handle_execute_code)
        logger.info(f"execute_code tool registered for agent {agent_id}")

    def register_file_tools(self, orch, agent_id: str) -> None:
        """向 agent 注册 glob 和 grep 工具。"""
        import re
        import fnmatch

        llm_agent = orch._llm_agents.get(agent_id)
        if not llm_agent:
            return
        registry = llm_agent.tool_registry

        project_dir = self._resolve_project_dir()

        # ── Glob handler ──
        def _handle_glob(pattern: str, path: str = "project") -> str:
            search_dir = self.sandbox_root / self.task_id / path if path != "project" else project_dir
            if not search_dir.exists():
                search_dir = project_dir
            try:
                matches = sorted(search_dir.rglob(pattern))
                matches = [
                    m for m in matches
                    if not any(part.startswith(".") for part in m.relative_to(search_dir).parts)
                    and "node_modules" not in str(m)
                    and "__pycache__" not in str(m)
                    and "team.db" not in str(m)
                ]
                if not matches:
                    return f"glob('{pattern}'): 没有匹配的文件"
                lines = [f"glob('{pattern}') — {len(matches)} 个文件:"]
                for m in matches[:50]:
                    rel = str(m.relative_to(search_dir)).replace("\\", "/")
                    size = m.stat().st_size if m.is_file() else 0
                    tag = "/" if m.is_dir() else f" ({_format_size(size)})"
                    lines.append(f"  {rel}{tag}")
                if len(matches) > 50:
                    lines.append(f"  ... 还有 {len(matches) - 50} 个文件")
                return "\n".join(lines)
            except Exception as exc:
                return f"glob 错误: {exc}"

        # ── Grep handler ──
        def _handle_grep(pattern: str, glob: str = "", path: str = "project") -> str:
            search_dir = self.sandbox_root / self.task_id / path if path != "project" else project_dir
            if not search_dir.exists():
                search_dir = project_dir

            try:
                regex = re.compile(pattern)
            except re.error as exc:
                return f"grep 正则错误: {exc}"

            if glob:
                files = list(search_dir.rglob(glob))
            else:
                code_exts = {".py", ".ts", ".tsx", ".js", ".jsx", ".rs", ".go",
                             ".java", ".cpp", ".c", ".h", ".hpp", ".html", ".css",
                             ".json", ".yaml", ".yml", ".toml", ".md", ".txt"}
                files = [f for f in search_dir.rglob("*") if f.suffix in code_exts]

            files = [
                f for f in files
                if f.is_file()
                and not any(part.startswith(".") for part in f.relative_to(search_dir).parts)
                and "node_modules" not in str(f)
                and "__pycache__" not in str(f)
                and "team.db" not in str(f)
            ]

            results: list[str] = []
            total_matches = 0
            for filepath in sorted(files)[:100]:
                try:
                    content = filepath.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue
                file_matches = []
                for i, line in enumerate(content.split("\n"), 1):
                    if regex.search(line):
                        file_matches.append((i, line.strip()[:120]))
                        total_matches += 1
                if file_matches:
                    rel = str(filepath.relative_to(search_dir)).replace("\\", "/")
                    results.append(f"\n  📄 {rel} ({len(file_matches)} 处匹配)")
                    for lineno, text in file_matches[:5]:
                        results.append(f"    {lineno}: {text}")
                    if len(file_matches) > 5:
                        results.append(f"    ... 还有 {len(file_matches) - 5} 处")

            if not results:
                return f"grep('{pattern}'): 没有匹配"
            header = f"grep('{pattern}') — {total_matches} 处匹配:"
            return header + "".join(results[:60])

        from ._runner_tools import GLOB_SCHEMA, GREP_SCHEMA
        registry.register(GLOB_SCHEMA, _handle_glob)
        registry.register(GREP_SCHEMA, _handle_grep)
        logger.info(f"glob + grep tools registered for agent {agent_id}")

    def setup_memory(self, orch, agent_id: str):
        """为 agent 设置持久记忆，包裹 ToolRegistry.execute 记录所有工具调用。

        Returns: AgentMemoryService 实例（调用方可存下来用于预认领记录等）。
        """
        from ..services.agent_memory_service import AgentMemoryService

        llm_agent = orch._llm_agents.get(agent_id)
        if not llm_agent:
            return None
        registry = llm_agent.tool_registry

        memory = AgentMemoryService(self.sandbox_root, self.task_id, agent_id)
        self._memories[agent_id] = memory

        _original_execute = registry.execute

        async def _execute_with_memory(name: str, args: dict) -> str:
            result = await _original_execute(name, args)
            try:
                # 状态查询 → upsert；动作 → append
                if name in UPSERT_TOOLS:
                    memory.upsert_conversation(
                        role="tool", tool_name=name,
                        tool_input=str(args)[:300], tool_output=str(result)[:300],
                    )
                else:
                    memory.append_conversation(
                        role="tool", tool_name=name,
                        tool_input=str(args)[:300], tool_output=str(result)[:300],
                    )
                self._dispatch_memory_event(name, args, result, memory, orch)
            except Exception:
                logger.debug(f"Memory recording skipped for {name}: non-critical error", exc_info=True)
            return result

        registry.execute = _execute_with_memory

        llm_agent._memory_provider = self._build_memory_context(memory)
        logger.debug(f"Memory recording enabled for agent {agent_id[:8]}")
        return memory

    async def safe_shutdown(self, orch, agent_id: str, console,
                            timeout: float = 3.0) -> None:
        """安全关停单个 agent：优雅关闭 → 强制关闭 → 取消 asyncio task。"""
        try:
            await asyncio.wait_for(
                orch.shutdown_agent(agent_id, timeout=timeout),
                timeout=timeout + 3,
            )
        except (asyncio.TimeoutError, Exception):
            pass
        finally:
            try:
                await orch.shutdown_agent(agent_id, force=True)
            except Exception:
                pass
            agent_task = orch._llm_agent_tasks.get(agent_id)
            if agent_task and not agent_task.done():
                agent_task.cancel()
                try:
                    await agent_task
                except asyncio.CancelledError:
                    pass

        if isinstance(orch.agents, dict):
            agent = orch.agents.get(agent_id)
            if agent:
                agent.state = AgentState.IDLE
                agent.current_task_id = None
        console.team_dashboard(orch.agents, orch.task_manager.list_tasks())

    # ── 内部方法 ──────────────────────────────────────────────────

    def _resolve_project_dir(self):
        """解析沙盒 project 目录路径。"""
        project_dir = self.sandbox_root / self.task_id / "project"
        if not project_dir.exists():
            project_dir = self.sandbox_root / self.task_id
        return project_dir

    def _dispatch_memory_event(self, name: str, args: dict, result: str,
                               memory, orch) -> None:
        """根据工具名称分发到对应的记忆事件处理器。"""
        is_error = str(result).startswith(("⛔", "错误", "⚠️", "无法"))

        if name == "write_file":
            path = args.get("path", "")
            memory.track_file_change(
                file_path=path, operation="modify",
                snippet=str(args.get("content", ""))[:500],
            )
            if not is_error:
                memory.add_event("file_written", f"写入 {path}",
                                 detail=str(args.get("content", ""))[:200])

        elif name == "read_file":
            path = args.get("path", "")
            if not is_error and path:
                memory.add_event("file_read", f"读取 {path}",
                                 detail=str(result)[:200])

        elif name == "complete_task":
            task_id = args.get("task_id", "")
            task = orch.task_manager.get_task(task_id) if task_id else None
            task_name = task.name if task else task_id
            memory.record_decision(
                context=(task.description or "")[:200],
                decision=f"complete_task: {task_name}",
                reasoning=str(args.get("result", ""))[:300],
                outcome="completed",
            )
            if not is_error:
                memory.add_event("task_completed", f"完成任务: {task_name}",
                                 detail=str(args.get("result", ""))[:300], task_id=task_id)

        elif name == "fail_task":
            task_id = args.get("task_id", "")
            task = orch.task_manager.get_task(task_id) if task_id else None
            task_name = task.name if task else task_id
            reason = str(args.get("reason", ""))[:200]
            memory.record_decision(
                context=(task.description or "")[:200],
                decision=f"fail_task: {task_name}",
                reasoning=reason, outcome="failed",
            )
            memory.add_event("task_failed", f"任务失败: {task_name}",
                             detail=reason, task_id=task_id)

        elif name == "claim_task":
            if "已认领" in str(result):
                task_id = args.get("task_id", "")
                task = orch.task_manager.get_task(task_id) if task_id else None
                task_name = task.name if task else (task_id or "自动分配")
                memory.add_note(content=f"认领: {str(result)[:200]}", tags="claim_task")
                memory.add_event("task_started", f"开始处理: {task_name}",
                                 detail=str(result)[:200], task_id=task_id)

        elif name == "publish_task":
            pub_name = args.get("name", "")
            memory.add_note(
                content=f"发布: {pub_name}\n{str(args.get('description', ''))[:300]}",
                tags="publish_task",
            )
            if not is_error:
                memory.add_event("task_published", f"发布任务: {pub_name}",
                                 detail=str(args.get("description", ""))[:200])

        elif name == "send_message":
            recipient = args.get("recipient", "") or "全体"
            subject = args.get("subject", "")[:80]
            if not is_error:
                memory.add_event("message_sent",
                                 f"→ {recipient}: {subject}",
                                 detail=str(args.get("content", ""))[:200])

        elif name == "check_mailbox":
            if "没有未读" not in str(result) and "没有消息" not in str(result):
                memory.add_event("messages_read", f"收到新消息", detail=str(result)[:300])

        elif name == "list_tasks":
            if "没有任务" in str(result):
                memory.add_event("waiting", "等待新任务...", detail="当前无可用任务")

        elif name == "fork_agent":
            child = args.get("name", "")
            if not is_error and "失败" not in str(result):
                memory.add_event("agent_forked", f"Fork 子智能体: {child}",
                                 detail=str(args.get("reason", ""))[:200])

    @staticmethod
    @staticmethod
    def _build_memory_context(memory):
        """构建注入到 LLM prompt 的记忆上下文回调函数。"""
        def _memory_context() -> str:
            try:
                parts = []

                events = memory.get_events(limit=40)
                if events:
                    # 关键事件摘要
                    key_lines = []
                    for e in events:
                        if e["event_type"] not in KEY_EVENT_TYPES:
                            continue
                        ts = e.get("created_at", "")[11:19]
                        summary = e.get("summary", "")
                        icon = EVENT_ICONS.get(e["event_type"], "")
                        key_lines.append(f"{icon} [{ts}] {summary}")
                    if key_lines:
                        parts.append("## 🔑 关键事件\n" + "\n".join(key_lines[-15:]))

                    # 完整时间线
                    lines = []
                    for e in events[-30:]:
                        ts = e.get("created_at", "")[11:19]
                        etype = e["event_type"]
                        summary = e.get("summary", "")
                        detail = e.get("detail", "")
                        icon = EVENT_ICONS.get(etype, "•")
                        line = f"{icon} [{ts}] {summary}"
                        if detail and etype in ("task_started", "task_completed",
                                                 "task_failed", "task_published",
                                                 "message_sent", "file_read"):
                            line += f"\n   {detail[:120]}"
                        lines.append(line)
                    parts.append(
                        "## 📋 完整时间线\n" + "\n".join(lines) +
                        "\n\n⚠️ 已完成的不要重复。读过的文件直接用记忆中的内容。"
                    )

                decisions = memory.get_decisions(limit=5)
                if decisions:
                    parts.append("## 最近决策\n" + "\n".join(
                        f"- {d['decision'][:200]}" for d in decisions
                    ))

                file_changes = memory.get_file_changes(limit=15)
                if file_changes:
                    parts.append("## 最近文件变更\n" + "\n".join(
                        f"- {fc['operation']}: {fc['file_path']}" for fc in file_changes
                    ))

                return "\n\n".join(parts) if parts else ""
            except Exception:
                logger.warning("Failed to build memory context for agent", exc_info=True)
                return ""

        return _memory_context

    # ── execute_code schema ───────────────────────────────────────

    EXECUTE_CODE_SCHEMA = {
        "name": "execute_code",
        "description": (
            "在沙盒环境中执行 Shell 命令并获取输出。"
            "命令在项目根目录下执行，直接写 'python main.py' 即可，"
            "无需 cd 或指定完整路径。workdir 留空即可。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "要执行的 Shell 命令，如 'python main.py'、'npm test'。不要加 cd，不要用完整路径。",
                },
                "workdir": {
                    "type": "string",
                    "description": "留空。工作目录已自动设为项目根目录。",
                },
                "timeout": {
                    "type": "integer",
                    "description": "超时秒数，默认 30",
                },
            },
            "required": ["command"],
        },
    }


def _format_size(size: int) -> str:
    """格式化文件大小（内部辅助）。"""
    for unit in ["B", "KB", "MB"]:
        if size < 1024:
            return f"{size}{unit}"
        size //= 1024
    return f"{size}GB"
