import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from core.logger import log

if TYPE_CHECKING:
    from .debug_helper import DebugHelper


class VirtualEnvironment:
    """Creates and manages venv for repo."""

    def __init__(self, repo_path: Path):
        self.repo_path = Path(repo_path)
        self.venv_path = self.repo_path / "venv"
        self.project_type = "pip"

    def setup(self) -> bool:
        """Create venv and install dependencies."""
        import time

        start_time = time.time()
        try:
            log("  Setting up venv...")

            if not self._create_venv():
                return False

            self._detect_project_type()
            log(f"  --> Detected: {self.project_type}")

            log("  --> Installing build & test tools...")
            self._install_core_tools()
            log("      --> Done.")

            log("  Installing project dependencies...")
            self._install_dependencies()

            setup_time = time.time() - start_time
            log(f"Environment setup completed in {setup_time:.1f}s")

            self._setup_time = setup_time
            return True

        except subprocess.CalledProcessError as e:
            log(f"  --> CRITICAL FAILURE: command failed: {e.stderr}")
            return False

        except Exception as e:
            setup_time = time.time() - start_time
            self._setup_time = setup_time
            import traceback

            log(f"  --> FATAL ERROR during venv setup.")
            log(f"  --> Type: {type(e).__name__}")
            log(f"  --> Details: {e}")
            log(f"  --> Traceback:\n{traceback.format_exc()}")
            return False

    def get_setup_time(self) -> float:
        """Get time taken for environment setup."""
        return getattr(self, "_setup_time", 0.0)

    def execute_command(
        self,
        command: list[str],
        timeout: int = 1200,
    ) -> subprocess.CompletedProcess:
        """Run command in venv."""
        env = os.environ.copy()
        env.pop("VIRTUAL_ENV", None)  # avoid parent venv conflicts

        bin_dir = "Scripts" if sys.platform == "win32" else "bin"
        venv_bin_path = self.venv_path / bin_dir

        env["PATH"] = f"{venv_bin_path}{os.pathsep}{env['PATH']}"

        # build command based on project type
        if self.project_type == "poetry":
            cmd = ["poetry", "run"] + command
        elif self.project_type == "uv":
            cmd = ["uv", "run"] + command
        else:
            exe = venv_bin_path / command[0]
            cmd = [str(exe)] + command[1:]

        return subprocess.run(
            cmd,
            cwd=self.repo_path,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
            check=True,
        )

    def _create_venv(self) -> bool:
        """Create the virtual environment."""
        if self.venv_path.exists():
            log(f"  --> venv exists: {self.venv_path}")
            return True

        log(f"  --> Creating venv: {self.venv_path}")
        try:
            subprocess.run(
                [sys.executable, "-m", "venv", str(self.venv_path)],
                check=True,
                capture_output=True,
                text=True,
            )
            log("  --> venv created.")
            return True
        except subprocess.CalledProcessError as e:
            log(f"  --> ERROR: Failed to create venv: {e.stderr}")
            return False

    def run_tests(
        self,
        test_command: str,
        config: dict[str, Any],
        repo_name: str,
        commit_sha: str,
        run_type: str,
        debug_helper: "DebugHelper",
    ) -> bool:
        """Run tests with configured exclusions."""
        cmd = test_command.split()
        exclusions = config.get("test_exclusions", {}).get(repo_name, {})

        # add ignored paths
        ignores = exclusions.get("ignore_paths", [])
        if ignores:
            log(f"    --> Ignoring {len(ignores)} path(s)")
            for path in ignores:
                cmd.extend(["--ignore", path])

        # add deselected tests
        deselects = exclusions.get("deselect_nodes", [])
        if deselects:
            log(f"    --> Deselecting {len(deselects)} test(s).")
            for test in deselects:
                cmd.extend(["--deselect", test])

        try:
            result = self.execute_command(cmd)
            summary = self._extract_summary(result.stdout)
            log(f"    --> Tests PASSED: {summary}")
            return True

        except subprocess.CalledProcessError as e:
            log(f"    --> Tests FAILED: {e.returncode}")
            log_path = debug_helper.save_test_failure_log(
                repo_name, commit_sha, run_type, e
            )
            log(f"    --> Logs: {log_path}")
            return False

    def _extract_summary(self, stdout: str) -> str:
        """Extract the pytest summary line"""
        for line in stdout.splitlines():
            if "passed" in line and "in" in line and "s" in line:
                return line.strip("=")
        return "No summary found."

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

    def _install_core_tools(self):
        """Install core build and test tools into venv."""
        bin_dir = "Scripts" if sys.platform == "win32" else "bin"
        pip_exe = self.venv_path / bin_dir / "pip"

        subprocess.run(
            [
                str(pip_exe),
                "install",
                "--upgrade",
                "pip",
                "poetry",
                "uv",
                "pytest",
                "pytest-cov",
                "pytest-xdist",  # +pytest-sugar later?
                "anyio",
            ],
            check=True,
            capture_output=True,
            text=True,
            cwd=self.repo_path,
        )

    def _install_dependencies(self):
        """Install project deps based on detected type."""
        pyproject_path = self.repo_path / "pyproject.toml"

        if self.project_type == "poetry":
            log("  Poetry: installing with 'poetry install'...")
            self.execute_command(["poetry", "install"])
            return

        if self.project_type == "uv":
            log("  UV: installing with 'uv sync'...")
            self.execute_command(["uv", "sync"])
            return

        req = self._find_requirements()
        if req:
            log(f"  Found: '{req.name}', installing...")
            # try installing package first
            try:
                self.execute_command(["pip", "install", "-e", "."])
            except subprocess.CalledProcessError:
                log("  --> WARNING: 'pip install -e .' failed, continuing...")

            self.execute_command(["pip", "install", "-r", str(req)])
            return

        if pyproject_path.exists():
            log("  --> Fallback: installing from pyproject.toml...")
            try:
                self.execute_command(
                    ["pip", "install", "-e", ".[dev,test,tests,typing]"]
                )
            except subprocess.CalledProcessError:
                log("  --> WARNING: Installing with extras failed, trying without...")
                self.execute_command(["pip", "install", "-e", "."])
            return

        log("  --> Warning: No dependency method found.")

    def _find_requirements(self) -> Path | None:
        """Find requirements file."""
        patterns = [
            "*requirements-dev.txt",
            "*requirements_dev.txt",
            "*requirements-test*.txt",
            "*test-requirements.txt",
            "*requirements.txt",
        ]

        for pattern in patterns:
            for match in self.repo_path.glob(pattern):
                return match

        req_dir = self.repo_path / "requirements"
        if req_dir.exists():
            for pattern in patterns:
                for match in req_dir.glob(pattern):
                    return match

        return None

    def cleanup(self):
        """Delete venv."""
        if self.venv_path.exists():
            log(f"  --> Removing venv: {self.venv_path}")
            shutil.rmtree(self.venv_path, ignore_errors=True)
