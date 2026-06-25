"""能力→工具白名单映射、角色提示词、工具白名单计算。"""

# ── 所有智能体都有的基础工具
BASE_TOOLS = {
    "claim_task", "complete_task", "fail_task",
    "send_message", "check_mailbox",
    "list_agents", "list_tasks", "read_task",
    "respond_to_shutdown",
}

# ── 每个能力额外授予的工具
CAPABILITY_TOOLS = {
    "code_generation":      {"read_file", "write_file"},
    "debugging":            {"read_file", "write_file"},
    "file_operations":      {"read_file", "write_file"},
    "code_review":          {"read_file"},
    "bug_detection":        {"read_file"},
    "quality_assurance":    {"read_file"},
    "security_audit":       {"read_file"},
    "performance_analysis": {"read_file"},
    "problem_decomposition": {"submit_plan"},
    "architecture_design":  {"submit_plan", "fork_agent"},
    "task_planning":        {"submit_plan"},
    "system_design":        {"submit_plan", "fork_agent", "read_file", "write_file"},
    "testing":              {"read_file", "write_file"},
}

# ── 角色基础提示词 ───────────────────────────────────────────────────

ROLE_PROMPTS = {
    "specialist": (
        "## 角色: 专家\n"
        "你是独立问题解决者。claim_task → write_file → complete_task，一步到位。"
    ),
    "coordinator": (
        "## 角色: 协调者\n"
        "你是任务协调者。用 publish_task 分派编码任务，用 list_tasks 跟踪进度。\n"
        "⛔ 不能写代码文件，可写 .md 文档。不要创建 'Design' 任务——直接分派编码任务。\n"
        "⛔ 如果认领了不该你做的编码任务 → fail_task + publish_task 转发给正确的 executor。\n"
        "全部子任务完成后 complete_task 结束项目。"
    ),
    "executor": (
        "## 角色: 执行者\n"
        "你是编码执行者。\n"
        "没有任务时: list_tasks 查看 → claim_task 认领匹配的\n"
        "有任务时: write_file 写代码 → complete_task 提交 → send_message 通知发布者\n"
        "如果任务明显不匹配你的能力 → fail_task + send_message 通知 Leader 重新分配\n"
        "收到消息时: check_mailbox 查看并回复。不要 publish_task——那是协调者的工作。"
    ),
    "reviewer": (
        "## 角色: 审查者\n"
        "你是代码审查者。read_file 检查代码 → 有问题 publish_task 发布修补 → 无问题 complete_task 通过。\n"
        "⛔ 不能写代码文件，可写 .md 报告。完成后通知 Leader。\n"
        "如果审查的代码质量太差无法修补 → fail_task + publish_task 转发给原作者重做。"
    ),
}

# ── Leader 追加提示词 ─────────────────────────────────────────────────

LEADER_EXTRA_PROMPT = (
    "\n\n## Leader 职责\n"
    "你是团队 Leader。多协调者时你是唯一发布任务的人。\n"
    "1. publish_task 发布编码任务，有 reviewer 加 [审查] 任务\n"
    "2. list_tasks 等全部完成 → complete_task 结束项目"
)

# ── 能力追加提示词 ───────────────────────────────────────────────────

