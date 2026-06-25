"""团队配置服务 — 管理用户自定义的智能体团队模板。

团队模板可在创建任务时复用，避免每次重新配置。
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from ..models.task import TaskDB
from ..models.team_config import TeamConfig

logger = logging.getLogger(__name__)


class TeamConfigService:
    """团队配置模板的 CRUD 服务。

    存储：coding-web.db 中的 team_templates 表。
    """

    def __init__(self, db: TaskDB):
        self._db = db

    # ── CRUD ──────────────────────────────────────────────────

    def create(self, config: TeamConfig) -> TeamConfig:
        """创建团队模板。"""
        now = datetime.now(timezone.utc).isoformat()
        config.id = config.id or str(uuid4())
        config.created_at = config.created_at or now
        config.updated_at = now

        self._db.create_team_template(
            template_id=config.id,
            name=config.name,
            config_json=json.dumps(config.to_dict(), ensure_ascii=False),
            created_at=config.created_at,
            updated_at=config.updated_at,
        )
        logger.info(f"Team template created: {config.name} ({config.id[:8]})")
        return config

    def get(self, template_id: str) -> Optional[TeamConfig]:
        """按 ID 获取团队模板。"""
        row = self._db.get_team_template(template_id)
        if row is None:
            return None
        return TeamConfig.from_dict(json.loads(row["config_json"]))

    def list_all(self) -> list[TeamConfig]:
        """列出所有团队模板"""
        rows = self._db.list_team_templates()
        results = []
        for row in rows:
            try:
                config = TeamConfig.from_dict(json.loads(row["config_json"]))
                results.append(config)
            except Exception:
                logger.exception(f"Failed to parse template {row['id']}")
        return results

    def update(self, template_id: str, config: TeamConfig) -> Optional[TeamConfig]:
        """更新团队模板。"""
        existing = self._db.get_team_template(template_id)
        if existing is None:
            return None

        now = datetime.now(timezone.utc).isoformat()
        config.updated_at = now
        config.id = template_id  # 保持原 ID

        self._db.update_team_template(
            template_id=template_id,
            name=config.name,
            config_json=json.dumps(config.to_dict(), ensure_ascii=False),
            updated_at=now,
        )
        logger.info(f"Team template updated: {config.name} ({template_id[:8]})")
        return config

    def delete(self, template_id: str) -> bool:
        """删除团队模板。"""
        result = self._db.delete_team_template(template_id)
        if result:
            logger.info(f"Team template deleted: {template_id[:8]}")
        return result
