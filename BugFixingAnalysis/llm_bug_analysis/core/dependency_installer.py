import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from .logger import log

if TYPE_CHECKING:
    from .terminal_manager import TerminalManager


class DependencyInstaller:
    """Manages dependency installation for a virtual environment."""

    def __init__(
        self,
        repo_path: Path,
        venv_path: Path,
        repo_name: str,
        project_type: str,
        terminal_manager: TerminalManager | None = None,
    ):
        self.repo_path = repo_path
        self.venv_path = venv_path
        self.repo_name = repo_name
        self.project_type = project_type
        self.terminal_manager = terminal_manager

    def _install_dependencies(self):
        """Install project dependencies based on detected type."""
        if self.project_type == "poetry":
            self._install_with_poetry()
        elif self.project_type == "uv":
            self._install_with_uv()
        else:
            self._install_with_pip()

    def _install_core_tools(self):
        """Install core build and test tools into venv."""
        uv_path = self._get_uv_path()

        # minimal core packages needed for most test suites
        packages = [
            "pytest",  # test runner
            "pytest-cov",  # coverage reporting
            "pytest-timeout",  # prevent hanging tests
            "mock",  # legacy unittest.mock
            "sniffio",  # async loop detection
        ]

        cmd = [
            uv_path,
            "pip",
            "install",
            "--python",
            str(self.venv_path / "bin" / "python"),
        ] + packages

        title = f"Install tools"
        self._execute_install(cmd, title)

    def _install_with_poetry(self):
        """Install dependencies using Poetry."""
        log("  poetry: installing with 'poetry install'...")
        poetry_cmd = self._get_poetry_path()
        cmd = [poetry_cmd, "install"]
        title = f"poetry install: {self.repo_path.name}"

        # poetry handles both deps and package installation
        self._execute_install(cmd, title, poetry=True)

    def _install_with_uv(self):
        """Install dependencies using UV."""
        log("  uv: installing with 'uv sync'...")
        uv_path = self._get_uv_path()
        cmd = [uv_path, "sync", "--all-extras"]
        title = f"uv sync: {self.repo_path.name}"

        # uv sync handles both deps and package installation
        self._execute_install(cmd, title, uv_project=True)

    def _install_with_pip(self):
        """Install dependencies using (uv) pip."""
        self._install_requirements_if_exists()
        self._install_package_if_exists()

    def _install_requirements_if_exists(self):
        """Install from *requirements*.txt if it exists."""
        req = self._find_requirements()
        if not req:
            return

        log(f"  Found: '{req.name}', installing dependencies...")
        uv_path = self._get_uv_path()
        python_path = str(self.venv_path / "bin" / "python")

        cmd = [uv_path, "pip", "install", "--python", python_path, "-r", str(req)]
        title = f"uv pip install requirements: {self.repo_path.name}"
        self._execute_install(cmd, title)

    def _install_package_if_exists(self):
        """Install package in editable mode if setup.py/pyproject.toml exists."""
        pyproject_path = self.repo_path / "pyproject.toml"
        setup_py_path = self.repo_path / "setup.py"

        if not (pyproject_path.exists() or setup_py_path.exists()):
            log(
                "  --> Warning: No package definition found (no pyproject.toml or setup.py)"
            )
            return

        log("  --> Installing package in editable mode...")

        # determine install specification
        install_spec = self._build_install_spec(pyproject_path)
        self._execute_package_install(pyproject_path, install_spec)

    def _build_install_spec(self, pyproject_path: Path) -> str:
        """Build the install specification (e.g., '.[test,dev]')."""
        has_dep_groups = self._check_dependency_groups(pyproject_path)
        available_extras = self._get_available_extras(pyproject_path)

        # dependency-groups
        if has_dep_groups:
            if available_extras:
                extras_str = ",".join(available_extras)
                log(f"  --> Also installing extras: {extras_str}")
                return f".[{extras_str}]"
            return "."

        # optional-dependencies
        if available_extras:
            extras_str = ",".join(available_extras)
            log(f"  --> Installing with extras: {extras_str}")
            return f".[{extras_str}]"

        # plain editable install
        return "."

    def _execute_package_install(self, pyproject_path: Path, install_spec: str):
        """Execute the package installation command."""
        uv_path = self._get_uv_path()
        python_path = str(self.venv_path / "bin" / "python")

        cmd = [uv_path, "pip", "install", "--python", python_path, "-e", install_spec]

        has_dep_groups = self._check_dependency_groups(pyproject_path)
        if has_dep_groups:
            cmd.extend(["--group", "test"])
            title = f"uv pip install package (dep-groups): {self.repo_path.name}"
        elif "[" in install_spec:
            title = f"uv pip install package (extras): {self.repo_path.name}"
        else:
            title = f"uv pip install package: {self.repo_path.name}"

        self._execute_install(cmd, title)

    def _execute_install(
        self, cmd: list[str], title: str, poetry: bool = False, uv_project: bool = False
    ):
        """Execute an install command (helper to reduce duplication)."""
        if self.terminal_manager:

            if uv_project:
                env = {"UV_PROJECT_ENVIRONMENT": str(self.venv_path)}
            elif poetry:
                env = {"VIRTUAL_ENV": str(self.venv_path)}
            else:
                env = None

            process = self.terminal_manager.queue_command(
                cmd,
                title=title,
                cwd=self.repo_path,
                timeout=1200,
                env=env,
                repo_name=self.repo_name,
            )
            if process.returncode != 0:
                raise subprocess.CalledProcessError(process.returncode, cmd, "", "")
        else:
            if uv_project:
                env = os.environ.copy()
                env["UV_PROJECT_ENVIRONMENT"] = str(self.venv_path)
            elif poetry:
                env = os.environ.copy()
                env["VIRTUAL_ENV"] = str(self.venv_path)
            else:
                env = None

            subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                cwd=self.repo_path,
                env=env,
            )

    @staticmethod
    def _get_uv_path() -> str:
        """Get the path to uv executable."""

        try:
            result = subprocess.run(
                ["bash", "-c", "which uv"],
                capture_output=True,
                text=True,
                check=True,
            )
            uv_path = result.stdout.strip()
            if uv_path:
                return uv_path
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

        possible_paths = [
            Path.home() / ".local" / "bin" / "uv",
            Path.home() / ".cargo" / "bin" / "uv",
            Path("/usr/local/bin/uv"),
            Path("/usr/bin/uv"),
        ]

        for path in possible_paths:
            if path.exists():
                return str(path)

        return "uv"

    def _get_poetry_path(self) -> str:
        """Get poetry executable path (system-wide or install in venv)."""

        # check if poetry exists globally
        try:
            result = subprocess.run(
                ["which", "poetry"],
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )
            poetry_path = result.stdout.strip()
            if poetry_path:
                log(f"  --> Using system poetry: {poetry_path}")
                return poetry_path

        except (subprocess.CalledProcessError, FileNotFoundError):
            log("  --> System poetry not found")

        # check if already installed in venv
        venv_poetry = self.venv_path / "bin" / "poetry"
        if venv_poetry.exists():
            log("  --> Using venv poetry")
            return str(venv_poetry)

        # install poetry in venv as fallback
        log("  --> Installing poetry in venv...")
        uv_path = self._get_uv_path()
        python_path = str(self.venv_path / "bin" / "python")

        subprocess.run(
            [uv_path, "pip", "install", "--python", python_path, "poetry"],
            check=True,
            capture_output=True,
            text=True,
            cwd=self.repo_path,
            timeout=120,
        )

        log("  --> Poetry installed in venv")
        return str(venv_poetry)

    def _get_available_extras(self, pyproject_path: Path) -> list[str]:
        """Get list of available extras from pyproject.toml."""
        try:
            import tomllib
        except ImportError:
            try:
                import tomli as tomllib
            except ImportError:
                return []

        try:
            with open(pyproject_path, "rb") as f:
                data = tomllib.load(f)

            extras = []

            # check [project.optional-dependencies]
            if "project" in data and "optional-dependencies" in data["project"]:
                extras.extend(data["project"]["optional-dependencies"].keys())

            if extras:
                log(f"  --> Found optional-dependencies: {extras}")

            return extras

        except Exception as e:
            log(f"  --> Error reading extras: {e}")
            return []

    def _check_dependency_groups(self, pyproject_path: Path) -> bool:
        """Check if pyproject.toml has [dependency-groups]."""
        try:
            import tomllib
        except ImportError:
            try:
                import tomli as tomllib
            except ImportError:
                return False

        try:
            with open(pyproject_path, "rb") as f:
                data = tomllib.load(f)

            if "dependency-groups" in data:
                groups = list(data["dependency-groups"].keys())
                log(f"  --> Found dependency-groups: {groups}")
                return True

            return False

        except Exception as e:
            log(f"  --> Error checking dependency-groups: {e}")
            return False

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
