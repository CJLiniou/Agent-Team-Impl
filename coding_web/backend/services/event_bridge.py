"""事件桥接 — 连接智能体活动和 WebSocket 广播。

是 Runner 和 ConnectionManager 之间的中央事件总线。
"""

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional

from ..models.events import (
    ServerEvent,
    AgentSnapshot,
    TaskSnapshot,
    make_agent_state_event,
    make_agent_step_event,
    make_task_status_event,
    make_message_event,
    make_tool_call_event,
    make_sandbox_file_event,
    make_log_event,
    make_run_completed_event,
    make_error_event,
)

logger = logging.getLogger(__name__)

BroadcastHandler = Callable[[str, ServerEvent], Any]


class EventBridge:
    """中央事件总线。

    收集来自 Runner/WebSocketConsole 的事件，
    缓存快照数据，并转发给 WebSocket ConnectionManager。

    用法:
        bridge = EventBridge()

        # Runner 端
        bridge.publish(task_id, make_agent_step_event(...))

        # 获取快照
        agents = bridge.get_agent_states(task_id)
    """

    def __init__(self, buffer_size: int = 200):
        # 事件缓冲区（按任务）：最近 N 条事件
        self._buffers: Dict[str, list[ServerEvent]] = {}
        self._buffer_size = buffer_size

        # 智能体状态快照（按任务）：agent_id → AgentSnapshot
        self._agent_states: Dict[str, Dict[str, AgentSnapshot]] = {}

        # 内部任务状态快照（按任务）
        self._task_states: Dict[str, Dict[str, TaskSnapshot]] = {}

        # 消息历史（按任务）
        self._messages: Dict[str, list[dict]] = {}

        # 广播处理器（由 ConnectionManager 注册）
        self._broadcast_handler: Optional[BroadcastHandler] = None
        self._pending_events: Dict[str, list[ServerEvent]] = {}

    # ── 广播处理器注册 ───────────────────────────────────────

    def set_broadcast_handler(self, handler: BroadcastHandler) -> None:
        """由 ConnectionManager 注册广播回调。

        注册后会立即发送所有积压事件。
        """
        self._broadcast_handler = handler
        # 发送积压事件
        for task_id, events in self._pending_events.items():
            for event in events:
                asyncio.ensure_future(handler(task_id, event))
        self._pending_events.clear()

    # ── 事件发布 ─────────────────────────────────────────────

    def publish(self, task_id: str, event: ServerEvent) -> None:
        """发布事件：缓存到缓冲区 + 更新快照 + 广播。"""
        # 1. 缓存
        if task_id not in self._buffers:
            self._buffers[task_id] = []
        self._buffers[task_id].append(event)
        if len(self._buffers[task_id]) > self._buffer_size:
            self._buffers[task_id] = self._buffers[task_id][-self._buffer_size:]

        # 2. 更新快照（按事件类型）
        self._update_snapshots(task_id, event)

        # 3. 广播
        if self._broadcast_handler:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._broadcast_handler(task_id, event))
            except RuntimeError:
                # 无运行中的事件循环 — 暂存事件等待下次轮询
                if task_id not in self._pending_events:
                    self._pending_events[task_id] = []
                self._pending_events[task_id].append(event)
        else:
            # 积压（连接管理器尚未注册）
            if task_id not in self._pending_events:
                self._pending_events[task_id] = []
            self._pending_events[task_id].append(event)

    # ── 快照更新 ─────────────────────────────────────────────

    def _update_snapshots(self, task_id: str, event: ServerEvent) -> None:
        """根据事件类型更新对应的快照数据。"""
        etype = event.type
        data = event.data

        if etype == "agent_state_changed":
            agent_dict = data.get("agent", {})
            snapshot = AgentSnapshot(
                id=agent_dict.get("id", ""),
                name=agent_dict.get("name", ""),
                role=agent_dict.get("role", ""),
                state=agent_dict.get("state", "idle"),
                current_task_id=agent_dict.get("current_task_id", ""),
                current_action=agent_dict.get("current_action", ""),
                completed_tasks=agent_dict.get("completed_tasks", 0),
                failed_tasks=agent_dict.get("failed_tasks", 0),
                error_message=agent_dict.get("error_message", ""),
            )
            if task_id not in self._agent_states:
                self._agent_states[task_id] = {}
            self._agent_states[task_id][snapshot.id] = snapshot

        elif etype == "agent_step":
            name = data.get("name", "")
            action = data.get("action", "")
            # 更新对应 agent 的 current_action
            agents = self._agent_states.get(task_id, {})
            for agent in agents.values():
                if agent.name == name:
                    agent.current_action = action
                    break

        elif etype == "task_status_changed":
            task_dict = data.get("task", {})
            snapshot = TaskSnapshot(
                id=task_dict.get("id", ""),
                name=task_dict.get("name", ""),
                description=task_dict.get("description", ""),
                status=task_dict.get("status", "pending"),
                assigned_to=task_dict.get("assigned_to", ""),
                priority=task_dict.get("priority", 0),
                result=task_dict.get("result", ""),
            )
            if task_id not in self._task_states:
                self._task_states[task_id] = {}
            self._task_states[task_id][snapshot.id] = snapshot

        elif etype == "message_sent":
            msg = data.get("message", {})
            if task_id not in self._messages:
                self._messages[task_id] = []
            self._messages[task_id].append(msg)
            if len(self._messages[task_id]) > 100:
                self._messages[task_id] = self._messages[task_id][-100:]

    # ── 快照数据获取（ConnectionManager 用它构建初始快照）────

    def get_buffer(self, task_id: str) -> list[ServerEvent]:
        return self._buffers.get(task_id, [])

    def get_agent_states(self, task_id: str) -> list[AgentSnapshot]:
        agents = self._agent_states.get(task_id, {})
        return list(agents.values())

    def get_task_states(self, task_id: str) -> list[TaskSnapshot]:
        tasks = self._task_states.get(task_id, {})
        return list(tasks.values())

    def get_messages(self, task_id: str) -> list[dict]:
        return self._messages.get(task_id, [])

    # ── 清理 ─────────────────────────────────────────────────

    def clear_task(self, task_id: str) -> None:
        """清理任务相关的所有缓存数据。"""
        self._buffers.pop(task_id, None)
        self._agent_states.pop(task_id, None)
        self._task_states.pop(task_id, None)
        self._messages.pop(task_id, None)
        self._pending_events.pop(task_id, None)
