"""沙盒服务 — 为每个编码任务创建隔离的项目目录。

每个沙盒包含：
- TEAM.md（问题描述和上下文）
- project/（代码项目脚手架）
"""

import logging
import shutil
from pathlib import Path
from typing import Optional

from ..config import get_settings

logger = logging.getLogger(__name__)

# ── 语言脚手架模板 ──────────────────────────────────────────

SCAFFOLD_TEMPLATES = {
    "python": {
        "files": {
            "project/pyproject.toml": (
                '[build-system]\nrequires = ["setuptools>=64.0"]\nbuild-backend = "setuptools.build_meta"\n\n'
                '[project]\nname = "sandbox-project"\nversion = "0.1.0"\nrequires-python = ">=3.10"\n'
            ),
            "project/src/__init__.py": "# Package init — coding agents will add modules here\n",
            "project/README.md": (
                "# 沙盒项目 (Python)\n\n"
                "在 `src/` 目录下编写你的实现代码。\n"
                "Leader 会告诉你需要创建哪些文件。\n"
                "完成后在 complete_task 中列出你的文件路径。\n"
            ),
        },
        "dirs": ["project/src"],
    },
    "typescript": {
        "files": {
            "project/package.json": (
                '{\n  "name": "sandbox-project",\n  "version": "1.0.0",\n  "main": "src/index.ts",\n'
                '  "scripts": {\n    "build": "tsc",\n    "start": "node dist/index.js"\n  },\n'
                '  "devDependencies": {\n    "typescript": "^5.0.0"\n  }\n}\n'
            ),
            "project/tsconfig.json": (
                '{\n  "compilerOptions": {\n    "target": "ES2022",\n    "module": "commonjs",\n'
                '    "outDir": "./dist",\n    "rootDir": "./src",\n    "strict": true,\n'
                '    "esModuleInterop": true\n  },\n  "include": ["src/**/*"]\n}\n'
            ),
            "project/README.md": (
                "# 沙盒项目 (TypeScript)\n\n"
                "在 `src/` 目录下编写你的实现代码。\n"
                "Leader 会告诉你需要创建哪些文件。\n"
                "完成后在 complete_task 中列出你的文件路径。\n"
            ),
            "project/src/.gitkeep": "",
        },
        "dirs": ["project/src"],
    },
    "javascript": {
        "files": {
            "project/package.json": (
                '{\n  "name": "sandbox-project",\n  "version": "1.0.0",\n  "main": "src/index.js",\n'
                '  "scripts": {\n    "start": "node src/index.js"\n  }\n}\n'
            ),
            "project/README.md": (
                "# 沙盒项目 (JavaScript)\n\n"
                "在 `src/` 目录下编写你的实现代码。\n"
                "Leader 会告诉你需要创建哪些文件。\n"
                "完成后在 complete_task 中列出你的文件路径。\n"
            ),
            "project/src/.gitkeep": "",
        },
        "dirs": ["project/src"],
    },
    "rust": {
        "files": {
            "project/Cargo.toml": (
                '[package]\nname = "sandbox-project"\nversion = "0.1.0"\nedition = "2021"\n\n[dependencies]\n'
            ),
            "project/README.md": (
                "# 沙盒项目 (Rust)\n\n"
                "在 `src/` 目录下编写你的实现代码。\n"
                "Leader 会告诉你需要创建哪些文件。\n"
                "完成后在 complete_task 中列出你的文件路径。\n"
            ),
            "project/src/.gitkeep": "",
        },
        "dirs": ["project/src"],
    },
    "go": {
        "files": {
            "project/go.mod": "module sandbox-project\n\ngo 1.21\n",
            "project/README.md": (
                "# 沙盒项目 (Go)\n\n"
                "在项目目录下编写你的实现代码。\n"
                "The Architect will tell you which files to create.\n"
                "When done, list your file paths in complete_task.\n"
            ),
        },
        "dirs": [],
    },
    "java": {
        "files": {
            "project/README.md": (
                "# 沙盒项目 (Java)\n\n"
                "在项目目录下编写你的实现代码。\n"
                "The Architect will tell you which files to create.\n"
                "When done, list your file paths in complete_task.\n"
            ),
        },
        "dirs": [],
    },
    "cpp": {
        "files": {
            "project/CMakeLists.txt": (
                'cmake_minimum_required(VERSION 3.15)\nproject(SandboxProject)\n\nadd_executable(main main.cpp)\n'
            ),
            "project/README.md": (
                "# 沙盒项目 (C++)\n\n"
                "在项目目录下编写你的实现代码。\n"
                "The Architect will tell you which files to create.\n"
                "When done, list your file paths in complete_task.\n"
            ),
            "project/src/.gitkeep": "",
        },
        "dirs": ["project/src"],
    },
    "web": {
        "files": {
            "project/package.json": (
                '{\n  "name": "sandbox-project",\n  "version": "1.0.0",\n'
                '  "scripts": {\n    "start": "node src/index.js"\n  }\n}\n'
            ),
            "project/README.md": (
                "# 沙盒项目 (Web)\n\n"
                "在项目目录下编写你的 HTML/CSS/JS 代码。\n"
                "The Architect will tell you which files to create.\n"
                "When done, list your file paths in complete_task.\n"
            ),
            "project/src/.gitkeep": "",
        },
        "dirs": ["project/src"],
    },
    "general": {
        "files": {
            "project/README.md": (
                "# 沙盒项目\n\n"
                "在项目目录下编写你的实现代码。\n"
                "The Architect will tell you which files to create.\n"
                "When done, list your file paths in complete_task.\n"
            ),
        },
        "dirs": ["project/src"],
    },
}


