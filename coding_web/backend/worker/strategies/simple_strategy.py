"""SimpleStrategy — 单个 Specialist 智能体解决问题。"""

from pathlib import Path

from agent_team import AgentRole
from .base import RunStrategy
from ..team_definitions import AGENT_DEFINITIONS


class SimpleStrategy(RunStrategy):
    """单智能体模式：一个 Specialist 认领任务 → 编码 → 完成。"""

    def __init__(self, model: str, max_tokens: int, task_title: str, problem: str):
        self.model = model
        self.max_tokens = max_tokens
        self.task_title = task_title
        self.problem = problem

    async def execute(self, sandbox_path: Path, orch, console, provider,
                      lifecycle, waiter) -> dict:
        project_dir = sandbox_path / "project"

        # TEAM.md
        (project_dir / "TEAM.md").write_text(
            f"# 单人模式\nclaim_task → write_file → complete_task，一遍过\n",
            encoding="utf-8",
        )

        # 注册 agent + 创建任务
        simple_def = AGENT_DEFINITIONS["simple"]
        orch.register_agent(
            agent_id=simple_def["id"], name=simple_def["name"],
            role=AgentRole.SPECIALIST, capabilities=simple_def["capabilities"],
        )
        console.register_agent_meta(simple_def["id"], simple_def["name"], "specialist")
        orch.task_manager.create_task(
            name=f"Solve: {self.task_title}",
            description=f"{self.problem}\n\nclaim_task → write_file → complete_task，一遍过",
            priority=2,
        )

        # 启动
        agent_id = simple_def["id"]
        console.agent_start(simple_def["name"], self.model or provider.default_model)
        orch.spawn_llm_agent(agent_id, model=self.model or provider.default_model,
                             provider=provider, max_tokens=self.max_tokens)
        lifecycle.setup_memory(orch, agent_id)
        await lifecycle.register_execute_tool(orch, agent_id)
        lifecycle.register_file_tools(orch, agent_id)

        # 等待完成
        wait_result = await waiter.wait_for_completion(orch, [agent_id])
        success = wait_result["ok"]

        # 关闭
        await lifecycle.safe_shutdown(orch, agent_id, console)

        return self._build_result(orch, sandbox_path, success, wait_result)

    def _build_result(self, orch, sandbox_path, success, wait_result) -> dict:
        from ..result_extractor import ResultExtractor
        answer = ResultExtractor.extract_answer(orch, sandbox_path)
        if wait_result["failed_tasks"]:
            answer = f"[部分任务未完成: {', '.join(wait_result['failed_tasks'])}]\n\n{answer}"
        return {
            "success": success,
            "answer": answer,
            "error": "",
            "stats": orch.get_team_stats(),
        }
