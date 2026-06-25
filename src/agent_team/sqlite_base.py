"""SQLite 存储基类 — TaskManager 和 AgentMailbox 的共享样板代码。

提供连接管理、时间戳工具和标准查询辅助方法。
"""

import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TypeVar, Generic

T = TypeVar('T')


class SqliteStore(Generic[T]):
    """基于 SQLite 的泛型持久化存储基类。

    子类只需定义 _init_db() 和 _row_to_object()，其余连接管理
    和序列化逻辑由基类提供。
    """

    def __init__(self, db_path: Path):
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)

    # ── 连接管理 ──────────────────────────────────────────────────

    def _get_conn(self) -> sqlite3.Connection:
        """获取数据库连接（短连接模式，每次操作即连即断）。"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """执行一条 SQL，返回 cursor。"""
        with self._get_conn() as conn:
            return conn.execute(sql, params)

    def _execute_script(self, sql: str) -> None:
        """执行多语句 SQL 脚本（用于建表）。"""
        with self._get_conn() as conn:
            conn.executescript(sql)

    def _fetch_all(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        """查询并返回所有行。"""
        with self._get_conn() as conn:
            return conn.execute(sql, params).fetchall()

    def _fetch_one(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        """查询并返回一行，无结果返回 None。"""
        with self._get_conn() as conn:
            return conn.execute(sql, params).fetchone()

    # ── 序列化辅助 ──────────────────────────────────────────────

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _now_unix() -> int:
        return int(time.time())

    @staticmethod
    def _serialize_meta(metadata: dict | None) -> str:
        return json.dumps(metadata or {}, ensure_ascii=False)

    @staticmethod
    def _deserialize_meta(raw: str | None) -> dict:
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}

    # ── 子类需实现 ──────────────────────────────────────────────

    def _init_db(self) -> None:
        """子类实现：创建表结构和索引。"""
        raise NotImplementedError

    def _row_to_object(self, row: sqlite3.Row) -> T:
        """子类实现：将 sqlite3.Row 转换为领域对象。"""
        raise NotImplementedError

    @staticmethod
    def _object_to_dict(obj: T) -> dict:
        """子类可覆盖：将领域对象转为字典用于存储。"""
        raise NotImplementedError
