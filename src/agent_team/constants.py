"""集中管理的常量 — 消除散布在多文件中的魔法值。

用法:
    from agent_team.constants import DEFAULT_ANTHROPIC_MODEL, MAX_TOOL_ROUNDS
"""

# ── 模型名称 ──────────────────────────────────────────────────────────

DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-6"
DEFAULT_HAIKU_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_OPUS_MODEL = "claude-opus-4-7"
DEFAULT_OPENAI_MODEL = "gpt-4o"

# ── 每百万 token 参考定价（USD，输入 / 输出）─────────────────────────

MODEL_PRICING: dict[str, tuple[float, float]] = {
    DEFAULT_ANTHROPIC_MODEL: (3.0, 15.0),
    DEFAULT_HAIKU_MODEL: (1.0, 5.0),
    DEFAULT_OPUS_MODEL: (15.0, 75.0),
    "default": (3.0, 15.0),
}

# ── 超时（秒）─────────────────────────────────────────────────────────

POLL_INTERVAL = 5.0                # run_llm_team 轮询间隔
DASHBOARD_INTERVAL = 15            # orchestrator 仪表盘刷新间隔
STAGGER_DELAY_MIN = 0.3            # Agent 启动随机延迟最小值
STAGGER_DELAY_MAX = 1.5            # Agent 启动随机延迟最大值
FALLBACK_TIMEOUT = 5.0             # 暂停/空闲时等待事件的超时
SHUTDOWN_TIMEOUT = 5.0             # 强制关闭超时
PLAN_AUTO_APPROVE_TIMEOUT = 10.0   # 计划自动批准等待时间
PLAN_DECISION_TIMEOUT = 30.0       # 计划决定超时

# ── LLM 调用 ──────────────────────────────────────────────────────────

MAX_TOOL_ROUNDS = 3                # 每轮推理最多工具调用轮数
MAX_RETRY_ATTEMPTS = 3             # LLM API 调用最大重试次数
RETRY_BACKOFF_BASE = 3             # 重试退避基数（秒）：backoff = (attempt+1) * base
MAX_CONCURRENT_LLM = 3             # 最大并发 LLM 调用数
DEFAULT_MAX_TOKENS = 4096          # 默认 max_tokens
PLAN_REVIEW_MAX_TOKENS = 512       # 计划审查使用的 max_tokens

# ── 并发与限制 ────────────────────────────────────────────────────────

DEFAULT_FORK_LIMIT = 3             # 每个 Agent 默认最大 fork 数量
MAX_IDLE_ROUNDS = 3               # 连续空闲轮数后进入等待模式
EXECUTE_TIMEOUT_CAP = 60           # 代码执行超时上限（秒）
SANDBOX_IMAGE = "coding-web-sandbox:latest"
SANDBOX_MEMORY_LIMIT = "512m"
SANDBOX_CPU_QUOTA = 50000
SANDBOX_NETWORK_MODE = "none"

# ── 环境变量名 ────────────────────────────────────────────────────────

ENV_ANTHROPIC_API_KEY = "ANTHROPIC_API_KEY"
ENV_ANTHROPIC_BASE_URL = "ANTHROPIC_BASE_URL"
ENV_OPENAI_API_KEY = "OPENAI_API_KEY"
ENV_OPENAI_BASE_URL = "OPENAI_BASE_URL"
ENV_AGENT_TEAM_PROVIDER = "AGENT_TEAM_PROVIDER"

# ── WebSocket ─────────────────────────────────────────────────────────

WS_PUSH_INTERVAL = 2.0             # 服务端推送间隔（秒）

# ── 沙盒执行输出限制 ─────────────────────────────────────────────────

SANDBOX_STDOUT_MAX_CHARS = 10000
SANDBOX_STDERR_MAX_CHARS = 10000

# ── 文件搜索限制 ──────────────────────────────────────────────────────

GLOB_MAX_MATCHES = 50
GREP_MAX_FILES = 100
GREP_MAX_MATCHES_PER_FILE = 5
GREP_MAX_OUTPUT_LINES = 60

# ── Web 应用 ──────────────────────────────────────────────────────────

WEB_MAX_SANDBOXES = 10
WEB_TASK_TIMEOUT = 1800            # 默认任务超时（秒）
WEB_MAX_CODERS = 5
WEB_EVENT_BUFFER_SIZE = 200
WEB_LOG_BUFFER_SIZE = 50
WEB_REVIEWER_EXTRA_TIME = 90       # Reviewer 重试额外时间（秒）
