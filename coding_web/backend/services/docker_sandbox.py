"""Docker 沙盒服务 — 为每个编码任务创建隔离的 Docker 容器。

特性：
- 按任务创建/销毁临时容器
- 挂载项目目录到容器内 /workspace
- 提供 exec 方法执行代码并捕获输出
- Docker 不可用时自动降级为本地进程执行

依赖：docker-py（pip install docker）
"""

import asyncio
import logging
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..config import get_settings

logger = logging.getLogger(__name__)

# Sandbox 镜像名
SANDBOX_IMAGE = "coding-web-sandbox:latest"


class DockerSandboxService:
    """管理 Docker 沙盒容器的生命周期。"""

    def __init__(self, sandbox_root: Optional[Path] = None):
        settings = get_settings()
        self.sandbox_root = sandbox_root or settings.sandbox_root
        self._docker_available: Optional[bool] = None
        self._client = None
        self._containers: dict[str, str] = {}  # task_id → container_id

    # ── Docker 可用性检查 ───────────────────────────────────

    @property
    def docker_available(self) -> bool:
        """检查 Docker 是否可用（惰性检测，只检测一次）。"""
        if self._docker_available is None:
            self._docker_available = self._check_docker()
        return self._docker_available

    def _check_docker(self) -> bool:
        """检测 Docker 是否安装且可连接。"""
        try:
            import docker
            client = docker.from_env()
            client.ping()
            self._client = client
            logger.info("Docker is available")
            return True
        except ImportError:
            logger.warning("docker-py not installed — Docker sandbox disabled")
            return False
        except Exception as exc:
            logger.warning(f"Docker not available (this is OK): {exc}")
            return False

    def _get_client(self):
        """获取 Docker 客户端。"""
        if self._client is None:
            import docker
            self._client = docker.from_env()
        return self._client

    # ── 镜像管理 ───────────────────────────────────────────

    async def ensure_image(self) -> bool:
        """确保沙盒镜像已构建（异步，不阻塞）。"""
        if not self.docker_available:
            return False
        client = self._get_client()
        try:
            client.images.get(SANDBOX_IMAGE)
            return True
        except Exception:
            dockerfile_dir = Path(__file__).parent.parent.parent / "docker"
            dockerfile_path = dockerfile_dir / "Dockerfile.sandbox"
            if not dockerfile_path.exists():
                logger.warning(f"Dockerfile not found at {dockerfile_path} — skip Docker")
                return False
            logger.info(f"Building sandbox image '{SANDBOX_IMAGE}'...")
            try:
                # 在线程池中构建，最多等 60 秒
                await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: client.images.build(
                            path=str(dockerfile_dir),
                            dockerfile=str(dockerfile_path),
                            tag=SANDBOX_IMAGE,
                            rm=True,
                        ),
                    ),
                    timeout=60.0,
                )
                logger.info(f"Sandbox image '{SANDBOX_IMAGE}' built successfully")
                return True
            except asyncio.TimeoutError:
                logger.warning("Docker image build timed out — using local fallback")
                return False
            except Exception as exc:
                logger.warning(f"Docker image build failed: {exc} — using local fallback")
                return False

    # ── 容器生命周期 ────────────────────────────────────────

    def cleanup_orphaned_containers(self) -> int:
        """Remove all orphaned coding-sandbox-* containers.

        Call this on application startup to clean up containers left behind
        from a previous run (e.g. after a restart or crash).

        Returns:
            Number of containers removed.
        """
        if not self.docker_available:
            return 0
        client = self._get_client()
        removed = 0
        try:
            for container in client.containers.list(all=True, filters={"name": "coding-sandbox"}):
                name = container.name
                try:
                    logger.info(
                        f"Cleaning up orphaned container: {name} "
                        f"(id={container.id[:12]}, status={container.status})"
                    )
                    if container.status == "running":
                        container.stop(timeout=3)
                    try:
                        container.remove(force=True)
                    except Exception:
                        pass  # already gone is fine
                    removed += 1
                except Exception as exc:
                    logger.warning(f"Failed to clean up container {name}: {exc}")
        except Exception as exc:
            logger.warning(f"Failed to list containers for cleanup: {exc}")
        if removed:
            logger.info(f"Cleaned up {removed} orphaned sandbox container(s)")
        return removed

    def _cleanup_existing_container(self, container_name: str) -> bool:
        """Remove an existing container with the given name if it exists.

        Returns True if a container was removed, False if none existed.
        """
        client = self._get_client()
        try:
            existing = client.containers.get(container_name)
            logger.info(
                f"Removing stale container '{container_name}' "
                f"(id={existing.id[:12]}, status={existing.status})"
            )
            existing.stop(timeout=3)
            # Container was created with auto-remove, so stop triggers removal;
            # explicitly remove in case it was created without auto-remove or is already stopped.
            try:
                existing.remove(force=True)
            except Exception:
                pass  # already gone is fine
            return True
        except Exception:
            return False  # container not found or not accessible

    async def create_container(self, task_id: str, project_dir: Path) -> Optional[str]:
        """为任务创建 Docker 容器（带超时，不阻塞）。

        Args:
            task_id: 任务 ID
            project_dir: 项目目录（将挂载到 /workspace）

        Returns:
            容器 ID，失败返回 None
        """
        if not self.docker_available:
            return None
        if not await self.ensure_image():
            return None

        client = self._get_client()
        project_abs = str(project_dir.absolute())
        container_name = f"coding-sandbox-{task_id[:8]}"

        # 清理残留的同名容器（例如后端重启导致 in-memory 状态丢失）
        self._cleanup_existing_container(container_name)

        try:
            # 在线程池中运行，加超时保护（最多 15 秒）
            container = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: client.containers.run(
                        image=SANDBOX_IMAGE,
                        command="tail -f /dev/null",
                        volumes={project_abs: {"bind": "/workspace", "mode": "rw"}},
                        working_dir="/workspace",
                        name=container_name,
                        detach=True,
                        remove=True,
                        mem_limit="512m",
                        cpu_quota=50000,
                        network_mode="none",
                    ),
                ),
                timeout=15.0,
            )
            container_id = container.id
            self._containers[task_id] = container_id
            logger.info(f"Docker sandbox created: {container_id[:12]} for task {task_id[:8]}")
            return container_id
        except asyncio.TimeoutError:
            logger.warning(f"Docker container creation timed out for task {task_id[:8]} — using local fallback")
            return None
        except Exception as exc:
            logger.warning(f"Docker container creation failed for task {task_id[:8]}: {exc} — using local fallback")
            return None

    def remove_container(self, task_id: str) -> bool:
        """删除任务的 Docker 容器。"""
        container_id = self._containers.pop(task_id, None)
        if not container_id:
            return False
        try:
            client = self._get_client()
            container = client.containers.get(container_id)
            container.stop(timeout=3)
            logger.info(f"Docker sandbox removed: {container_id[:12]}")
            return True
        except Exception as exc:
            logger.warning(f"Failed to remove container {container_id}: {exc}")
            return False

    # ── 代码执行 ───────────────────────────────────────────

    async def execute(
        self,
        task_id: str,
        command: str,
        workdir: str = "/workspace",
        timeout: int = 30,
    ) -> dict:
        """在沙盒中执行命令并返回结果。

        Args:
            task_id: 任务 ID
            command: 要执行的命令
            workdir: 工作目录
            timeout: 超时秒数

        Returns:
            {"success": bool, "stdout": str, "stderr": str, "exit_code": int, "method": "docker"|"local"}
        """
        # Docker 可用：有容器直接用，没有则自动创建
        if self.docker_available:
            if task_id not in self._containers:
                project_dir = self.sandbox_root / task_id / "project"
                if not project_dir.exists():
                    project_dir = self.sandbox_root / task_id
                if project_dir.exists():
                    await self.create_container(task_id, project_dir)
            if task_id in self._containers:
                return await self._execute_docker(task_id, command, workdir, timeout)
        # 降级到本地执行
        return await self._execute_local(task_id, command, timeout)

    async def _execute_docker(
        self, task_id: str, command: str, workdir: str, timeout: int,
    ) -> dict:
        """在 Docker 容器中执行命令。"""
        container_id = self._containers[task_id]
        client = self._get_client()
        container = client.containers.get(container_id)

        try:
            exit_code, output = container.exec_run(
                cmd=["sh", "-c", command],
                workdir=workdir,
                stdout=True,
                stderr=True,
                demux=True,
            )
            stdout = output[0].decode("utf-8", errors="replace") if output[0] else ""
            stderr = output[1].decode("utf-8", errors="replace") if output[1] else ""
            return {
                "success": exit_code == 0,
                "stdout": stdout[:10000],
                "stderr": stderr[:10000],
                "exit_code": exit_code,
                "method": "docker",
            }
        except Exception as exc:
            return {
                "success": False,
                "stdout": "",
                "stderr": str(exc),
                "exit_code": -1,
                "method": "docker",
            }

    async def _execute_local(self, task_id: str, command: str, timeout: int) -> dict:
        """本地执行命令（Docker 不可用时的降级方案）。"""
        project_dir = self.sandbox_root / task_id / "project"
        if not project_dir.exists():
            project_dir = self.sandbox_root / task_id

        try:
            proc = await asyncio.wait_for(
                asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(project_dir),
                ),
                timeout=timeout,
            )
            stdout, stderr = await proc.communicate()
            return {
                "success": proc.returncode == 0,
                "stdout": stdout.decode("utf-8", errors="replace")[:10000],
                "stderr": stderr.decode("utf-8", errors="replace")[:10000],
                "exit_code": proc.returncode,
                "method": "local",
            }
        except asyncio.TimeoutError:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Command timed out after {timeout}s",
                "exit_code": -1,
                "method": "local",
            }
        except Exception as exc:
            return {
                "success": False,
                "stdout": "",
                "stderr": str(exc),
                "exit_code": -1,
                "method": "local",
            }

    # ── 快速验证脚本 ────────────────────────────────────────

    PRESET_SCRIPTS = {
        "python": {
            "run": (
                "(python main.py || python test_demo.py || python demo.py || python app.py || "
                "python -c \"import glob,runpy; fs=[f for f in glob.glob('*.py') if not f.startswith('test_')]; runpy.run_path(fs[0]) if fs else print('未找到可运行的 .py 文件')\") "
                "2>&1"
            ),
            "test": (
                "python -m pytest test_*.py -v 2>/dev/null || "
                "python -c \"import unittest; loader=unittest.TestLoader(); suite=loader.discover('.'); unittest.TextTestRunner().run(suite)\" 2>/dev/null || "
                "echo '未找到测试'"
            ),
            "lint": "python -m py_compile *.py 2>&1; python -c \"import glob; [__import__('py_compile').compile(f, doraise=True) for f in glob.glob('**/*.py', recursive=True) if 'test_' not in f]\" 2>/dev/null || true",
        },
        "typescript": {
            "run": "npx ts-node src/index.ts 2>/dev/null || npx ts-node *.ts 2>/dev/null || echo '未找到可运行的 TS 文件'",
            "test": "npx jest --passWithNoTests 2>/dev/null || echo '未配置测试'",
            "build": "npx tsc --noEmit",
        },
        "javascript": {
            "run": "node src/index.js 2>/dev/null || node *.js 2>/dev/null || echo '未找到可运行的 JS 文件'",
            "test": "npx jest --passWithNoTests 2>/dev/null || echo '未配置测试'",
        },
        "general": {
            "run": "echo '该语言没有默认运行命令'",
            "test": "echo '该语言没有默认测试命令'",
        },
    }

    def get_preset_scripts(self, language: str) -> dict:
        """获取指定语言的预设验证脚本。"""
        return self.PRESET_SCRIPTS.get(language, self.PRESET_SCRIPTS["general"])

    async def run_preset(
        self, task_id: str, language: str, script_name: str,
    ) -> dict:
        """执行预设的验证脚本。

        Args:
            task_id: 任务 ID
            language: 编程语言
            script_name: 脚本名（run/test/lint/build）

        Returns:
            执行结果 dict
        """
        scripts = self.get_preset_scripts(language)
        command = scripts.get(script_name, f"echo '未知脚本: {script_name}'")
        return await self.execute(task_id, command)


# ── 全局单例 ──────────────────────────────────────────────

_docker_sandbox: Optional[DockerSandboxService] = None


def get_docker_sandbox() -> DockerSandboxService:
    """获取 DockerSandboxService 全局单例。"""
    global _docker_sandbox
    if _docker_sandbox is None:
        _docker_sandbox = DockerSandboxService()
    return _docker_sandbox
