"""WebSocketConsole — 将智能体活动转为 WebSocket 事件的适配器。

从 runner.py 中提取，减少主文件体积。
"""

import logging
from datetime import datetime, timezone
from uuid import uuid4

from ..models.events import (
    AgentSnapshot,
    TaskSnapshot,
    ServerEvent,
    EventType,
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
from ..services.event_bridge import EventBridge

logger = logging.getLogger(__name__)


class WebSocketConsole:
    """将智能体活动转为 WebSocket 事件的适配器。

    接口与 agent_team.TeamConsole 兼容，但输出到 EventBridge。
    """

    def __init__(self, task_id: str, event_bridge: EventBridge, enabled: bool = True):
        self.task_id = task_id
        self.bridge = event_bridge
        self.enabled = enabled
        self._agent_meta: dict[str, dict] = {}

    def register_agent_meta(self, agent_id: str, name: str, role: str) -> None:
        """注册智能体元信息，供后续事件使用。"""
        self._agent_meta[name] = {"id": agent_id, "role": role}

    def agent_start(self, name: str, model: str) -> None:
        if not self.enabled:
            return
        self.bridge.publish(
            self.task_id,
            make_log_event(self.task_id, "info", f"Agent started ({model})", name=name),
        )
        self.bridge.publish(
            self.task_id,
            make_agent_step_event(self.task_id, name, f"Started ({model})"),
        )
        meta = self._agent_meta.get(name, {})
        snapshot = AgentSnapshot(
            id=meta.get("id", name),
            name=name,
            role=meta.get("role", "executor"),
            state="busy",
            current_action=f"Starting ({model})",
        )
        self.bridge.publish(
            self.task_id,
            make_agent_state_event(self.task_id, snapshot),
        )

    def agent_step(self, name: str, action: str) -> None:
        if not self.enabled:
            return
        self.bridge.publish(
            self.task_id,
            make_agent_step_event(self.task_id, name, action),
        )
        self.bridge.publish(
            self.task_id,
            make_log_event(self.task_id, "info", action, name=name),
        )

    def tool_call(self, name: str, tool: str, args: dict, result: str = "") -> None:
        if not self.enabled:
            return
        self.bridge.publish(
            self.task_id,
            make_tool_call_event(self.task_id, name, tool, args, result),
        )
        if tool == "write_file":
            path = args.get("path", args.get("file_path", ""))
            if path:
                self.bridge.publish(
                    self.task_id,
                    make_sandbox_file_event(self.task_id, str(path), "modified"),
                )
        if tool == "send_message":
            recipient = args.get("recipient", args.get("to", ""))
            subject = args.get("subject", "")
            content = args.get("content", args.get("message", ""))
            self.bridge.publish(
                self.task_id,
                make_message_event(self.task_id, {
                    "id": str(uuid4()),
                    "sender": name,
                    "recipient": str(recipient),
                    "subject": str(subject),
                    "content": str(content),
                    "status": "sent",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }),
            )

    def tool_result(self, name: str, tool: str, result: str) -> None:
        if not self.enabled:
            return
        self.bridge.publish(
            self.task_id,
            make_log_event(self.task_id, "info", f"{tool}: {result[:200]}", name=name),
        )

    def task_claimed(self, name: str, task_name: str) -> None:
        if not self.enabled:
            return
        self.bridge.publish(
            self.task_id,
            make_log_event(self.task_id, "info", f"Claimed: {task_name}", name=name),
        )

    def task_completed(self, name: str, task_name: str, result: str = "") -> None:
        if not self.enabled:
            return
        self.bridge.publish(
            self.task_id,
            make_log_event(self.task_id, "info", f"Completed: {task_name}", name=name),
        )

    def team_dashboard(self, agents, tasks) -> None:
        """推送所有智能体和任务的当前状态快照。"""
        if not self.enabled:
            return
        if isinstance(agents, dict):
            agent_list = list(agents.values())
        else:
            agent_list = agents

        logger.info(
            f"WebSocketConsole.team_dashboard: pushing {len(agent_list)} agents, "
            f"{len(tasks) if tasks else 0} tasks for task {self.task_id[:8]}"
        )

        for agent in agent_list:
            if hasattr(agent, 'to_dict'):
                d = agent.to_dict()
            elif isinstance(agent, dict):
                d = agent
            else:
                continue
            meta = d.get("metadata", {}) or {}
            snapshot = AgentSnapshot(
                id=str(d.get("id", "")),
                name=str(d.get("name", "")),
                role=str(d.get("role", "")),
                state=str(d.get("state", "idle")),
                current_task_id=str(d.get("current_task_id", "")),
                current_action="",
                completed_tasks=int(d.get("completed_tasks", 0)),
                failed_tasks=int(d.get("failed_tasks", 0)),
                error_message=str(d.get("error_message", "")),
                parent_agent_name=str(meta.get("parent_agent_name", "")),
                allow_fork=bool(meta.get("allow_fork", False)),
            )
            self.bridge.publish(
                self.task_id,
                make_agent_state_event(self.task_id, snapshot),
            )

        for task in tasks:
            if hasattr(task, 'to_dict'):
                d = task.to_dict()
            elif isinstance(task, dict):
                d = task
            else:
                continue
            snapshot = TaskSnapshot(
                id=str(d.get("id", "")),
                name=str(d.get("name", "")),
                description=str(d.get("description", "")),
                status=str(d.get("status", "pending")),
                assigned_to=str(d.get("assigned_to", "")),
                priority=int(d.get("priority", 0)),
                result=str(d.get("result", "")),
            )
            self.bridge.publish(
                self.task_id,
                make_task_status_event(self.task_id, snapshot),
            )

    def agent_idle(self, name: str) -> None:
        if not self.enabled:
            return
        self.bridge.publish(
            self.task_id,
            make_log_event(self.task_id, "info", "Idle, waiting...", name=name),
        )

    def error(self, name: str, message: str) -> None:
        """记录 Agent 异常。"""
        if not self.enabled:
            return
        self.bridge.publish(
            self.task_id,
            make_error_event(self.task_id, message, source=name),
        )

    def agent_forked(self, parent_name: str, child_name: str, reason: str) -> None:
        """推送 agent_forked 事件。"""
        if not self.enabled:
            return
        self.bridge.publish(
            self.task_id,
            ServerEvent(
                type=EventType.AGENT_FORKED.value,
                task_id=self.task_id,
                data={
                    "parent_name": parent_name,
                    "child_name": child_name,
                    "reason": reason,
                },
            ),
        )
