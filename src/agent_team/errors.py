"""统一异常层次结构 — 替代裸 except Exception: pass。

用法:
    from agent_team.errors import TaskClaimError, ShutdownError
    raise TaskClaimError(task_id="task-1")
"""


class AgentTeamError(Exception):
    """所有 agent_team 异常的基类。"""
    pass


class TaskClaimError(AgentTeamError):
    """任务认领失败（已被其他 Agent 认领或状态已变更）。"""
    def __init__(self, task_id: str = "", reason: str = ""):
        self.task_id = task_id
        self.reason = reason
        msg = f"Task claim failed: {task_id} - {reason}" if task_id else f"Task claim failed: {reason}"
        super().__init__(msg)


class PlanRejectedError(AgentTeamError):
    """计划被驳回。"""
    def __init__(self, plan_id: str = "", reason: str = ""):
        self.plan_id = plan_id
        self.reason = reason
        super().__init__(f"Plan rejected: {plan_id} - {reason}")


class ShutdownError(AgentTeamError):
    """Agent 关机相关错误。"""
    def __init__(self, agent_id: str = "", reason: str = ""):
        self.agent_id = agent_id
        self.reason = reason
        super().__init__(f"Shutdown failed: {agent_id} - {reason}")


class ToolExecutionError(AgentTeamError):
    """工具执行失败。"""
    def __init__(self, tool_name: str = "", detail: str = ""):
        self.tool_name = tool_name
        self.detail = detail
        super().__init__(f"Tool '{tool_name}' failed: {detail}")


class ProviderError(AgentTeamError):
    """LLM Provider 错误。"""
    pass


class RateLimitError(ProviderError):
    """LLM API 限流错误。"""
    def __init__(self, provider: str = "", retry_after: float = 0):
        self.provider = provider
        self.retry_after = retry_after
        super().__init__(f"Rate limited by {provider}, retry after {retry_after}s")
