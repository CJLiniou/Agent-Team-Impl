"""ToolRegistry — 管理工具 schema 与 handler 的注册和调用。"""

from dataclasses import dataclass, field
from typing import Callable, Optional

ToolHandler = Callable[..., str]


@dataclass
class AgentContext:
    """智能体运行时上下文 — 替代函数属性变异。

    所有工具处理器工厂通过此类型安全的数据类获取智能体身份信息，
    而非通过脆弱的多层 getattr 链。

    用法:
        ctx = AgentContext(agent_name="Coder-Alpha", agent_id="coder-0")
        handler = make_claim_task_handler(task_manager, ctx)
    """

    agent_name: str = ""
    agent_id: str = ""
    agent_role: str = ""
    current_task_id: str = ""
    current_plan_id: str = ""
    shutdown_response: tuple | None = None
    last_published_for_task: str = ""
    published_task_ids: set = field(default_factory=set)


class ToolRegistry:
    """管理工具 schema 与 handler 的注册和调用。"""

    def __init__(self):
        self._handlers: dict[str, ToolHandler] = {}
        self._schemas: dict[str, dict] = {}
        self.context: AgentContext = AgentContext()

    def register(self, schema: dict, handler: ToolHandler) -> None:
        name = schema["name"]
        self._schemas[name] = schema
        self._handlers[name] = handler

    def get_schemas(self) -> list[dict]:
        return list(self._schemas.values())

    def get_schema(self, name: str) -> Optional[dict]:
        return self._schemas.get(name)

    async def execute(self, name: str, args: dict) -> str:
        handler = self._handlers.get(name)
        if not handler:
            return f"错误: 未知工具 '{name}'"
        try:
            import asyncio
            result = handler(**args)
            if asyncio.iscoroutine(result):
                result = await result
            return str(result)
        except TypeError as e:
            return (
                f"错误: 工具 '{name}' 调用参数无效 — {e}\n"
                f"你传入的参数: {args}\n"
                f"请检查: 参数名是否正确？如 path= 而非 file_path=，content= 而非 code=。"
            )


def set_agent_context(registry: ToolRegistry, agent_name: str, agent_id: str = "",
                      agent_role: str = "") -> None:
    """将 agent 名称、ID、角色注入到注册表的 AgentContext 中。

    替代原来的函数属性变异（fn._agent_name = ...）。
    """
    registry.context.agent_name = agent_name
    registry.context.agent_id = agent_id or agent_name
    registry.context.agent_role = agent_role
