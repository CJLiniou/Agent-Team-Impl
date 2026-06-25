"""应用配置 — 从环境变量和 .env 文件加载。

优先级：环境变量 > .env 文件 > 默认值
"""

import os
from pathlib import Path
from typing import Optional


class Settings:
    """coding-web 应用配置。

    所有配置项均可通过环境变量设置，有合理的默认值。
    """

    def __init__(self):
        # ── 路径 ──
        self.project_root: Path = Path(__file__).parent.parent.parent  # team/
        self.sandbox_root: Path = Path(
            os.environ.get("CODING_WEB_SANDBOX_ROOT", str(Path(__file__).parent / "sandboxes"))
        )
        self.database_path: Path = Path(
            os.environ.get("CODING_WEB_DATABASE_PATH", str(Path(__file__).parent / "coding-web.db"))
        )

        # ── 服务 ──
        self.host: str = os.environ.get("CODING_WEB_HOST", "127.0.0.1")
        self.port: int = int(os.environ.get("CODING_WEB_PORT", "8000"))
        self.cors_origins: list[str] = os.environ.get(
            "CODING_WEB_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        ).split(",")

        # ── 沙盒限制 ──
        self.max_sandboxes: int = int(os.environ.get("CODING_WEB_MAX_SANDBOXES", "10"))
        self.task_timeout_seconds: int = int(os.environ.get("CODING_WEB_TASK_TIMEOUT", "1800"))
        self.max_coders: int = int(os.environ.get("CODING_WEB_MAX_CODERS", "5"))

        # ── LLM 默认配置（用户可在任务创建时覆盖）──
        self.llm_provider: str = os.environ.get("AGENT_TEAM_PROVIDER", "anthropic")
        self.llm_model: str = os.environ.get("CODING_WEB_MODEL", "")
        self.llm_api_key: str = os.environ.get(
            "ANTHROPIC_API_KEY" if self.llm_provider == "anthropic" else "OPENAI_API_KEY", ""
        )
        self.llm_base_url: str = os.environ.get("CODING_WEB_BASE_URL", "")
        self.llm_max_tokens: int = int(os.environ.get("CODING_WEB_MAX_TOKENS", "4096"))
        self.llm_max_concurrent: Optional[int] = None
        _mc = os.environ.get("CODING_WEB_MAX_CONCURRENT", "")
        if _mc and _mc.isdigit():
            self.llm_max_concurrent = int(_mc)

        # ── 事件缓冲 ──
        self.event_buffer_size: int = int(os.environ.get("CODING_WEB_EVENT_BUFFER_SIZE", "200"))


# 全局单例
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """获取全局配置单例。"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
