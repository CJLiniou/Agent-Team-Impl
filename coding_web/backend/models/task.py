"""编码任务数据模型。"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4
import sqlite3
import json


class CodingTaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskMode(str, Enum):
    SIMPLE = "simple"     # 单智能体
    TEAM = "team"         # 多智能体团队


@dataclass
class CodingTaskCreate:
    """创建编码任务的请求体。"""
    title: str
    description: str
    language: str = "general"  # python|typescript|rust|go|java|cpp|web|general
    mode: str = "team"         # simple|team
    num_coders: int = 2        # team 模式下的 coder 数量
    model: str = ""            # 覆盖默认模型
    max_tokens: int = 0        # 覆盖默认 max_tokens
    team_config_json: str = "" # 可选的自定义团队配置 JSON


@dataclass
class CodingTask:
    """编码任务实体。"""
    id: str = field(default_factory=lambda: str(uuid4()))
    title: str = ""
    description: str = ""
    language: str = "general"
    mode: str = "team"
    num_coders: int = 2
    status: str = "pending"
    sandbox_path: str = ""
    result: str = ""
    error_message: str = ""
    model: str = ""
    max_tokens: int = 0
    stats_json: str = "{}"
    run_history_json: str = "{}"   # 持久化运行历史（agents, tasks, messages, logs）
    team_config_json: str = "{}"   # 团队配置 JSON（TeamConfig.to_dict()）
    continue_from_task_id: str = ""  # 如果从其他任务继续编辑，记录源任务 ID
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: str = ""
    completed_at: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "language": self.language,
            "mode": self.mode,
            "num_coders": self.num_coders,
            "status": self.status,
            "sandbox_path": self.sandbox_path,
            "result": self.result,
            "error_message": self.error_message,
            "model": self.model,
            "max_tokens": self.max_tokens,
            "stats": json.loads(self.stats_json) if self.stats_json else {},
            "run_history": json.loads(self.run_history_json) if self.run_history_json else {},
            "team_config": json.loads(self.team_config_json) if self.team_config_json else {},
            "continue_from_task_id": self.continue_from_task_id,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }

    @staticmethod
    def from_row(row: tuple) -> "CodingTask":
        """从 SQLite 行创建 CodingTask。"""
        return CodingTask(
            id=row[0],
            title=row[1],
            description=row[2],
            language=row[3],
            mode=row[4],
            num_coders=row[5],
            status=row[6],
            sandbox_path=row[7],
            result=row[8],
            error_message=row[9],
            model=row[10],
            max_tokens=row[11],
            stats_json=row[12],
            created_at=row[13],
            started_at=row[14],
            completed_at=row[15],
            run_history_json=row[16] if len(row) > 16 else "{}",
            team_config_json=row[17] if len(row) > 17 else "{}",
            continue_from_task_id=row[18] if len(row) > 18 else "",
        )


class TaskDB:
    """编码任务数据库（元数据存储，与智能体团队的 SQLite 分开）。"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            # 主表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS coding_tasks (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    language TEXT NOT NULL DEFAULT 'general',
                    mode TEXT NOT NULL DEFAULT 'team',
                    num_coders INTEGER NOT NULL DEFAULT 2,
                    status TEXT NOT NULL DEFAULT 'pending',
                    sandbox_path TEXT NOT NULL DEFAULT '',
                    result TEXT NOT NULL DEFAULT '',
                    error_message TEXT NOT NULL DEFAULT '',
                    model TEXT NOT NULL DEFAULT '',
                    max_tokens INTEGER NOT NULL DEFAULT 0,
                    stats_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL DEFAULT '',
                    started_at TEXT NOT NULL DEFAULT '',
                    completed_at TEXT NOT NULL DEFAULT '',
                    run_history_json TEXT NOT NULL DEFAULT '{}'
                )
            """)
            conn.commit()
            try:
                conn.execute("ALTER TABLE coding_tasks ADD COLUMN run_history_json TEXT NOT NULL DEFAULT '{}'")
                conn.commit()
            except sqlite3.OperationalError:
                pass  # 列已存在
            try:
                conn.execute("ALTER TABLE coding_tasks ADD COLUMN team_config_json TEXT NOT NULL DEFAULT '{}'")
                conn.commit()
            except sqlite3.OperationalError:
                pass  # 列已存在
            try:
                conn.execute("ALTER TABLE coding_tasks ADD COLUMN continue_from_task_id TEXT NOT NULL DEFAULT ''")
                conn.commit()
            except sqlite3.OperationalError:
                pass  # 列已存在
            # 团队模板表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS team_templates (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    config_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL DEFAULT ''
                )
            """)
            # 人工介入记录表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS interventions (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL DEFAULT '',
                    type TEXT NOT NULL DEFAULT 'message',
                    content TEXT NOT NULL DEFAULT '',
                    response TEXT NOT NULL DEFAULT '',
                    metadata TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL DEFAULT '',
                    processed_at TEXT NOT NULL DEFAULT ''
                )
            """)
            conn.commit()

    def create(self, task: CodingTask) -> CodingTask:
        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO coding_tasks
                   (id, title, description, language, mode, num_coders,
                    status, sandbox_path, result, error_message,
                    model, max_tokens, stats_json, run_history_json, team_config_json,
                    continue_from_task_id, created_at, started_at, completed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    task.id, task.title, task.description, task.language,
                    task.mode, task.num_coders,
                    task.status, task.sandbox_path, task.result, task.error_message,
                    task.model, task.max_tokens, task.stats_json, task.run_history_json,
                    task.team_config_json, task.continue_from_task_id,
                    task.created_at, task.started_at, task.completed_at,
                ),
            )
            conn.commit()
        return task

    def get(self, task_id: str) -> Optional[CodingTask]:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM coding_tasks WHERE id = ?", (task_id,)
            ).fetchone()
        if row is None:
            return None
        return CodingTask.from_row(tuple(row))

    def list_all(self, status: str = "") -> list[CodingTask]:
        with self._get_conn() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM coding_tasks WHERE status = ? ORDER BY created_at DESC",
                    (status,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM coding_tasks ORDER BY created_at DESC"
                ).fetchall()
        return [CodingTask.from_row(tuple(r)) for r in rows]

    def update(self, task: CodingTask) -> CodingTask:
        with self._get_conn() as conn:
            conn.execute(
                """UPDATE coding_tasks SET
                   title=?, description=?, language=?, mode=?, num_coders=?,
                   status=?, sandbox_path=?, result=?, error_message=?,
                   model=?, max_tokens=?, stats_json=?, run_history_json=?, team_config_json=?,
                   continue_from_task_id=?, started_at=?, completed_at=?
                   WHERE id=?""",
                (
                    task.title, task.description, task.language,
                    task.mode, task.num_coders,
                    task.status, task.sandbox_path, task.result, task.error_message,
                    task.model, task.max_tokens, task.stats_json, task.run_history_json,
                    task.team_config_json, task.continue_from_task_id,
                    task.started_at, task.completed_at,
                    task.id,
                ),
            )
            conn.commit()
        return task

    def delete(self, task_id: str) -> bool:
        with self._get_conn() as conn:
            cur = conn.execute("DELETE FROM coding_tasks WHERE id = ?", (task_id,))
            conn.commit()
        return cur.rowcount > 0

    # ── 团队模板 CRUD ──────────────────────────────────────────

    def create_team_template(self, template_id: str, name: str, config_json: str,
                             created_at: str, updated_at: str) -> bool:
        """插入团队模板。"""
        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO team_templates (id, name, config_json, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (template_id, name, config_json, created_at, updated_at),
            )
            conn.commit()
        return True

    def get_team_template(self, template_id: str) -> Optional[dict]:
        """按 ID 获取团队模板。返回包含 config_json 等字段的 dict。"""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM team_templates WHERE id = ?", (template_id,)
            ).fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "name": row["name"],
            "config_json": row["config_json"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def list_team_templates(self) -> list[dict]:
        """列出所有团队模板。"""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM team_templates ORDER BY updated_at DESC"
            ).fetchall()
        return [
            {
                "id": r["id"],
                "name": r["name"],
                "config_json": r["config_json"],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
            }
            for r in rows
        ]

    def update_team_template(self, template_id: str, name: str, config_json: str,
                             updated_at: str) -> bool:
        """更新团队模板。"""
        with self._get_conn() as conn:
            cur = conn.execute(
                """UPDATE team_templates SET name=?, config_json=?, updated_at=?
                   WHERE id=?""",
                (name, config_json, updated_at, template_id),
            )
            conn.commit()
        return cur.rowcount > 0

    def delete_team_template(self, template_id: str) -> bool:
        """删除团队模板。"""
        with self._get_conn() as conn:
            cur = conn.execute(
                "DELETE FROM team_templates WHERE id = ?", (template_id,)
            )
            conn.commit()
        return cur.rowcount > 0

    # ── 介入记录 CRUD ──────────────────────────────────────────

    def create_intervention(self, intervention) -> bool:
        """插入介入记录。接受 InterventionRecord 实例。"""
        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO interventions (id, task_id, agent_id, type, content,
                   response, metadata, created_at, processed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    intervention.id, intervention.task_id, intervention.agent_id,
                    intervention.type, intervention.content,
                    intervention.response, intervention.metadata,
                    intervention.created_at, intervention.processed_at,
                ),
            )
            conn.commit()
        return True

    def list_interventions(self, task_id: str) -> list:
        """列出某个任务的所有介入记录。"""
        from .intervention import InterventionRecord  # noqa: F811
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM interventions WHERE task_id = ? ORDER BY created_at ASC",
                (task_id,),
            ).fetchall()
        return [InterventionRecord.from_row(tuple(r)) for r in rows]

    def update_intervention_response(self, intervention_id: str, response: str,
                                     processed_at: str) -> bool:
        """更新介入记录的智能体响应。"""
        with self._get_conn() as conn:
            cur = conn.execute(
                "UPDATE interventions SET response=?, processed_at=? WHERE id=?",
                (response, processed_at, intervention_id),
            )
            conn.commit()
        return cur.rowcount > 0
