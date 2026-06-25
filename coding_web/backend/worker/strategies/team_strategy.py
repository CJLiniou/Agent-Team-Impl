"""TeamStrategy — Architect → Coders → Reviewer 三阶段流水线。"""

import re
from pathlib import Path

from agent_team import AgentRole, AgentState, HookEvent
from .base import RunStrategy
from ..team_definitions import AGENT_DEFINITIONS, CODER_NAMES
from ..result_extractor import ResultExtractor


class TeamStrategy(RunStrategy):
    """标准团队模式：1 Architect + N Coders + 1 Reviewer。"""

    def __init__(self, num_coders: int, model: str, max_tokens: int,
                 problem: str, task_title: str):
        self.num_coders = max(1, min(num_coders, len(CODER_NAMES)))
        self.model = model
        self.max_tokens = max_tokens
        self.problem = problem
        self.task_title = task_title

    async def execute(self, sandbox_path: Path, orch, console, provider,
                      lifecycle, waiter) -> dict:
        project_dir = sandbox_path / "project"

        ResultExtractor.write_strong_team_md(project_dir, "python", self.num_coders)

        # ── 注册 agent ──
        arch_def = AGENT_DEFINITIONS["architect"]
        orch.register_agent(
            agent_id=arch_def["id"], name=arch_def["name"],
            role=AgentRole.COORDINATOR, capabilities=arch_def["capabilities"],
        )
        console.register_agent_meta(arch_def["id"], arch_def["name"], "coordinator")

        coder_def = AGENT_DEFINITIONS["coder"]
        coder_ids = []
        for i in range(self.num_coders):
            coder_name = CODER_NAMES[i]
            agent_id = coder_def["id_template"].format(i=i + 1)
            coder_ids.append(agent_id)
            orch.register_agent(
                agent_id=agent_id,
                name=coder_def["name_template"].format(name=coder_name),
                role=AgentRole.EXECUTOR,
                capabilities=coder_def["capabilities_base"],
                metadata={"coder_index": i},
            )
            console.register_agent_meta(
                agent_id, coder_def["name_template"].format(name=coder_name), "executor",
            )

        review_def = AGENT_DEFINITIONS["reviewer"]
        orch.register_agent(
            agent_id=review_def["id"], name=review_def["name"],
            role=AgentRole.REVIEWER, capabilities=review_def["capabilities"],
            metadata={"can_publish_tasks": True},
        )
        console.register_agent_meta(review_def["id"], review_def["name"], "reviewer")

        # ── 创建任务 DAG ──
        arch_id = arch_def["id"]
        review_id = review_def["id"]

        task_design = orch.task_manager.create_task(
            name=f"Design: {self.task_title[:50]}",
            description=(
                f"需求: {self.problem}\n\n"
                f"1. 拆成 {self.num_coders} 个编码子任务\n"
                f"2. write_file('REQUIREMENTS.md', 子任务分配)\n"
                f"3. send_message 通知编码者（只发一次，不要反复提醒）\n"
                f"4. complete_task 提交，然后保持空闲——不要再干涉团队"
            ),
            priority=2, assigned_to=arch_id,
        )

        coder_task_ids = []
        for i, cid in enumerate(coder_ids):
            task = orch.task_manager.create_task(
                name=f"Implement Part {i + 1} — {CODER_NAMES[i]}",
                description=(
                    f"需求: {self.problem}\n\n"
                    f"1. claim_task 认领\n2. write_file 写代码到当前目录\n"
                    f"3. complete_task 提交（文件列表 + 简短说明）\n"
                    f"审查员可能 publish_task 发布修复 → claim → 改 → complete"
                ),
                priority=2, depends_on=[task_design.id], assigned_to=cid,
            )
            coder_task_ids.append(task.id)

        orch.task_manager.create_task(
            name="Review and Final Solution",
            description=(
                f"需求: {self.problem}\n\n"
                f"1. read_file 读 Coder 写的代码（最多 3 个文件，跳过 .md）\n"
                f"2. 读完立刻决策:\n"
                f"   代码 OK → complete_task('审查通过')\n"
                f"   有问题 → publish_task('修复: <问题>', description='文件+问题+期望修复')"
            ),
            priority=2, depends_on=coder_task_ids, assigned_to=review_id,
        )

        # ── Hook: Architect 完成时更新 Coder 任务描述 ──
        orch.hook_registry.register(
            HookEvent.TASK_COMPLETED,
            self._make_coder_update_hook(orch, console, coder_task_ids),
        )

        # ── 启动所有 agent ──
        model = self.model or provider.default_model
        all_agent_ids = [arch_id] + coder_ids + [review_id]

        # Architect（预认领 Design 任务）
        console.agent_step(arch_def["name"], "Starting...")
        orch.spawn_llm_agent(arch_id, model=model, provider=provider, max_tokens=self.max_tokens)
        life_mem = lifecycle.setup_memory(orch, arch_id)
        orch.task_manager.claim_task(task_design.id, arch_id)
        llm = orch._llm_agents.get(arch_id)
        if llm:
            llm.tool_registry.context.current_task_id = task_design.id
            orch.agents[arch_id].state = AgentState.BUSY
            orch.agents[arch_id].current_task_id = task_design.id
        if life_mem:
            life_mem.add_note(content=f"认领设计任务: {task_design.name}", tags="claim_task")
        await lifecycle.register_execute_tool(orch, arch_id)
        lifecycle.register_file_tools(orch, arch_id)

        # Coders
        for cid in coder_ids:
            orch.spawn_llm_agent(cid, model=model, provider=provider, max_tokens=self.max_tokens)
            lifecycle.setup_memory(orch, cid)
            await lifecycle.register_execute_tool(orch, cid)
            lifecycle.register_file_tools(orch, cid)

        # Reviewer
        review_task = None
        for t in orch.task_manager.list_tasks():
            if "Review" in t.name and t.assigned_to == review_id:
                review_task = t
                break
        if review_task and review_task.status.value == "pending":
            ResultExtractor.update_task_description(
                orch.task_manager.db_path, review_task.id,
                f"需求: {self.problem}\n\n"
                "1. read_file 读 Coder 写的代码文件（最多读 3 个，不要读 .md）\n"
                "2. 读完后立刻决策，不要再反复读:\n"
                "   代码 OK → complete_task('审查通过')\n"
                "   有问题 → publish_task('修复: <问题>', description='文件+问题+期望修复')"
            )

        orch.spawn_llm_agent(review_id, model=model, provider=provider, max_tokens=self.max_tokens)
        lifecycle.setup_memory(orch, review_id)
        await lifecycle.register_execute_tool(orch, review_id)
        lifecycle.register_file_tools(orch, review_id)

        # ── 等待 + 关闭 ──
        waiter._update_task_fn = ResultExtractor.update_task_description
        wait_result = await waiter.wait_for_completion(orch, all_agent_ids)
        success = wait_result["ok"]

        if not success and wait_result["timed_out"]:
            if all("Review" in t for t in wait_result["failed_tasks"]):
                success = True

        for aid in all_agent_ids:
            await lifecycle.safe_shutdown(orch, aid, console)

        return self._build_result(orch, sandbox_path, success, wait_result)

    # ── 内部: Coder 任务更新 Hook ────────────────────────────────

    def _make_coder_update_hook(self, orch, console, coder_task_ids: list[str]):
        """当 Architect 完成时，更新 Coder 任务描述。"""
        def on_task_complete(ctx):
            task_name = getattr(ctx, 'task_name', '')
            if "Design" not in task_name:
                return None
            result = getattr(ctx, 'task_result', '') or ''
            if not result.strip():
                return None

            sub_problems = self._parse_sub_problems(result)
            db_path = orch.task_manager.db_path

            for i, task_id in enumerate(coder_task_ids):
                if sub_problems and i < len(sub_problems):
                    sub = sub_problems[i]
                    desc = (
                        f"=== 你的编码任务 ===\n"
                        f"标题: {sub['title']}\n\n{sub['description']}\n\n"
                        f"=== 原始问题 ===\n{self.problem}\n=== 结束 ===\n\n"
                        f"用 write_file 实现干净、地道的代码\n"
                        f"⛔  write_file 之后立刻 complete_task\n"
                        f"✅  write_file → complete_task，一遍过"
                    )
                else:
                    desc = (
                        f"=== 方案设计 ===\n{result}\n=== 结束 ===\n\n"
                        f"=== 原始问题 ===\n{self.problem}\n=== 结束 ===\n\n"
                        f"你是第 {i + 1} 号编码者。实现上面设计方案的第 {i + 1} 部分\n"
                        f"用 write_file 创建实现文件\n"
                        f"⛔  write_file 之后立刻 complete_task，不要重读重写\n"
                        f"✅  write_file → complete_task，一遍过"
                    )
                ResultExtractor.update_task_description(db_path, task_id, desc)

            console.agent_step("System", f"Updated {len(coder_task_ids)} coder task descriptions")
            return None
        return on_task_complete

    @staticmethod
    def _parse_sub_problems(result: str) -> list[dict]:
        """解析 Architect 结果中的子问题。"""
        pattern = r'###\s*(?:SUB_PROBLEM|子任务)[:\s]+(.+?)(?=###\s*(?:SUB_PROBLEM|子任务)|###\s*$|$)'
        matches = re.findall(pattern, result, re.DOTALL | re.IGNORECASE)
        if matches:
            sub_problems = []
            for match in matches:
                lines = match.strip().split("\n", 1)
                title = lines[0].strip()
                description = lines[1].strip() if len(lines) > 1 else title
                sub_problems.append({"title": title, "description": description})
            return sub_problems
        return []

    def _build_result(self, orch, sandbox_path, success, wait_result) -> dict:
        answer = ResultExtractor.extract_answer(orch, sandbox_path)
        if wait_result["failed_tasks"]:
            answer = f"[部分任务未完成: {', '.join(wait_result['failed_tasks'])}]\n\n{answer}"
        return {
            "success": success,
            "answer": answer,
            "error": "",
            "stats": orch.get_team_stats(),
        }
