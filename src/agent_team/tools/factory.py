"""create_default_registry() — 组装 15 个工具到 ToolRegistry。

每个处理器通过 handlers.py 中的工厂函数创建，使用 AgentContext 传递智能体身份。
"""

from .registry import ToolRegistry, AgentContext
from .schemas import (
    CLAIM_TASK_SCHEMA, COMPLETE_TASK_SCHEMA, FAIL_TASK_SCHEMA,
    SEND_MESSAGE_SCHEMA, CHECK_MAILBOX_SCHEMA,
    LIST_AGENTS_SCHEMA, LIST_TASKS_SCHEMA,
    READ_FILE_SCHEMA, READ_TASK_SCHEMA, WRITE_FILE_SCHEMA,
    SUBMIT_PLAN_SCHEMA, CHECK_PLAN_STATUS_SCHEMA,
    RESPOND_TO_SHUTDOWN_SCHEMA, FORK_AGENT_SCHEMA, PUBLISH_TASK_SCHEMA,
)
from .capabilities import BASE_TOOLS
from .handlers import (
    make_claim_task_handler,
    make_complete_task_handler,
    make_fail_task_handler,
    make_send_message_handler,
    make_check_mailbox_handler,
    make_list_agents_handler,
    make_list_tasks_handler,
    make_read_file_handler,
    make_write_file_handler,
    make_read_task_handler,
    make_submit_plan_handler,
    make_check_plan_status_handler,
    make_respond_to_shutdown_handler,
    make_publish_task_handler,
    make_fork_agent_handler,
)


def create_default_registry(task_manager, mailbox, agents_dict,
                            work_dir: str = ".",
                            plan_manager=None,
                            notification_bus=None,
                            fork_callback=None,
                            tools_allowlist=None) -> ToolRegistry:
    """创建包含所有默认工具的 ToolRegistry。

    Args:
        task_manager: TaskManager 实例
        mailbox: AgentMailbox 实例
        agents_dict: {agent_id: Agent} 字典，由 Orchestrator 维护
        work_dir: 文件操作的工作目录
        plan_manager: 可选的 PlanManager，用于 submit_plan/check_plan_status 工具
        notification_bus: 可选的 NotificationBus，用于推送通知
        fork_callback: 可选的回调 async def fork_callback(...) -> str
        tools_allowlist: 可选，允许的工具名集合。None = 全部可用。
    """
    registry = ToolRegistry()
    context = registry.context  # AgentContext 实例

    # 注册所有工具的 schema + handler
    registry.register(CLAIM_TASK_SCHEMA,
                      make_claim_task_handler(task_manager, context, agents_dict))
    registry.register(COMPLETE_TASK_SCHEMA,
                      make_complete_task_handler(task_manager, context))
    registry.register(FAIL_TASK_SCHEMA,
                      make_fail_task_handler(task_manager, context))
    registry.register(SEND_MESSAGE_SCHEMA,
                      make_send_message_handler(mailbox, context, agents_dict))
    registry.register(CHECK_MAILBOX_SCHEMA,
                      make_check_mailbox_handler(mailbox, context))
    registry.register(LIST_AGENTS_SCHEMA,
                      make_list_agents_handler(agents_dict))
    registry.register(LIST_TASKS_SCHEMA,
                      make_list_tasks_handler(task_manager))
    registry.register(READ_FILE_SCHEMA,
                      make_read_file_handler(work_dir))
    registry.register(WRITE_FILE_SCHEMA,
                      make_write_file_handler(work_dir, context))
    registry.register(READ_TASK_SCHEMA,
                      make_read_task_handler(task_manager))
    registry.register(SUBMIT_PLAN_SCHEMA,
                      make_submit_plan_handler(plan_manager, context))
    registry.register(CHECK_PLAN_STATUS_SCHEMA,
                      make_check_plan_status_handler(plan_manager, context))
    registry.register(RESPOND_TO_SHUTDOWN_SCHEMA,
                      make_respond_to_shutdown_handler(context))
    registry.register(PUBLISH_TASK_SCHEMA,
                      make_publish_task_handler(task_manager, context))
    registry.register(FORK_AGENT_SCHEMA,
                      make_fork_agent_handler(fork_callback, context))

    # ── 工具白名单过滤 ──
    if tools_allowlist is not None:
        allowed = set(tools_allowlist) | BASE_TOOLS
        for name in list(registry._schemas.keys()):
            if name not in allowed:
                del registry._schemas[name]
                del registry._handlers[name]

    return registry
