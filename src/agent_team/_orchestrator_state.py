"""StateSnapshot — 团队状态统计、结果查询、导出/导入。

从 orchestrator.py 中提取的纯查询 + 序列化方法。
"""

from datetime import datetime, timezone
from typing import Optional

from ._orchestrator_models import Agent, AgentRole, AgentState, ExecutionResult
from .tasks import TaskStatus


class StateSnapshot:
    """管理团队统计、结果过滤和状态持久化。"""

    def __init__(self, team_name: str):
        self.team_name = team_name

    def get_team_stats(self, agents: dict, task_manager, token_tracker,
                       results: list) -> dict:
        """获取团队统计，包括 token 消耗。"""
        agents_by_state = {}
        for state in AgentState:
            count = sum(1 for a in agents.values() if a.state == state)
            agents_by_state[state.value] = count

        task_stats = task_manager.get_task_stats()
        total_completed = task_stats.get('completed', 0)
        total_failed = task_stats.get('failed', 0)
        token_summary = token_tracker.team_summary()

        return {
            'team_name': self.team_name,
            'total_agents': len(agents),
            'agents_by_state': agents_by_state,
            'total_completed_tasks': total_completed,
            'total_failed_tasks': total_failed,
            'task_stats': task_stats,
            'results_recorded': len(results),
            'token_usage': token_summary,
        }

    @staticmethod
    def get_results(results: list, task_id: Optional[str] = None,
                    agent_id: Optional[str] = None,
                    status: Optional[TaskStatus] = None) -> list[ExecutionResult]:
        """获取已记录的结果，支持可选过滤。"""
        filtered = results
        if task_id:
            filtered = [r for r in filtered if r.task_id == task_id]
        if agent_id:
            filtered = [r for r in filtered if r.agent_id == agent_id]
        if status:
            filtered = [r for r in filtered if r.status == status]
        return filtered

    def export_state(self, agents: dict, results: list, task_manager) -> dict:
        """导出团队状态以便持久化。"""
        return {
            'team_name': self.team_name,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'agents': {aid: agent.to_dict() for aid, agent in agents.items()},
            'results': [r.to_dict() for r in results],
            'task_stats': task_manager.get_task_stats()
        }

    @staticmethod
    def import_state(agents: dict, state: dict) -> None:
        """从持久化数据导入团队状态。"""
        for agent_data in state.get('agents', {}).values():
            agent = Agent(
                id=agent_data['id'],
                name=agent_data['name'],
                role=AgentRole(agent_data['role']),
                capabilities=agent_data['capabilities'],
                state=AgentState(agent_data['state']),
                current_task_id=agent_data['current_task_id'],
                error_message=agent_data['error_message'],
                completed_tasks=agent_data['completed_tasks'],
                failed_tasks=agent_data['failed_tasks'],
                metadata=agent_data['metadata']
            )
            agents[agent.id] = agent
