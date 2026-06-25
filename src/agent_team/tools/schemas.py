"""工具 schema 定义 — 15 个 Anthropic tool-use 格式的工具 schema。

每个 schema 包含 name / description / input_schema。
"""

from typing import Optional


def _make_schema(name: str, description: str, properties: dict,
                 required: Optional[list[str]] = None) -> dict:
    return {
        "name": name,
        "description": description,
        "input_schema": {
            "type": "object",
            "properties": properties,
            "required": required or list(properties.keys()),
        },
    }


# ── 任务操作 ──────────────────────────────────────────────────────────

CLAIM_TASK_SCHEMA = _make_schema(
    name="claim_task",
    description="认领一个可用的待处理任务。只有依赖已满足、且未被其他 agent 认领的任务才会被返回。",
    properties={
        "task_id": {
            "type": "string",
            "description": "要认领的任务 ID。留空则自动获取优先级最高的可用任务。",
        }
    },
    required=[],
)

COMPLETE_TASK_SCHEMA = _make_schema(
    name="complete_task",
    description="标记当前任务为已完成，并记录执行结果。",
    properties={
        "task_id": {"type": "string", "description": "要完成的任务 ID"},
        "result": {"type": "string", "description": "任务执行结果摘要"},
    },
)

FAIL_TASK_SCHEMA = _make_schema(
    name="fail_task",
    description="标记当前任务为失败，并说明原因。",
    properties={
        "task_id": {"type": "string", "description": "要标记失败的任务 ID"},
        "reason": {"type": "string", "description": "失败原因"},
    },
)

SEND_MESSAGE_SCHEMA = _make_schema(
    name="send_message",
    description="向团队成员或全体广播发送消息。recipient 为空时广播给所有人。",
    properties={
        "recipient": {"type": "string", "description": "收件人名称。留空广播给所有人。"},
        "subject": {"type": "string", "description": "消息主题"},
        "content": {"type": "string", "description": "消息正文"},
    },
)

CHECK_MAILBOX_SCHEMA = _make_schema(
    name="check_mailbox",
    description="检查收件箱，返回未读消息列表。",
    properties={},
    required=[],
)

# ── 信息获取 ──────────────────────────────────────────────────────────

LIST_AGENTS_SCHEMA = _make_schema(
    name="list_agents",
    description="列出团队中所有智能体及其状态和角色。",
    properties={},
    required=[],
)

LIST_TASKS_SCHEMA = _make_schema(
    name="list_tasks",
    description="列出所有任务及其状态和依赖关系。可选按状态过滤。",
    properties={
        "status": {"type": "string", "description": "可选，按状态过滤: pending, in_progress, completed, failed, blocked"},
    },
    required=[],
)

READ_FILE_SCHEMA = _make_schema(
    name="read_file",
    description="读取指定路径的文件内容。",
    properties={
        "path": {"type": "string", "description": "相对于工作目录的文件路径"},
    },
)

READ_TASK_SCHEMA = _make_schema(
    name="read_task",
    description="读取指定任务的详细信息，包括描述和依赖。",
    properties={
        "task_id": {"type": "string", "description": "要查看的任务 ID"},
    },
)

WRITE_FILE_SCHEMA = _make_schema(
    name="write_file",
    description="将内容写入指定路径的文件（覆盖已有文件或创建新文件）。",
    properties={
        "path": {"type": "string", "description": "相对于工作目录的文件路径"},
        "content": {"type": "string", "description": "要写入的文件内容"},
    },
)

# ── 计划审批 ──────────────────────────────────────────────────────────

SUBMIT_PLAN_SCHEMA = _make_schema(
    name="submit_plan",
    description="提交执行计划供 Leader 审批。在 Plan 模式下使用。",
    properties={
        "task_id": {"type": "string", "description": "关联的任务 ID"},
        "plan": {"type": "string", "description": "详细的执行计划描述"},
    },
)

CHECK_PLAN_STATUS_SCHEMA = _make_schema(
    name="check_plan_status",
    description="检查自己提交的计划的审批状态。",
    properties={},
    required=[],
)

RESPOND_TO_SHUTDOWN_SCHEMA = _make_schema(
    name="respond_to_shutdown",
    description="响应 Leader 的关机请求。",
    properties={
        "accept": {"type": "boolean", "description": "是否接受关机请求"},
        "reason": {"type": "string", "description": "状态和关机原因"},
    },
)

# ── 团队操作 ──────────────────────────────────────────────────────────

FORK_AGENT_SCHEMA = _make_schema(
    name="fork_agent",
    description="派生子智能体并行处理子任务。需有 fork 权限。",
    properties={
        "name": {"type": "string", "description": "子智能体名称"},
        "role": {"type": "string", "description": "子智能体角色: executor, reviewer, specialist"},
        "reason": {"type": "string", "description": "Fork 原因和子任务描述"},
    },
)

PUBLISH_TASK_SCHEMA = _make_schema(
    name="publish_task",
    description="发布新任务到任务池，可选指定依赖关系。",
    properties={
        "name": {"type": "string", "description": "任务名称"},
        "description": {"type": "string", "description": "详细任务描述"},
        "depends_on": {
            "type": "array",
            "items": {"type": "string"},
            "description": "依赖的任务 ID 列表（可选）",
        },
        "priority": {
            "type": "integer",
            "description": "优先级: 0=低, 1=中, 2=高（默认 1）",
        },
        "assigned_to": {
            "type": "string",
            "description": "分配给指定智能体（可选，留空则公开认领）",
        },
    },
    required=["name", "description"],
)

# ── 所有 schema 列表 ──────────────────────────────────────────────────

ALL_TOOL_SCHEMAS = [
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
]
