"""Agent 定义（复用 docoding 的配置）。

从 runner.py 中提取，减少主文件体积。
"""

CODER_NAMES = ["Alpha", "Beta", "Gamma", "Delta", "Epsilon"]

AGENT_DEFINITIONS = {
    "architect": {
        "id": "code-architect",
        "name": "CodeArchitect",
        "role": "coordinator",
        "capabilities": [
            "problem_decomposition", "architecture_design", "task_planning",
            "code_review", "system_design",
        ],
    },
    "coder": {
        "id_template": "coder-{i}",
        "name_template": "Coder-{name}",
        "role": "executor",
        "capabilities_base": ["code_generation", "debugging", "file_operations"],
    },
    "reviewer": {
        "id": "code-reviewer",
        "name": "CodeReviewer",
        "role": "reviewer",
        "capabilities": [
            "code_review", "bug_detection", "quality_assurance",
            "security_audit", "performance_analysis",
        ],
    },
    "simple": {
        "id": "code-solver",
        "name": "CodeSolver",
        "role": "specialist",
        "capabilities": ["code_generation", "debugging", "file_operations"],
    },
}
