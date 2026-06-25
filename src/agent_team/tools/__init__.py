"""工具系统 — Anthropic tool-use 格式的工具定义、注册与执行。

从 agent_team.tools 导入:

    from agent_team.tools import ToolRegistry, create_default_registry, set_agent_context
    from agent_team.tools import compute_tools_allowlist, build_system_prompt
"""

from .registry import ToolRegistry, AgentContext, set_agent_context
from .factory import create_default_registry
from .capabilities import (
    compute_tools_allowlist,
    build_system_prompt,
    build_system_prompt_from_capabilities,
    CAPABILITY_TOOLS,
    BASE_TOOLS,
    ROLE_PROMPTS,
    CAPABILITY_PROMPTS,
    LEADER_EXTRA_PROMPT,
    ROLE_CODE_EXTENSIONS,
    ROLE_WRITE_RESTRICTIONS,
)
from .schemas import (
    ALL_TOOL_SCHEMAS,
    CLAIM_TASK_SCHEMA,
    COMPLETE_TASK_SCHEMA,
    FAIL_TASK_SCHEMA,
    SEND_MESSAGE_SCHEMA,
    CHECK_MAILBOX_SCHEMA,
    LIST_AGENTS_SCHEMA,
    LIST_TASKS_SCHEMA,
    READ_FILE_SCHEMA,
    READ_TASK_SCHEMA,
    WRITE_FILE_SCHEMA,
    SUBMIT_PLAN_SCHEMA,
    CHECK_PLAN_STATUS_SCHEMA,
    RESPOND_TO_SHUTDOWN_SCHEMA,
    FORK_AGENT_SCHEMA,
    PUBLISH_TASK_SCHEMA,
)

# 支持 `from agent_team.tools import ToolHandler`
from .registry import ToolHandler