CAPABILITY_PROMPTS = {
    "code_generation": (
        "## 代码生成能力\n"
        "你擅长编写代码。写干净、高效、有注释的代码，遵循目标语言的最佳实践。"
    ),
    "debugging": (
        "## 调试能力\n"
        "你擅长调试。系统性地定位根因，先复现问题，再隔离变量，最后应用最小修复。"
    ),
    "file_operations": (
        "## 文件操作能力\n"
        "你可以读写项目文件。修改前先 read_file 了解现有代码，write_file 保持清晰的文件结构。"
    ),
    "code_review": (
        "## 代码审查能力\n"
        "你审查代码的正确性、可读性、可维护性和规范遵循。给出具体建议但不要重写全部代码。"
    ),
    "bug_detection": (
        "## 缺陷检测能力\n"
        "你扫描代码中的逻辑错误、边界情况、竞态条件、资源泄漏等问题。对每个缺陷报告严重程度和复现步骤。"
    ),
    "quality_assurance": (
        "## 质量保证能力\n"
        "你验证代码是否满足需求、边界情况是否处理、测试覆盖是否充分。以明确的验收标准来评估。"
    ),
    "security_audit": (
        "## 安全审计能力\n"
        "你专注于 OWASP Top 10 和常见安全漏洞的审计。\n"
        "检查: SQL注入、XSS、认证绕过、敏感数据泄露、越权访问、安全配置错误、不安全的反序列化。\n"
        "对每个发现报告: 严重程度(严重/高/中/低)、漏洞类型、受影响代码位置、影响范围和修复建议。\n"
        "⛔ 你是只读的 — 只能报告发现，不能修改代码。如需修复，用 publish_task 发布。"
    ),
    "performance_analysis": (
        "## 性能分析能力\n"
        "你识别性能瓶颈: O(n)复杂度问题、不必要的内存分配、阻塞I/O、N+1查询等。给出优化建议和预期效果。"
    ),
    "problem_decomposition": (
        "## 问题拆解能力\n"
        "你将复杂问题分解为独立、可并行的子任务。定义清晰的组件接口。拆解后提交计划供审批。"
    ),
    "architecture_design": (
        "## 架构设计能力\n"
        "你设计系统架构，考虑可扩展性、可靠性、可维护性。定义组件边界、数据流和技术选型。你可以 fork 子智能体并行实现各组件。"
    ),
    "task_planning": (
        "## 任务规划能力\n"
        "你创建详细的执行计划，包含里程碑、依赖关系和工期估算。执行前提交计划供审查。"
    ),
    "system_design": (
        "## 系统设计能力\n"
        "你设计端到端系统，产出清晰的设计文档和可工作的代码。你可以 fork 子智能体并行实现各组件。"
    ),
    "testing": (
        "## 测试能力\n"
        "你编写全面的测试: 单元测试、集成测试、边界测试、回归测试。追求高覆盖率，测试行为而非实现细节。"
    ),
}

# ── 角色文件写入限制 ─────────────────────────────────────────────────

ROLE_CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs",
    ".cpp", ".c", ".h", ".hpp", ".cs", ".rb", ".php", ".swift",
    ".html", ".css", ".scss", ".less", ".vue", ".svelte",
}

ROLE_WRITE_RESTRICTIONS: dict[str, set[str]] = {
    "coordinator": ROLE_CODE_EXTENSIONS,
    "reviewer":    ROLE_CODE_EXTENSIONS,
}


# ── 工具白名单计算 ───────────────────────────────────────────────────

def compute_tools_allowlist(capabilities: list[str], role: str = "",
                            explicit_allowlist: list[str] | None = None) -> set[str] | None:
    """根据能力标签计算可用的工具集合。

    Args:
        capabilities: 智能体的能力标签列表
        role: 未使用（保留兼容）
        explicit_allowlist: 显式工具白名单，非空时直接使用

    Returns:
        允许的工具名集合，返回 None 表示全部可用
    """
    if explicit_allowlist:
        return set(explicit_allowlist)
    if not capabilities:
        return None
    allowed = set(BASE_TOOLS)
    for cap in capabilities:
        extra = CAPABILITY_TOOLS.get(cap, set())
        allowed.update(extra)
    return allowed


# ── 系统提示词构建 ───────────────────────────────────────────────────

def build_system_prompt(role: str = "executor", capabilities: list[str] | None = None,
                        is_leader: bool = False, user_extra: str = "") -> str:
    """构建最终系统提示词: 角色基础 + Leader追加 + 能力追加 + 用户自定义。"""
    parts = []

    role_prompt = ROLE_PROMPTS.get(role, ROLE_PROMPTS["executor"])
    parts.append(role_prompt)

    if is_leader:
        parts.append(LEADER_EXTRA_PROMPT)

    if capabilities:
        for cap in capabilities:
            snippet = CAPABILITY_PROMPTS.get(cap, "")
            if snippet:
                parts.append(snippet)

    if user_extra.strip():
        parts.append(f"## 用户补充指令\n{user_extra.strip()}")

    return "\n\n".join(parts)


def build_system_prompt_from_capabilities(capabilities: list[str], base_prompt: str = "") -> str:
    """兼容旧接口: 根据能力标签构建系统提示词。"""
    if base_prompt:
        return base_prompt + "\n\n" + "\n\n".join(
            CAPABILITY_PROMPTS.get(c, "") for c in capabilities if CAPABILITY_PROMPTS.get(c)
        )
    return "\n\n".join(CAPABILITY_PROMPTS.get(c, "") for c in capabilities if CAPABILITY_PROMPTS.get(c))
