# Demox — AI 多智能体协作编码平台

多智能体协作框架，让多个 AI 智能体以不同角色（Architect、Coder、Reviewer）协同完成编码任务。提供 Web 仪表盘实时监控整个协作过程。

## 架构

```
coding_web/                         # Web 应用
├── backend/
│   ├── main.py                     # FastAPI 入口 + 生命周期
│   ├── config.py                   # 配置（环境变量）
│   ├── dependencies.py             # 全局服务单例（DI）
│   ├── middleware.py               # 请求追踪中间件
│   ├── routes/                     # REST API（tasks/agents/messages/sandbox/execute/teams/memory/interventions）
│   ├── models/                     # 数据模型（CodingTask/AgentStateResponse/ServerEvent/TeamConfig）
│   ├── services/
│   │   ├── task_service.py         # 任务生命周期 + Runner 调度
│   │   ├── sandbox_service.py      # 沙盒文件系统管理
│   │   ├── docker_sandbox.py       # Docker 容器执行（自动降级到本地进程）
│   │   ├── event_bridge.py         # 事件总线（WebSocket 广播）
│   │   ├── agent_memory_service.py # 每 Agent 独立 SQLite 记忆库
│   │   └── intervention_service.py # 人工介入（暂停/恢复/消息注入/计划审批）
│   ├── websocket/manager.py        # WebSocket 连接 + 2s 推送循环
│   └── worker/
│       ├── runner.py               # CodingRunner — 薄调度器（~150 行）
│       ├── agent_lifecycle_manager.py  # Agent 生命周期（工具注册/记忆/关闭）
│       ├── wait_manager.py         # 等待循环 + dashboard 推送 + Reviewer 重试
│       ├── result_extractor.py     # 答案提取 + TEAM.md 生成
│       ├── ws_console.py           # WebSocket 事件适配器
│       ├── team_definitions.py     # Agent 定义常量
│       └── strategies/             # 执行策略（简单/团队/自定义）
├── frontend/                       # React 18 + TypeScript + Tailwind
│   └── src/
│       ├── pages/                  # HomePage / TaskDetailPage / TeamEditorPage
│       ├── components/             # AgentPanel / MessagePanel / SandboxFileTree / EventTimeline ...
│       ├── api/                    # REST 客户端
│       ├── store/                  # Zustand 状态管理
│       └── hooks/                  # useWebSocket
└── run_server.py                   # uvicorn 启动入口

src/agent_team/                     # 核心库（纯 Python，可独立使用）
├── orchestrator.py                 # TeamOrchestrator — facade，委托给 4 个 delegate 类
├── _orchestrator_registry.py       # AgentRegistry — Agent CRUD + 回调
├── _orchestrator_plan.py           # PlanDelegate — 计划审批
├── _orchestrator_execution.py      # ExecutionDelegate — 回调模式任务执行
├── _orchestrator_state.py          # StateSnapshot — 统计/导出/导入
├── _orchestrator_models.py         # Agent / ExecutionResult / 枚举
├── llm_agent.py                    # LLMAgent — 自主推理循环（事件驱动 + 智能休眠）
├── llm_provider.py                 # AnthropicProvider / OpenAIProvider（_BaseProvider 去重）
├── tools/                          # 15 个工具（schema + handler + registry + AgentContext）
├── tasks.py                        # TaskManager（继承 SqliteStore）— DAG + FileLock 并发
├── mailbox.py                      # AgentMailbox（继承 SqliteStore）— 点对点 + 广播
├── sqlite_base.py                  # 泛型 SQLite 存储基类
├── constants.py                    # 集中管理的魔法值
├── errors.py                       # 异常层次结构
├── hooks.py / planning.py / notifications.py / token_tracker.py / profiles.py / observability.py
└── __init__.py                     # 36 个公开导出（稳定 API）
```

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+
- Docker（可选，用于沙盒隔离执行）

### 1. 配置

```bash
cp .env.example .env
```

编辑 `.env`：

```bash
# LLM API Key（二选一）
ANTHROPIC_API_KEY=sk-ant-...
# 或
AGENT_TEAM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.deepseek.com   # 或其他兼容 API

# 可选
CODING_WEB_MODEL=deepseek-v4-flash
CODING_WEB_MAX_TOKENS=4096
CODING_WEB_API_KEY=your-api-key            # 生产环境必设
```

