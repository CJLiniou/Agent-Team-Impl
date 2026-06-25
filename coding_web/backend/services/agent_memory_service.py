"""智能体记忆服务 — 每智能体独立的持久化记忆空间。

记忆数据库位于 sandbox 下：sandboxes/{task_id}/agent_memory/{agent_id}.db
包含：对话历史、决策记录、文件变更追踪、智能体笔记、上下文摘要。
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class AgentMemoryService:
    """管理单个智能体的持久化记忆。

    每个智能体一个独立 SQLite 数据库，存储在沙盒目录下。
    """

    def __init__(self, sandbox_root: Path, task_id: str, agent_id: str):
        self.task_id = task_id
        self.agent_id = agent_id
        self.db_dir = sandbox_root / task_id / "agent_memory"
        self.db_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.db_dir / f"{agent_id}.db"
        self._init_db()

    # ── 数据库初始化 ──────────────────────────────────────

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS conversation (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL DEFAULT '',
                    tool_name TEXT,
                    tool_input TEXT,
                    tool_output TEXT,
                    token_count INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    context TEXT NOT NULL DEFAULT '',
                    decision TEXT NOT NULL DEFAULT '',
                    reasoning TEXT NOT NULL DEFAULT '',
                    outcome TEXT DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS file_changes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT NOT NULL,
                    operation TEXT NOT NULL DEFAULT 'modify',
                    snippet TEXT DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS agent_notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL DEFAULT '',
                    tags TEXT DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS context_summary (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    summary TEXT NOT NULL DEFAULT '',
                    compressed_range TEXT DEFAULT '',
                    token_count INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS agent_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    summary TEXT NOT NULL DEFAULT '',
                    detail TEXT DEFAULT '',
                    task_id TEXT DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT ''
                );
            """)
            conn.commit()

    # ── 对话记忆 ──────────────────────────────────────────

    def append_conversation(self, role: str, content: str = "",
                            tool_name: str = "", tool_input: str = "",
                            tool_output: str = "", token_count: int = 0) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self._get_conn() as conn:
            cur = conn.execute(
                """INSERT INTO conversation (role, content, tool_name, tool_input,
                   tool_output, token_count, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (role, content, tool_name, tool_input, tool_output, token_count, now),
            )
            conn.commit()
        return cur.lastrowid

    def upsert_conversation(self, role: str, tool_name: str, tool_input: str = "",
                            tool_output: str = "") -> int:
        """更新或插入对话记录。同 tool_name 存在则 UPDATE，否则 INSERT。

        用于 list_tasks/check_mailbox 等反复调用的工具——只需保留最新状态。
        """
        now = datetime.now(timezone.utc).isoformat()
        with self._get_conn() as conn:
            existing = conn.execute(
                "SELECT id FROM conversation WHERE tool_name = ? ORDER BY id DESC LIMIT 1",
                (tool_name,)
            ).fetchone()
            if existing:
                conn.execute(
                    """UPDATE conversation SET tool_input=?, tool_output=?, created_at=?
                       WHERE id=?""",
                    (tool_input, tool_output, now, existing["id"])
                )
                conn.commit()
                return existing["id"]
            else:
                cur = conn.execute(
                    """INSERT INTO conversation (role, tool_name, tool_input, tool_output, created_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (role, tool_name, tool_input, tool_output, now)
                )
                conn.commit()
                return cur.lastrowid

    def get_conversation(self, limit: int = 50, offset: int = 0) -> list[dict]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM conversation ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def get_conversation_count(self) -> int:
        with self._get_conn() as conn:
            row = conn.execute("SELECT COUNT(*) as cnt FROM conversation").fetchone()
        return row["cnt"] if row else 0

    # ── 决策记录 ──────────────────────────────────────────

    def record_decision(self, context: str, decision: str,
                        reasoning: str = "", outcome: str = "") -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self._get_conn() as conn:
            cur = conn.execute(
                """INSERT INTO decisions (context, decision, reasoning, outcome, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (context, decision, reasoning, outcome, now),
            )
            conn.commit()
        return cur.lastrowid

    def get_decisions(self, limit: int = 20) -> list[dict]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM decisions ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in reversed(rows)]

    # ── 文件变更追踪 ──────────────────────────────────────

    def track_file_change(self, file_path: str, operation: str = "modify",
                          snippet: str = "") -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self._get_conn() as conn:
            cur = conn.execute(
                """INSERT INTO file_changes (file_path, operation, snippet, created_at)
                   VALUES (?, ?, ?, ?)""",
                (file_path, operation, snippet[:500] if snippet else "", now),
            )
            conn.commit()
        return cur.lastrowid

    def get_file_changes(self, limit: int = 30) -> list[dict]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM file_changes ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in reversed(rows)]

    # ── 笔记 ──────────────────────────────────────────────

    def add_note(self, content: str, tags: str = "") -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self._get_conn() as conn:
            cur = conn.execute(
                """INSERT INTO agent_notes (content, tags, created_at, updated_at)
                   VALUES (?, ?, ?, ?)""",
                (content, tags, now, now),
            )
            conn.commit()
        return cur.lastrowid

    def get_notes(self) -> list[dict]:
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM agent_notes ORDER BY updated_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    # ── 智能体事件时间线 ──────────────────────────────────

    def add_event(self, event_type: str, summary: str, detail: str = "",
                  task_id: str = "") -> int:
        """记录语义事件到智能体时间线。

        事件类型: task_started | task_completed | task_failed |
                  task_published | task_claimed |
                  file_read | file_written |
                  message_sent | messages_read |
                  waiting | error
        """
        now = datetime.now(timezone.utc).isoformat()
        with self._get_conn() as conn:
            cur = conn.execute(
                """INSERT INTO agent_events (event_type, summary, detail, task_id, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (event_type, summary, detail, task_id, now),
            )
            conn.commit()
        return cur.lastrowid

    def get_events(self, limit: int = 50, event_type: str = "") -> list[dict]:
        """获取智能体事件时间线（按时间倒序）。

        Args:
            limit: 返回条数上限
            event_type: 可选，按类型过滤
        """
        with self._get_conn() as conn:
            if event_type:
                rows = conn.execute(
                    "SELECT * FROM agent_events WHERE event_type = ? ORDER BY id DESC LIMIT ?",
                    (event_type, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM agent_events ORDER BY id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [dict(r) for r in reversed(rows)]

    # ── 上下文摘要 ────────────────────────────────────────

    def set_context_summary(self, summary: str, compressed_range: str = "",
                            token_count: int = 0) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self._get_conn() as conn:
            cur = conn.execute(
                """INSERT INTO context_summary (summary, compressed_range, token_count, created_at)
                   VALUES (?, ?, ?, ?)""",
                (summary, compressed_range, token_count, now),
            )
            conn.commit()
        return cur.lastrowid

    def get_latest_summary(self) -> Optional[dict]:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM context_summary ORDER BY id DESC LIMIT 1"
            ).fetchone()
        return dict(row) if row else None

    # ── 综合摘要 ──────────────────────────────────────────

    def get_memory_summary(self) -> dict:
        """获取记忆摘要，供 API 和系统提示词使用。"""
        conv_count = self.get_conversation_count()
        latest_summary = self.get_latest_summary()
        return {
            "agent_id": self.agent_id,
            "task_id": self.task_id,
            "conversation_count": conv_count,
            "decision_count": self._count("decisions"),
            "file_change_count": self._count("file_changes"),
            "note_count": self._count("agent_notes"),
            "latest_summary": latest_summary["summary"][:500] if latest_summary else "",
        }

    def _count(self, table: str) -> int:
        with self._get_conn() as conn:
            row = conn.execute(f"SELECT COUNT(*) as cnt FROM {table}").fetchone()
        return row["cnt"] if row else 0

    # ── 记忆继承（Fork 用）────────────────────────────────

    def export_recent_context(self, conversation_limit: int = 10) -> dict:
        """导出最近上下文，供 fork 子智能体继承。"""
        recent_conv = self.get_conversation(limit=conversation_limit)
        latest_summary = self.get_latest_summary()
        notes = self.get_notes()
        return {
            "recent_conversation": recent_conv,
            "summary": latest_summary,
            "notes": notes,
        }

