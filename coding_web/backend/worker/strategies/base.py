"""RunStrategy 抽象基类。"""

from abc import ABC, abstractmethod
from pathlib import Path


class RunStrategy(ABC):
    """编码执行策略的抽象基类。

    每个具体策略实现 execute()，接收共享基础设施，返回执行结果。
    """

    @abstractmethod
    async def execute(
        self,
        sandbox_path: Path,
        orch: object,           # TeamOrchestrator
        console: object,        # WebSocketConsole
        provider,               # LLMProvider
        lifecycle,              # AgentLifecycleManager
        waiter,                 # WaitManager
    ) -> dict:
        """执行编码任务。

        Returns: {"success": bool, "answer": str, "error": str, "stats": dict}
        """
        ...
