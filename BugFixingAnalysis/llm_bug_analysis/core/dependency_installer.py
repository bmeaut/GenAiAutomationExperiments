from __future__ import annotations
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
        poetry_cmd = self._get_poetry_path()

        # regenerate lock file for consistency
        # TODO: no reason for lock file if I just regenerate it
        # TODO: (maybe) remove pip/uv/poetry logic, just use uv pip
        log("  poetry: regenerating lock file...")
        lock_cmd = [poetry_cmd, "lock", "--regenerate"]
        lock_title = f"poetry lock --regenerate: {self.repo_path.name}"
        self._execute_install(lock_cmd, lock_title, poetry=True)

        log("  poetry: installing dependencies...")
        cmd = [poetry_cmd, "install"]  # --no-root?
        title = f"poetry install: {self.repo_path.name}"
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
        requirements = self._find_all_requirements()
        if not requirements:
            log("  --> No requirements files found")
            return

        for req_file in requirements:
            rel_path = req_file.relative_to(self.repo_path)
            log(f"  Installing from: '{rel_path}'...")
            self._install_single_requirements_file(req_file)

    def _install_single_requirements_file(self, req_file: Path):
        """Install dependencies from a single requirements file."""
        uv_path = self._get_uv_path()
        python_path = str(self.venv_path / "bin" / "python")

        cmd = [uv_path, "pip", "install", "--python", python_path, "-r", str(req_file)]

        rel_path = req_file.relative_to(self.repo_path)
        title = f"uv pip install -r {rel_path}: {self.repo_path.name}"

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
        if not pyproject_path.exists():
            return "."

        dep_groups = self._check_dependency_groups(pyproject_path)
        available_extras = self._get_available_extras(pyproject_path)

        # dependency-groups
        if dep_groups:
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

        if pyproject_path.exists():
            dep_groups = self._check_dependency_groups(pyproject_path)
            test_groups = ["test", "tests", "testing", "dev"]
            found_groups = [g for g in test_groups if g in dep_groups]
            if found_groups:
                for group in found_groups:
                    cmd.extend(["--group", group])
                title = f"uv pip install package (dep-groups): {self.repo_path.name}"
            elif "[" in install_spec:
                title = f"uv pip install package (extras): {self.repo_path.name}"
            else:
                title = f"uv pip install package: {self.repo_path.name}"
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

    def _check_dependency_groups(self, pyproject_path: Path) -> list[str]:
        """Check if pyproject.toml has [dependency-groups]."""
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

            if "dependency-groups" in data:
                groups = list(data["dependency-groups"].keys())
                log(f"  --> Found dependency-groups: {groups}")
                return groups

            return []

        except Exception as e:
            log(f"  --> Error checking dependency-groups: {e}")
            return []

    def _find_all_requirements(self) -> list[Path]:
        """Find all requirements files."""
        found = []
        searched_patterns = []
        patterns = [
            "requirements/py*.txt",
            "tests/requirements/py*.txt",
            "requirements/dev.txt",
            "requirements/testing.txt",
            "*requirements-dev.txt",
            "*requirements_dev.txt",
            "*requirements-test*.txt",
            "*test-requirements.txt",
            "*requirements.txt",
        ]

        for pattern in patterns:
            matches = list(self.repo_path.glob(pattern))
            searched_patterns.append(pattern)

            for match in matches:
                if match not in found:
                    found.append(match)

        req_dir = self.repo_path / "requirements"
        if req_dir.exists() and req_dir.is_dir():
            for pattern in patterns:
                matches = list(req_dir.glob(pattern))
                for match in matches:
                    if match not in found:
                        found.append(match)

        if found:
            log(f"  --> Found {len(found)} requirements file(s):")
            for req_file in found:
                rel_path = req_file.relative_to(self.repo_path)
                log(f"      - {rel_path}")

        return found
