import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# 确保 src/ 在 path 中，以便导入 agent_team
_project_root = Path(__file__).parent.parent.parent  # team/
_src_path = _project_root / "src"
if str(_src_path) not in sys.path:
    sys.path.insert(0, str(_src_path))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .models.task import TaskDB
from .services.docker_sandbox import get_docker_sandbox
from .services.event_bridge import EventBridge
from .services.sandbox_service import SandboxService
from .services.task_service import TaskService
from .websocket.manager import ConnectionManager
from .dependencies import init_services, clear_services, get_ws_manager, get_task_service

# ── 日志配置 ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("coding-web")

# 延迟导入路由（在服务初始化之后）
_settings = get_settings()


# ── Lifespan ──────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理。"""
    # ── 启动 ──
    logger.info("Starting coding-web v0.1.0")
    logger.info(f"Sandbox root: {_settings.sandbox_root}")
    logger.info(f"LLM provider: {_settings.llm_provider}")

    # 清理上次运行残留的 Docker 容器（后端重启后 in-memory 状态丢失）
    ds = get_docker_sandbox()
    ds.cleanup_orphaned_containers()

    event_bridge = EventBridge(buffer_size=_settings.event_buffer_size)
    task_db = TaskDB(str(_settings.database_path))
    sandbox_service = SandboxService(sandbox_root=_settings.sandbox_root)
    ws_manager = ConnectionManager(event_bridge)
    task_service = TaskService(task_db, event_bridge, sandbox_service)

    # 注册广播处理器：Runner 发布的单个事件立即推送到 WebSocket 客户端
    event_bridge.set_broadcast_handler(ws_manager.broadcast_event)

    init_services(event_bridge, sandbox_service, task_service, ws_manager)
    logger.info("All services initialized")

    yield

    # ── 关闭 ──
    logger.info("Shutting down...")
    if task_service:
        for task in task_service.list_tasks("running"):
            try:
                await task_service.cancel_task(task.id)
            except Exception:
                pass

    clear_services()
    logger.info("Shutdown complete")


# ── FastAPI App ───────────────────────────────────────────

app = FastAPI(
    title="Coding Agent Team",
    description="基于 FastAPI 的编码智能体团队 Web 服务 — 创建编码任务，实时观察多智能体协作过程",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 路由注册 ──────────────────────────────────────────────

from .routes import tasks, agents, messages, sandbox, execute, teams, memory, interventions  # noqa: E402

app.include_router(tasks.router, prefix="/api", tags=["Tasks"])
app.include_router(agents.router, prefix="/api", tags=["Agents"])
app.include_router(messages.router, prefix="/api", tags=["Messages"])
app.include_router(sandbox.router, prefix="/api", tags=["Sandbox"])
app.include_router(execute.router, prefix="/api", tags=["Execute"])
app.include_router(teams.router, prefix="/api", tags=["Teams"])
app.include_router(memory.router, prefix="/api", tags=["Memory"])
app.include_router(interventions.router, prefix="/api", tags=["Interventions"])


# ── WebSocket 端点 ────────────────────────────────────────

@app.websocket("/ws/tasks/{task_id}")
async def websocket_task_stream(websocket: WebSocket, task_id: str):
    """实时事件流 — connect 后启动服务端 push loop，每 2s 推送快照。"""
    ws_manager = get_ws_manager()
    await ws_manager.connect(task_id, websocket)
    # connect() 内部启动了 _push_loop，会持续推送直到断开
    # 这里保持连接存活即可
    try:
        while True:
            # 等待客户端消息（心跳/关闭）。前端不主动发消息也没关系，
            # 服务端 push loop 退出时会 close websocket，receive_text 即抛出异常退出
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        # 确保 push loop 被取消（push loop 自身 finally 也会清理，此处兜底）
        ws_manager.disconnect(task_id, websocket)


# ── 健康检查 ──────────────────────────────────────────────

@app.get("/api/health")
async def health_check():
    """服务健康检查。"""
    try:
        ts = get_task_service()
        running = len(ts._running)
    except AssertionError:
        running = 0
    return {
        "status": "ok",
        "version": "0.1.0",
        "running_tasks": running,
    }
