"""WebSocket 连接管理器 — 服务端 push loop，直接从 orchestrator 读取。

单一机制：连接后每 2 秒从 orchestrator 读实时状态推送给客户端。
不需要 EventBridge 异步广播，不需要前端轮询。
"""

import asyncio
import json
import logging
from typing import Dict, Set

from fastapi import WebSocket, WebSocketDisconnect

from ..models.events import (
    make_snapshot_event,
    AgentSnapshot,
    TaskSnapshot,
)
from ..services.event_bridge import EventBridge

logger = logging.getLogger(__name__)

PUSH_INTERVAL = 2.0  # 服务端推送间隔（秒）


class ConnectionManager:
    """按任务房间管理 WebSocket 连接，每个连接启动独立的 push loop。"""

    def __init__(self, event_bridge: EventBridge):
        self._rooms: Dict[str, Set[WebSocket]] = {}
        self._event_bridge = event_bridge
        self._push_tasks: Dict[WebSocket, asyncio.Task] = {}
        self._lock = asyncio.Lock()

    async def connect(self, task_id: str, websocket: WebSocket) -> None:
        """接受 WebSocket 连接，发送初始快照。始终启动 push loop。

        push loop 内部会自行判断：orchestrator 未就绪时快速轮询，
        orchestrator 消失后推送最终快照并退出。
        """
        await websocket.accept()
        async with self._lock:
            if task_id not in self._rooms:
                self._rooms[task_id] = set()
            self._rooms[task_id].add(websocket)
        logger.info(f"WebSocket connected to room '{task_id}' ({len(self._rooms[task_id])} clients)")

        # 发送初始快照
        await self._send_snapshot(task_id, websocket)

        # 始终启动 push loop — 它会根据 orchestrator 是否存在自行决策
        self._push_tasks[websocket] = asyncio.create_task(
            self._push_loop(task_id, websocket)
        )

    def disconnect(self, task_id: str, websocket: WebSocket) -> None:
        """从房间移除 WebSocket 连接并取消 push loop。"""
        room = self._rooms.get(task_id)
        if room:
            room.discard(websocket)
            if not room:
                del self._rooms[task_id]
        task = self._push_tasks.pop(websocket, None)
        if task and not task.done():
            task.cancel()
        logger.info(f"WebSocket disconnected from room '{task_id}'")

    async def disconnect_all(self, task_id: str) -> None:
        """关闭房间内所有连接（任务结束时调用）。"""
        room = self._rooms.pop(task_id, set())
        for ws in list(room):
            self._push_tasks.pop(ws, None)
            try:
                await ws.close()
            except Exception:
                pass
        logger.info(f"Closed all connections for room '{task_id}'")

    # ── 核心：服务端 push loop ──────────────────────────────

    async def _push_loop(self, task_id: str, websocket: WebSocket) -> None:
        """每 PUSH_INTERVAL 秒从 orchestrator 读状态并推送 snapshot。

        三阶段自适应：
        1. orchestrator 未就绪 → 每 1 秒快速轮询，直到出现
        2. orchestrator 存在 → 每 PUSH_INTERVAL 秒推送快照
        3. orchestrator 消失（曾存在过）→ 推送最终快照后退出

        单次 snapshot 失败不退出，保持连接稳定。
        """
        from ..orch_registry import get as get_orchestrator

        orch_was_present = False

        try:
            while True:
                orch = get_orchestrator(task_id)

                if orch is None:
                    if orch_was_present:
                        # orchestrator 曾经存在，现在消失了 → 任务完成
                        # 推送最终快照（从 EventBridge 缓存读取）然后退出
                        try:
                            await self._send_snapshot(task_id, websocket)
                        except Exception:
                            pass
                        logger.info(
                            f"Push loop exiting for task '{task_id[:8]}': orchestrator unregistered"
                        )
                        break
                    else:
                        # orchestrator 还未就绪 → 快速轮询等待
                        await asyncio.sleep(1.0)
                        continue

                # orchestrator 存在 → 正常推送模式
                orch_was_present = True

                try:
                    await self._send_snapshot(task_id, websocket)
                except WebSocketDisconnect:
                    raise
                except Exception as exc:
                    # 连接已关闭则退出，其他错误继续
                    if "after sending 'websocket.close'" in str(exc) or "close" in str(exc).lower():
                        raise WebSocketDisconnect from None
                    logger.warning(
                        f"Snapshot failed for task {task_id[:8]}: {exc} — continuing"
                    )

                await asyncio.sleep(PUSH_INTERVAL)
        except (WebSocketDisconnect, ConnectionError):
            pass
        except asyncio.CancelledError:
            pass
        finally:
            self.disconnect(task_id, websocket)
            # 主动关闭 WebSocket，让前端 onclose 触发重连或 REST 降级
            try:
                await websocket.close()
            except Exception:
                pass

    # ── 主动推送（供 Runner 在关键节点调用）────────────────

    async def push_snapshot(self, task_id: str) -> None:
        """向房间内所有客户端推送最新快照。"""
        room = self._rooms.get(task_id, set())
        for ws in list(room):
            await self._send_snapshot(task_id, ws)

    # ── 单独事件广播（EventBridge broadcast handler）────────

    async def broadcast_event(self, task_id: str, event) -> None:
        """EventBridge 广播处理器：立即推送单个事件给房间内所有客户端。

        与 2 秒快照互补 — 关键事件（agent 状态变化、任务完成等）零延迟送达。
        """
        import json as _json
        room = self._rooms.get(task_id, set())
        if not room:
            return
        payload = _json.dumps(event.to_dict(), ensure_ascii=False)
        dead: set = set()
        for ws in list(room):
            try:
                await ws.send_text(payload)
            except Exception:
                dead.add(ws)
        for ws in dead:
            room.discard(ws)

    # ── 辅助读取方法 ──────────────────────────────────────

    @staticmethod
    def _read_mailbox_messages(task_id: str) -> list[dict]:
        """从 SQLite mailbox 直接读取消息。"""
        try:
            import sys
            from pathlib import Path
            _src = Path(__file__).parent.parent.parent.parent / "src"
            if str(_src) not in sys.path:
                sys.path.insert(0, str(_src))
            from agent_team import AgentMailbox

            db_path = Path(__file__).parent.parent / "sandboxes" / task_id / "team.db"
            if db_path.exists():
                mailbox = AgentMailbox(db_path)  # 传入 Path 对象，不是 str
                return [
                    {
                        "id": m.id, "sender": m.sender, "recipient": m.recipient,
                        "subject": m.subject, "content": m.content,
                        "status": m.status.value,
                        "created_at": m.created_at.isoformat() if m.created_at else "",
                    }
                    for m in mailbox.list_messages()
                ]
        except Exception:
            pass
        return []

    @staticmethod
    def _read_task_status(task_id: str) -> dict | None:
        """从 coding-web DB 读取 coding task 的当前状态。"""
        try:
            from ..dependencies import get_task_service
            ts = get_task_service()
            task = ts.get_task(task_id)
            if task:
                return {
                    "status": task.status,
                    "result": task.result[:500] if task.result else "",
                    "error_message": task.error_message,
                }
        except Exception:
            pass
        return None

    # ── 快照构建 ────────────────────────────────────────────

    async def _send_snapshot(self, task_id: str, websocket: WebSocket) -> None:
        """构建并发送当前状态快照。优先 orchestrator，降级 EventBridge。"""
        from ..orch_registry import get as get_orchestrator
        from ..models.events import AgentSnapshot as AS, TaskSnapshot as TS

        orch = get_orchestrator(task_id)

        if orch:
            agents_raw = [
                AS(
                    id=a.id, name=a.name, role=a.role.value,
                    state=a.state.value, current_task_id=a.current_task_id or "",
                    current_action="", completed_tasks=a.completed_tasks,
                    failed_tasks=a.failed_tasks, error_message=a.error_message,
                )
                for a in orch.agents.values()
            ]
            tasks_raw = [
                TS(
                    id=t.id, name=t.name, description=t.description[:200],
                    status=t.status.value, assigned_to=t.assigned_to,
                    priority=t.priority, result=(t.result or "")[:300],
                )
                for t in orch.task_manager.list_tasks()
            ]
        else:
            agents_raw = self._event_bridge.get_agent_states(task_id)
            tasks_raw = self._event_bridge.get_task_states(task_id)

        # ═══════════════════════════════════════════════════════
        # 消息：从 SQLite mailbox 直读（与 Agent 实际收发一致）
        # ═══════════════════════════════════════════════════════
        messages_raw = self._read_mailbox_messages(task_id)
        if not messages_raw:
            messages_raw = self._event_bridge.get_messages(task_id)

        buffer = self._event_bridge.get_buffer(task_id)
        recent_logs = [
            {"level": e.data.get("level", "info"),
             "message": e.data.get("message", ""),
             "name": e.data.get("name", ""),
             "timestamp": e.timestamp}
            for e in buffer
            if e.type == "log_entry"
        ][-50:]

        # ═══════════════════════════════════════════════════════
        # 任务状态：从 DB 读取 coding task 的当前状态
        # ═══════════════════════════════════════════════════════
        task_status = self._read_task_status(task_id)

        snapshot = make_snapshot_event(
            task_id=task_id,
            agents=agents_raw,
            tasks=tasks_raw,
            messages=messages_raw,
            logs=recent_logs,
        )
        # 注入 coding task 状态到 snapshot data
        if task_status:
            snapshot.data["task_status"] = task_status
        payload = json.dumps(snapshot.to_dict(), ensure_ascii=False)
        await websocket.send_text(payload)