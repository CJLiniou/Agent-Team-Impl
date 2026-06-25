"""CustomTeamStrategy — 用户自定义团队配置。"""

from pathlib import Path

from agent_team import AgentRole, AgentState
from .base import RunStrategy
from ..result_extractor import ResultExtractor


class CustomTeamStrategy(RunStrategy):
    """自定义团队模式：从 TeamConfig 构建 agent 团队。"""

    def __init__(self, team_config, model: str, max_tokens: int,
                 problem: str, task_title: str, language: str):
        self.team_config = team_config
        self.model = model
        self.max_tokens = max_tokens
        self.problem = problem
        self.task_title = task_title
        self.language = language

    async def execute(self, sandbox_path: Path, orch, console, provider,
                      lifecycle, waiter) -> dict:
        project_dir = sandbox_path / "project"
        agent_defs = self._build_agent_defs()

        # 写入 TEAM.md
        lines = [
            f"# 自定义团队: {self.team_config.name}",
            f"语言: {self.language}  |  描述: {self.team_config.description}",
            "", "## 智能体:",
        ]
        for a in agent_defs:
            lines.append(f"- **{a['name']}** ({a['role']}): {', '.join(a.get('capabilities', []))}")
            if a.get("system_prompt"):
                lines.append(f"  自定义提示词: {a['system_prompt'][:100]}...")
        lines.extend(["", "## 任务", self.problem])
        (project_dir / "TEAM.md").write_text("\n".join(lines), encoding="utf-8")

        # 注册所有 agent
        agent_ids = []
        for a in agent_defs:
            role = _map_role(a["role"])
            orch.register_agent(
                agent_id=a["id"], name=a["name"], role=role,
                capabilities=a.get("capabilities", []),
                metadata={
                    "allow_fork": a.get("allow_fork", False),
                    "system_prompt_extra": a.get("system_prompt", ""),
                    "is_leader": a.get("is_leader", False),
                    "can_publish_tasks": a.get("can_publish_tasks", False) or a.get("is_leader", False),
                },
            )
            console.register_agent_meta(a["id"], a["name"], a["role"])
            agent_ids.append(a["id"])

        # Leader 驱动 vs 无 Leader
        leader = next((a for a in agent_defs if a.get("is_leader")), None)
        leader_id = leader["id"] if leader else None

        if leader:
            orch.task_manager.create_task(
                name=f"Project: {self.task_title}",
                description=(
                    f"需求: {self.problem}\n\n"
                    f"1. publish_task 发布编码任务给 executor\n"
                    f"2. 如有 reviewer，编码完成后 publish_task 发布 [审查] 任务\n"
                    f"3. list_tasks 等所有子任务完成\n"
                    f"4. send_message 广播总结\n"
                    f"5. ⚠️ complete_task 标记本项目完成"
                ),
                priority=4, assigned_to=leader_id,
            )
        else:
            for a in agent_defs:
                if a["role"] in ("executor", "specialist"):
                    orch.task_manager.create_task(
                        name=f"Task for {a['name']}",
                        description=f"需求: {self.problem}\nclaim → write_file → complete_task",
                        priority=2, assigned_to=a["id"],
                    )

        # 启动所有 agent
        for a in agent_defs:
            agent_model = a.get("model") or self.model or provider.default_model
            agent_max_tokens = a.get("max_tokens") or self.max_tokens
            agent_require_plan = a.get("require_plan_approval", False)

            console.agent_start(a["name"], agent_model)
            orch.spawn_llm_agent(
                a["id"], model=agent_model, provider=provider,
                max_tokens=agent_max_tokens,
                system_prompt_extra=a.get("system_prompt", ""),
                require_plan_approval=agent_require_plan,
            )
            lifecycle.setup_memory(orch, a["id"])
            await lifecycle.register_execute_tool(orch, a["id"])
            lifecycle.register_file_tools(orch, a["id"])

        # Leader 任务预认领
        if leader:
            leader_task_id = None
            for t in orch.task_manager.list_tasks():
                if "Project:" in t.name and t.assigned_to == leader_id:
                    leader_task_id = t.id
                    break
            if leader_task_id:
                orch.task_manager.claim_task(leader_task_id, leader_id)
                llm = orch._llm_agents.get(leader_id)
                if llm:
                    llm.tool_registry.context.current_task_id = leader_task_id
                    orch.agents[leader_id].state = AgentState.BUSY
                    orch.agents[leader_id].current_task_id = leader_task_id
                mem = lifecycle.get_memory(leader_id)
                if mem:
                    mem.add_note(content=f"认领项目任务: {leader_task_id}", tags="claim_task")
                    mem.append_conversation(
                        role="tool", tool_name="claim_task",
                        tool_input=f"task_id={leader_task_id}",
                        tool_output="已认领（预分配）",
                    )

        # 等待 + 关闭
        wait_result = await waiter.wait_for_completion(orch, agent_ids)
        success = wait_result["ok"]

        if not success and wait_result["timed_out"]:
            if all("Review" in t for t in wait_result["failed_tasks"]):
                success = True

        for aid in agent_ids:
            await lifecycle.safe_shutdown(orch, aid, console)

        answer = ResultExtractor.extract_answer(orch, sandbox_path)
        if wait_result["failed_tasks"]:
            answer = f"[部分任务未完成: {', '.join(wait_result['failed_tasks'])}]\n\n{answer}"

        return {
            "success": success,
            "answer": answer,
            "error": "",
            "stats": orch.get_team_stats(),
        }

    def _build_agent_defs(self) -> list[dict]:
        """将 TeamConfig 转换为 agent_team 兼容的 dict 列表。"""
        defs = []
        for a in self.team_config.agents:
            d = {
                "id": a.id,
                "name": a.name,
                "role": a.role or "executor",
                "capabilities": a.capabilities or [],
                "system_prompt": a.system_prompt or "",
                "model": a.model or "",
                "max_tokens": a.max_tokens or 0,
                "allow_fork": a.allow_fork,
                "fork_limit": a.fork_limit,
                "is_leader": a.is_leader,
                "can_publish_tasks": a.can_publish_tasks,
                "require_plan_approval": a.require_plan_approval,
                "tools_allowlist": a.tools_allowlist or [],
            }
            defs.append(d)
        return defs


def _map_role(role_str: str) -> AgentRole:
    """将角色字符串映射到 AgentRole 枚举。"""
    role_map = {
        "executor": AgentRole.EXECUTOR,
        "coordinator": AgentRole.COORDINATOR,
        "reviewer": AgentRole.REVIEWER,
        "specialist": AgentRole.SPECIALIST,
    }
    return role_map.get(role_str, AgentRole.EXECUTOR)
