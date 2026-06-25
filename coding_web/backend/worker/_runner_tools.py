"""工具注册辅助函数和 Schema 常量 — 从 runner.py 中提取。"""

import re
import logging

logger = logging.getLogger(__name__)

# ── execute_code 工具 Schema ─────────────────────────────────────────

EXECUTE_CODE_SCHEMA = {
    "name": "execute_code",
    "description": (
        "在沙盒环境中执行代码命令并获取输出。"
        "用于运行测试、验证代码正确性、查看运行结果。"
        "支持 python/node 等命令。"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "要执行的命令，如 'python main.py' 或 'node src/index.js' 或 'python -m pytest test.py -v'",
            },
            "workdir": {
                "type": "string",
                "description": "工作目录，默认为 /workspace 或 project/",
            },
            "timeout": {
                "type": "integer",
                "description": "超时秒数，默认 30",
            },
        },
        "required": ["command"],
    },
}

# ── Glob 工具 Schema ─────────────────────────────────────────────────

GLOB_SCHEMA = {
    "name": "glob",
    "description": (
        "在沙盒项目目录中查找匹配通配符模式的文件。"
        "类似 Unix glob，支持 ** 递归匹配。"
        "示例: glob('**/*.py') 查找所有 Python 文件, "
        "glob('src/**/*.ts') 查找 src 下所有 TypeScript 文件。"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "文件匹配模式，如 '**/*.py'、'src/**/*.ts'、'*.json'",
            },
            "path": {
                "type": "string",
                "description": "搜索起始目录，默认为 project/",
            },
        },
        "required": ["pattern"],
    },
}

# ── Grep 工具 Schema ─────────────────────────────────────────────────

GREP_SCHEMA = {
    "name": "grep",
    "description": (
        "在沙盒项目文件中搜索匹配正则表达式的内容。"
        "返回匹配的文件路径、行号和内容摘要。"
        "示例: grep('class\\s+\\w+') 查找所有类定义, "
        "grep('TODO|FIXME') 查找待办标记。"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "正则表达式搜索模式，如 'def test_'、'class\\s+\\w+'、'TODO'",
            },
            "glob": {
                "type": "string",
                "description": "可选的文件过滤，如 '*.py'、'*.ts'，只搜索匹配的文件",
            },
            "path": {
                "type": "string",
                "description": "搜索起始目录，默认为 project/",
            },
        },
        "required": ["pattern"],
    },
}


# ── 工具函数 ────────────────────────────────────────────────────────

def format_size(size: int) -> str:
    """格式化文件大小。"""
    for unit in ["B", "KB", "MB"]:
        if size < 1024:
            return f"{size}{unit}"
        size //= 1024
    return f"{size}GB"
