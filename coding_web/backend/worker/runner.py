"""编码任务执行器 — 在沙盒中编排智能体团队。

改编自 CLI/docoding/modes.py 的团队模式，将 TeamConsole 替换为 WebSocketConsole。
重构后：CodingRunner 是薄调度器，委托给 AgentLifecycleManager / WaitManager / 策略类。
"""

import asyncio
import logging
import sys
from pathlib import Path

from ..services.docker_sandbox import get_docker_sandbox
from ..orch_registry import register as register_orchestrator, unregister as unregister_orchestrator

_project_root = Path(__file__).parent.parent.parent.parent
_src_path = _project_root / "src"
if str(_src_path) not in sys.path:
    sys.path.insert(0, str(_src_path))

from agent_team import TeamOrchestrator, AnthropicProvider, OpenAIProvider

from ..config import get_settings
from ..models.events import make_run_completed_event
from ..services.event_bridge import EventBridge
from ..services.sandbox_service import SandboxService
from .ws_console import WebSocketConsole
from .agent_lifecycle_manager import AgentLifecycleManager
from .wait_manager import WaitManager
from .result_extractor import ResultExtractor
from .strategies import SimpleStrategy, TeamStrategy, CustomTeamStrategy

logger = logging.getLogger(__name__)


class CodingRunner:
    """在沙盒中编排智能体团队执行编码任务。

    支持模式：simple / team / custom_team。
    """

    def __init__(
        self,
        task_id: str,
        task_title: str,
        problem_description: str,
        language: str,
        mode: str,
        num_coders: int,
        model: str,
        max_tokens: int,
        event_bridge: EventBridge,
        sandbox_service: SandboxService,
        team_config=None,
        continue_from_task_id: str = "",
    ):
        self.task_id = task_id
        self.task_title = task_title
        self.problem = problem_description
        self.language = language
        self.mode = mode
        self.num_coders = num_coders
        self.model = model
        self.max_tokens = max_tokens
        self.bridge = event_bridge
        self.sandbox = sandbox_service
        self.team_config = team_config
        self.continue_from_task_id = continue_from_task_id

        settings = get_settings()
        self._provider_type = settings.llm_provider
        self._api_key = settings.llm_api_key or ""
        self._base_url = settings.llm_base_url or ""
        self._timeout = settings.task_timeout_seconds

        self._orchestrator = None
        self._console = None
        self._cancelled = False

        # 委托对象
        self._lifecycle = AgentLifecycleManager(task_id, settings.sandbox_root)
        self._waiter = WaitManager(task_id, None)  # console 在 _begin_run 后设置

    # ── 公共接口 ──────────────────────────────────────────────────

    async def run(self) -> dict:
        """执行编码任务。"""
        sandbox_path = None
        ds = get_docker_sandbox()
        try:
            # 1. 创建沙盒
            if self.continue_from_task_id:
                sandbox_path = self.sandbox.clone_sandbox(
                    source_task_id=self.continue_from_task_id,
                    dest_task_id=self.task_id,
                    language=self.language,
                    problem_description=self.problem,
                )
            else:
                sandbox_path = self.sandbox.create_sandbox(
                    self.task_id, self.language, self.problem,
                )

            # 2. Docker 容器（可选）
            if ds.docker_available:
                project_dir = sandbox_path / "project"
                await ds.create_container(self.task_id, project_dir)

            # 3. 创建 orchestrator + console
            orch, console = self._begin_run(sandbox_path)

            # 4. 创建 provider
            provider = self._create_provider()

            # 5. 委托给策略执行
            strategy = self._select_strategy()
            result = await strategy.execute(
                sandbox_path, orch, console, provider,
                self._lifecycle, self._waiter,
            )

            # 6. 发布完成事件
            self.bridge.publish(
                self.task_id,
                make_run_completed_event(
                    self.task_id,
                    "completed" if result["success"] else "failed",
                    result["answer"],
                    result["stats"],
                ),
            )

            return result

        except asyncio.CancelledError:
            await self._shutdown_all()
            return {"success": False, "answer": "", "error": "Task cancelled", "stats": {}}

        except Exception as exc:
            logger.exception(f"Runner failed for task {self.task_id}")
            return {"success": False, "answer": "", "error": str(exc), "stats": {}}

        finally:
            if self._orchestrator:
                try:
                    self._orchestrator._db_conn.close()
                except (AttributeError, OSError):
                    pass

    async def cancel(self) -> None:
        """取消当前执行。"""
        self._cancelled = True
        await self._shutdown_all()

    # ── 内部方法 ──────────────────────────────────────────────────

    def _begin_run(self, sandbox_path: Path) -> tuple:
        """创建 orchestrator + console + 写 problem.txt。"""
        team_name = self._get_team_name()
        project_dir = sandbox_path / "project"
        project_dir.mkdir(parents=True, exist_ok=True)

        orch = TeamOrchestrator(sandbox_path / "team.db", team_name)
        orch.set_work_dir(str(project_dir))
        self._orchestrator = orch
        register_orchestrator(self.task_id, orch)

        self._console = WebSocketConsole(self.task_id, self.bridge)
        orch.console = self._console
        self._waiter.console = self._console

        (project_dir / "problem.txt").write_text(self.problem, encoding="utf-8")
        return orch, self._console

    def _get_team_name(self) -> str:
        if self.team_config and self.team_config.name:
            return self.team_config.name
        if self.mode == "simple":
            return "coding-web-simple"
        return "coding-web-team"

    def _select_strategy(self):
        """根据模式选择策略。"""
        if self.mode == "simple":
            return SimpleStrategy(self.model, self.max_tokens,
                                  self.task_title, self.problem)
        elif self.team_config and self.team_config.agents:
            return CustomTeamStrategy(self.team_config, self.model, self.max_tokens,
                                      self.problem, self.task_title, self.language)
        else:
            return TeamStrategy(self.num_coders, self.model, self.max_tokens,
                                self.problem, self.task_title)

    def _create_provider(self):
        """根据配置创建 LLM Provider。"""
        ptype = self._provider_type or "anthropic"
        if ptype == "openai":
            return OpenAIProvider(
                api_key=self._api_key, model=self.model or "gpt-4o",
                base_url=self._base_url,
            )
        return AnthropicProvider(
            api_key=self._api_key, model=self.model or "claude-sonnet-4-6",
            base_url=self._base_url,
        )

    async def _shutdown_all(self) -> None:
        """关停所有 agent。"""
        if self._orchestrator:
            try:
                await asyncio.wait_for(
                    self._orchestrator.shutdown_all(force=True),
                    timeout=5.0,
                )
            except (asyncio.TimeoutError, Exception):
                pass