### 2. 安装依赖

```bash
# Python
pip install -e .

# 前端
cd coding_web/frontend
npm install
```

### 3. 启动

```bash
# 终端 1 — 后端
cd coding_web
python run_server.py

# 终端 2 — 前端
cd coding_web/frontend
npm run dev
```

访问 `http://localhost:5173`。

### 作为 Python 库使用

```python
from agent_team import TeamOrchestrator, AgentRole

orch = TeamOrchestrator("team.db", "my-team")
orch.register_agent("coder-1", "Coder", AgentRole.EXECUTOR,
                    capabilities=["code_generation", "file_operations"])

task = orch.task_manager.create_task(
    name="实现登录模块",
    description="用 Python 实现 JWT 登录...",
    priority=2,
)

orch.spawn_llm_agent("coder-1", model="claude-sonnet-4-6")
```

## 核心概念

### Agent 角色

| 角色 | 职责 | 文件权限 |
|------|------|---------|
| **Executor** | 认领编码任务 → 写代码 → 提交 | 可写代码文件 |
| **Coordinator** | 分派任务 → 跟踪进度 → 收尾 | 仅 .md/.txt/.json |
| **Reviewer** | 检查代码 → 发布修复或通过 | 仅 .md 报告 |
| **Specialist** | 独立完成，一步到位 | 可写代码文件 |

### 15 个 LLM 工具

| 类别 | 工具 |
|------|------|
| 任务 | `claim_task` `complete_task` `fail_task` `publish_task` `read_task` |
| 通信 | `send_message` `check_mailbox` |
| 文件 | `read_file` `write_file` `glob` `grep` |
| 执行 | `execute_code`（Docker 沙盒） |
| 计划 | `submit_plan` `check_plan_status` |
| 团队 | `list_agents` `list_tasks` `respond_to_shutdown` `fork_agent` |

### 任务 DAG

```
pending → claim_task → in_progress → complete_task → completed
                                     → fail_task    → failed
pending → (依赖未满足) → blocked → (依赖完成) → pending
```

### Agent 休眠优化

Agent 空闲时不会每 5 秒调一次 LLM。`_should_enter_reasoning()` 基于本地 SQLite 查询任务池状态，无任务时直接跳过推理，拉长休眠到 60 秒。零 Token 浪费。

### 记忆系统

每个 Agent 有独立 SQLite 记忆库，记录对话、决策、文件变更、事件时间线。在 prompt 中注入关键事件摘要和文件变更历史，防止重复操作。

## 运行模式

| 模式 | 说明 |
|------|------|
| **simple** | 单个 Specialist，claim → write → complete |
| **team** | Architect → Coders（并行）→ Reviewer 三阶段流水线 |
| **custom_team** | 用户自定义 TeamConfig，Leader 驱动或自由认领 |

## Docker 沙盒

- 每个任务创建独立容器，挂载 `project/` → `/workspace`
- `network_mode=none`，无网络访问
- Docker 不可用时自动降级为本地进程执行
- 容器资源限制：512MB 内存，0.5 CPU

## 配置参考

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ANTHROPIC_API_KEY` | - | Anthropic API Key |
| `OPENAI_API_KEY` | - | OpenAI 兼容 API Key |
| `AGENT_TEAM_PROVIDER` | `anthropic` | LLM 供应商 |
| `CODING_WEB_MODEL` | - | 模型名称 |
| `CODING_WEB_MAX_TOKENS` | `4096` | 每请求最大 token |
| `CODING_WEB_SANDBOX_ROOT` | `./sandboxes` | 沙盒目录 |
| `CODING_WEB_MAX_SANDBOXES` | `10` | 最大并发沙盒数 |
| `CODING_WEB_TASK_TIMEOUT` | `1800` | 任务超时（秒） |
| `CODING_WEB_API_KEY` | - | API 鉴权 Key（不设则无鉴权） |
| `CODING_WEB_LOG_FORMAT` | `text` | 日志格式（text/json） |

## 许可证

MIT
