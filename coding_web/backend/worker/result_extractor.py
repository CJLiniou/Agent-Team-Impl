"""结果提取器 — 从 orchestrator 中提取最终答案、生成 TEAM.md、更新任务描述。

从 runner.py 中提取的无状态工具函数。
"""

import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)


class ResultExtractor:
    """从已完成的任务中提取答案，以及相关的文件生成工具。"""

    @staticmethod
    def extract_answer(orch, sandbox_path: Path) -> str:
        """从完成的任务中提取最终答案。

        优先级：Review/Solve 任务 > 任意完成的任务 > final_answer.md 文件。
        """
        tasks = orch.task_manager.list_tasks()

        for task in tasks:
            if ("Review" in task.name or "Solve" in task.name) and task.status.value == "completed" and task.result:
                return task.result

        for task in tasks:
            if task.status.value == "completed" and task.result and "Design" not in task.name:
                return task.result

        final_path = sandbox_path / "project" / "final_answer.md"
        if final_path.exists():
            return final_path.read_text(encoding="utf-8")

        return "No solution was produced."

    @staticmethod
    def write_strong_team_md(project_dir: Path, language: str, num_coders: int) -> None:
        """写 TEAM.md — 中文指令，描述预创建任务流水线。"""
        content = f"""# 编码智能体团队

语言: {language}  |  模式: 团队协作  |  成员: 1 架构师 + {num_coders} 编码者 + 1 审查员

## ⚠️ 重要：任务已预创建！

所有任务已经由系统创建好了，挂在任务池中。你只需要认领属于你的任务并完成它。
**不要 publish_task 创建新任务！** 架构师用 complete_task 提交设计方案，
系统会自动更新编码者的任务描述。

## 工作流水线: 架构师 → 编码者 → 审查员

- **CodeArchitect(架构师)**: claim_task 认领 "Design:" 任务 → 分析需求 → 用 complete_task 提交子任务拆分方案
- **Coder(编码者)**: 等架构师完成后 → claim_task 认领 "Implement" 任务 → write_file 写代码 → complete_task
- **CodeReviewer(审查员)**: 等编码者完成后 → claim_task 认领 "Review" 任务 → read_file 检查 → 通过则 complete_task，有问题则 send_message

## 核心规则

1. **先 claim_task 认领任务** — 不要 publish_task，任务已存在
2. **一个任务一次完成** — claim → 执行 → complete_task
3. **文件直接写在当前目录** — 用 write_file 创建实现文件
4. **积极沟通** — 用 send_message 和 check_mailbox 与队友交流
5. **禁止死循环** — 同一操作 3 次无进展就发消息求助
"""
        (project_dir / "TEAM.md").write_text(content, encoding="utf-8")

    @staticmethod
    def update_task_description(db_path, task_id: str, new_description: str) -> None:
        """直接更新 SQLite 中的任务描述。"""
        try:
            conn = sqlite3.connect(str(db_path))
            conn.execute(
                "UPDATE tasks SET description = ? WHERE id = ?",
                (new_description, task_id),
            )
            conn.commit()
            conn.close()
        except Exception as exc:
            logger.error(f"Failed to update task {task_id}: {exc}")