class SandboxService:
    """管理编码任务的隔离工作目录。"""

    def __init__(self, sandbox_root: Optional[Path] = None):
        settings = get_settings()
        self.sandbox_root = sandbox_root or settings.sandbox_root
        self.sandbox_root.mkdir(parents=True, exist_ok=True)

    # ── 沙盒生命周期 ─────────────────────────────────────────

    def create_sandbox(
        self,
        task_id: str,
        language: str,
        problem_description: str,
    ) -> Path:
        """创建沙盒目录并初始化项目脚手架。

        Args:
            task_id: 编码任务 ID
            language: 编程语言
            problem_description: 问题描述（写入 TEAM.md）

        Returns:
            沙盒根目录路径
        """
        sandbox_path = self.sandbox_root / task_id
        sandbox_path.mkdir(parents=True, exist_ok=True)

        # ── 写入 TEAM.md ──
        team_md = self._build_team_md(problem_description, language)
        (sandbox_path / "TEAM.md").write_text(team_md, encoding="utf-8")

        # ── 初始化项目脚手架 ──
        template = SCAFFOLD_TEMPLATES.get(language, SCAFFOLD_TEMPLATES["general"])

        for dir_path in template.get("dirs", []):
            (sandbox_path / dir_path).mkdir(parents=True, exist_ok=True)

        for file_path, content in template.get("files", {}).items():
            full_path = sandbox_path / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content, encoding="utf-8")

        logger.info(f"Sandbox created: {sandbox_path} (language={language})")
        return sandbox_path

    def clone_sandbox(
        self,
        source_task_id: str,
        dest_task_id: str,
        language: str,
        problem_description: str,
    ) -> Path:
        """从已有任务克隆沙盒到新任务目录。

        深拷贝源沙盒的所有文件，删除旧的 team.db（让新 run 从干净状态开始），
        覆盖 TEAM.md 和 problem.txt 为新任务描述。

        Args:
            source_task_id: 源任务 ID
            dest_task_id: 新任务 ID
            language: 编程语言
            problem_description: 新任务描述

        Returns:
            新沙盒根目录路径
        """
        source_path = self.sandbox_root / source_task_id
        dest_path = self.sandbox_root / dest_task_id

        if not source_path.exists():
            raise ValueError(f"源沙盒不存在: {source_task_id}")

        # 深拷贝源沙盒
        shutil.copytree(source_path, dest_path, dirs_exist_ok=True)

        # 删除旧的 team.db（新 run 用干净数据库）
        old_db = dest_path / "team.db"
        if old_db.exists():
            old_db.unlink()
        old_mailbox_db = dest_path / "coding-web-team_mailbox.db"
        if old_mailbox_db.exists():
            old_mailbox_db.unlink()

        # 覆盖 TEAM.md 为新任务描述
        team_md = self._build_team_md(problem_description, language)
        (dest_path / "TEAM.md").write_text(team_md, encoding="utf-8")

        # 覆盖 problem.txt 为新任务描述
        project_dir = dest_path / "project"
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "problem.txt").write_text(problem_description, encoding="utf-8")

        logger.info(f"Sandbox cloned: {source_task_id} -> {dest_task_id}")
        return dest_path

    def delete_sandbox(self, task_id: str) -> bool:
        """删除沙盒目录及其所有内容。

        Args:
            task_id: 编码任务 ID

        Returns:
            是否成功删除
        """
        sandbox_path = self.sandbox_root / task_id
        if not sandbox_path.exists():
            return False
        try:
            shutil.rmtree(sandbox_path, ignore_errors=True)
            logger.info(f"Sandbox deleted: {sandbox_path}")
            return True
        except Exception as exc:
            logger.error(f"Failed to delete sandbox {sandbox_path}: {exc}")
            return False

    def sandbox_exists(self, task_id: str) -> bool:
        """检查沙盒目录是否存在。"""
        return (self.sandbox_root / task_id).exists()

    # ── 文件操作 ─────────────────────────────────────────────

    def get_file_tree(self, task_id: str) -> list[dict]:
        """获取沙盒的文件树结构。

        Args:
            task_id: 编码任务 ID

        Returns:
            文件树节点列表，每个节点有 name、path、type（file/dir）、children
        """
        sandbox_path = self.sandbox_root / task_id
        if not sandbox_path.exists():
            return []

        return self._build_tree(sandbox_path, sandbox_path)

    def read_file(self, task_id: str, relative_path: str) -> Optional[str]:
        """读取沙盒中的文件内容。

        Args:
            task_id: 编码任务 ID
            relative_path: 相对于沙盒根目录的文件路径

        Returns:
            文件内容字符串，文件不存在则返回 None
        """
        sandbox_path = self.sandbox_root / task_id
        file_path = sandbox_path / relative_path

        # 安全检查：确保文件在沙盒内
        try:
            file_path.resolve().relative_to(sandbox_path.resolve())
        except ValueError:
            logger.warning(f"Path traversal attempt: {relative_path}")
            return None

        if not file_path.exists() or not file_path.is_file():
            return None

        try:
            return file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return f"[Binary file: {file_path.name}]"
        except Exception as exc:
            logger.error(f"Failed to read {file_path}: {exc}")
            return None

    def write_file(self, task_id: str, relative_path: str, content: str) -> bool:
        """向沙盒写入文件。

        Args:
            task_id: 编码任务 ID
            relative_path: 相对于沙盒根目录的文件路径
            content: 文件内容

        Returns:
            是否成功写入
        """
        sandbox_path = self.sandbox_root / task_id
        file_path = sandbox_path / relative_path

        try:
            file_path.resolve().relative_to(sandbox_path.resolve())
        except ValueError:
            logger.warning(f"Path traversal attempt: {relative_path}")
            return False

        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            return True
        except Exception as exc:
            logger.error(f"Failed to write {file_path}: {exc}")
            return False

    # ── 私有方法 ─────────────────────────────────────────────

    def _build_tree(self, root: Path, current: Path) -> list[dict]:
        """递归构建文件树。"""
        items = []
        try:
            entries = sorted(current.iterdir(), key=lambda p: (p.is_file(), p.name))
        except PermissionError:
            return items

        for entry in entries:
            # 跳过隐藏文件和 team.db
            if entry.name.startswith(".") or entry.name == "team.db":
                continue

            rel_path = str(entry.relative_to(root)).replace("\\", "/")
            if entry.is_dir():
                items.append({
                    "name": entry.name,
                    "path": rel_path,
                    "type": "dir",
                    "children": self._build_tree(root, entry),
                })
            else:
                items.append({
                    "name": entry.name,
                    "path": rel_path,
                    "type": "file",
                    "children": [],
                })
        return items

    @staticmethod
    def _build_team_md(problem_description: str, language: str) -> str:
        """生成 TEAM.md 内容。"""
        return (
            f"# 编码任务\n\n"
            f"**语言:** {language}\n\n"
            f"## 问题描述\n\n"
            f"{problem_description}\n\n"
            f"## 工作目录\n\n"
            f"项目脚手架已创建在 `project/` 目录下。\n"
            f"在对应的源文件中编写代码。\n\n"
            f"## 指南\n\n"
            f"1. 修改前先 read_file 阅读已有代码\n"
            f"2. 编写干净、有注释的代码\n"
            f"3. 包含适当的错误处理\n"
            f"4. 需要协作时用 send_message 与队友沟通\n"
        )
