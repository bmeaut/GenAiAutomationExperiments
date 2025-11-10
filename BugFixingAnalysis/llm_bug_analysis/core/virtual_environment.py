import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .logger import log
from .terminal_manager import TerminalManager
from .dependency_installer import DependencyInstaller
from .test_executor import TestExecutor

if TYPE_CHECKING:
    from .debug_helper import DebugHelper


class VirtualEnvironment:
    """Creates and manages venv for repo."""

    def __init__(
        self,
        repo_path: Path,
        terminal_manager: TerminalManager | None = None,
        repo_name: str | None = None,
    ):
        self.repo_path = Path(repo_path)
        self.venv_path = self.repo_path / ".venv"
        self.project_type = "pip"
        self.terminal_manager = terminal_manager

        if repo_name:
            self.repo_name = repo_name.replace("/", "_")
        else:
            self.repo_name = self.repo_path.name

    def setup(self) -> bool:
        """Create venv and install dependencies."""
        import time

        start_time = time.time()
        try:
            log("  Setting up venv...")
            if not self._create_venv():
                return False
            log("  Virtual environment created.")

            self._detect_project_type()
            log(f"  --> Detected: {self.project_type}")

            installer = DependencyInstaller(
                self.repo_path,
                self.venv_path,
                self.repo_name,
                self.project_type,
                self.terminal_manager,
            )

            log("  Installing project dependencies...")
            installer._install_dependencies()
            log("      --> Done.")

            log("  --> Installing build & test tools...")
            installer._install_core_tools()
            log("      --> Done.")

            setup_time = time.time() - start_time
            log(f"Environment setup completed in {setup_time:.1f}s")

            self._setup_time = setup_time
            return True

        except subprocess.CalledProcessError as e:
            setup_time = time.time() - start_time
            self._setup_time = setup_time
            log(f"  --> ERROR after {setup_time:.1f}s: {e.stderr}")
            return False

        except Exception as e:
            setup_time = time.time() - start_time
            self._setup_time = setup_time
            import traceback

            log(f"  --> ERROR after {setup_time:.1f}s:")
            log(f"  --> Type: {type(e).__name__}")
            log(f"  --> Details: {e}")
            log(f"  --> Traceback:\n{traceback.format_exc()}")
            return False

    def run_tests(
        self,
        test_command: str,
        config: dict[str, Any],
        repo_name: str,
        commit_sha: str,
        run_type: str,
        debug_helper: DebugHelper,
    ) -> tuple[bool, dict[str, int]]:
        """Run tests with configured exclusions."""
        executor = TestExecutor(
            self.repo_path,
            self.venv_path,
            self.repo_name,
            self.terminal_manager,
        )

        return executor.run_tests(
            test_command, config, repo_name, commit_sha, run_type, debug_helper
        )

    def get_setup_time(self) -> float:
        """Get time taken for environment setup."""
        return getattr(self, "_setup_time", 0.0)

    def cleanup(self):
        """Delete venv."""
        if self.venv_path.exists():
            log(f"  --> Removing venv: {self.venv_path}")
            shutil.rmtree(self.venv_path, ignore_errors=True)

    def _create_venv(self) -> bool:
        """Create the virtual environment."""
        if self.venv_path.exists():
            log(f"  --> venv exists: {self.venv_path}")
            return True

        log(f"  --> Creating venv: {self.venv_path}")
        try:
            uv_path = DependencyInstaller._get_uv_path()
            subprocess.run(
                [uv_path, "venv", str(self.venv_path)],
                check=True,
                capture_output=True,
                text=True,
                cwd=self.repo_path,
            )
            log("  --> venv created.")
            return True
        except subprocess.CalledProcessError as e:
            log(f"  --> ERROR: Failed to create venv: {e.stderr}")
            return False

    def _detect_project_type(self):
        """Detect poetry, uv or pip project."""
        pyproject = self.repo_path / "pyproject.toml"

        if pyproject.exists():
            content = pyproject.read_text(encoding="utf-8")
            if "[tool.poetry]" in content:
                self.project_type = "poetry"
                return
            if (self.repo_path / "uv.lock").exists():
                self.project_type = "uv"
                return

        self.project_type = "pip"
