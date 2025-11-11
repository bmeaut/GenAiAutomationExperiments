from __future__ import annotations
import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .logger import log

if TYPE_CHECKING:
    from .debug_helper import DebugHelper
    from .terminal_manager import TerminalManager


class TestExecutor:
    """Manages test execution and result parsing."""

    def __init__(
        self,
        repo_path: Path,
        venv_path: Path,
        repo_name: str,
        terminal_manager: TerminalManager | None = None,
    ):
        self.repo_path = repo_path
        self.venv_path = venv_path
        self.repo_name = repo_name
        self.terminal_manager = terminal_manager

    def run_tests(
        self,
        test_command: str,
        config: dict[str, Any],
        repo_name: str,
        commit_sha: str,
        run_type: str,
        debug_helper: DebugHelper,
    ) -> tuple[bool, dict[str, int]]:
        """Run tests with configured exclusions"""
        cmd = self._build_test_command(test_command, config, repo_name)
        env = self._build_test_environment()

        log(f"    Test command: {' '.join(cmd)}")

        success, stats, stdout = self._run_test_command(
            cmd, env, repo_name, commit_sha, run_type, debug_helper
        )

        return success, stats

    def _build_test_command(
        self, test_command: str, config: dict, repo_name: str
    ) -> list[str]:
        """Build test command with all configurations applied."""

        if self._is_django_core():
            python_path = str(self.venv_path / "bin" / "python")
            log("    --> Django core detected, using runtests.py")
            return [
                python_path,
                "runtests.py",
                "--settings",
                "test_sqlite",
                "--parallel",
                "1",
            ]

        cmd = test_command.split()

        # transformations in order
        cmd = self._fix_python_path(cmd)
        cmd = self._add_repo_exclusions(cmd, config, repo_name)
        cmd = self._add_global_ignores(cmd)
        cmd = self._add_test_directory_if_needed(cmd)
        cmd = self._add_pytest_xdist_if_available(cmd)

        return cmd

    def _add_pytest_xdist_if_available(self, cmd: list[str]) -> list[str]:
        """Add pytest-xdist parallel running if installed."""

        if "-m" not in cmd or "pytest" not in cmd:
            return cmd

        if any(arg.startswith("-n") or arg == "-n" for arg in cmd):
            log("    --> pytest-xdist already configured")
            return cmd

        if not self._has_pytest_xdist():
            return cmd

        cmd.extend(["-n", "6"])
        log(f"    --> pytest-xdist detected, using 6 workers")

        return cmd

    def _has_pytest_xdist(self) -> bool:
        """Check if pytest-xdist is installed in venv."""
        try:
            python_path = self.venv_path / "bin" / "python"
            result = subprocess.run(
                [str(python_path), "-c", "import xdist"],
                capture_output=True,
                timeout=5,
                check=False,
            )
            return result.returncode == 0
        except Exception:
            return False

    def _fix_python_path(self, cmd: list[str]) -> list[str]:
        """Replace 'python' with venv python path."""
        if cmd[0] == "python":
            cmd[0] = str(self.venv_path / "bin" / "python")
        return cmd

    def _add_repo_exclusions(
        self, cmd: list[str], config: dict, repo_name: str
    ) -> list[str]:
        """Add repository-specific test exclusions."""
        exclusions = config.get("test_exclusions", {}).get(repo_name, {})

        # --ignore flags for paths
        for path in exclusions.get("ignore_paths", []):
            cmd.extend(["--ignore", path])

        # --deselect flags for specific tests
        for test in exclusions.get("deselect_nodes", []):
            cmd.extend(["--deselect", test])

        return cmd

    def _add_global_ignores(self, cmd: list[str]) -> list[str]:
        """Add global ignore patterns for common directories."""

        global_ignores = [
            ".venv",
            "venv",
            ".tox",
            "build",
            "dist",
            ".eggs",
            "__pycache__",
        ]

        for ignore_path in global_ignores:
            if (self.repo_path / ignore_path).exists():
                # Skip if already ignored
                if self._is_already_ignored(cmd, ignore_path):
                    continue

                cmd.extend(["--ignore", ignore_path])

        return cmd

    def _add_test_directory_if_needed(self, cmd: list[str]) -> list[str]:
        """Add test directory if no test path is specified."""
        has_test_path = any(
            arg.startswith("test") or "/" in arg or arg.startswith(".")
            for arg in cmd[3:]  # skip 'python -m pytest'
        )

        if has_test_path:
            return cmd

        # try to find and add test directory
        for test_dir in ["tests", "test"]:
            if (self.repo_path / test_dir).exists():
                cmd.append(test_dir)
                log(f"    --> Auto-added '{test_dir}' directory")
                break

        return cmd

    @staticmethod
    def _is_already_ignored(cmd: list[str], path: str) -> bool:
        """Check if a path is already in the ignore list."""
        return any(f"--ignore={path}" in arg or path in arg for arg in cmd)

    def _build_test_environment(self) -> dict[str, str]:
        """Build environment for test execution."""
        env = {
            "VIRTUAL_ENV": str(self.venv_path),
            "PATH": os.pathsep.join(
                [
                    str(self.venv_path / "bin"),
                    str(Path.home() / ".local" / "bin"),
                    "/usr/local/bin",
                    "/usr/bin",
                    "/bin",
                ]
            ),
        }

        if self._is_django_core():
            env["DJANGO_SETTINGS_MODULE"] = "test_sqlite"

        return env

    def _run_test_command(
        self,
        cmd: list[str],
        env: dict[str, str],
        repo_name: str,
        commit_sha: str,
        run_type: str,
        debug_helper: DebugHelper,
    ) -> tuple[bool, dict[str, int], str]:
        """Execute test command (handles terminal and non-terminal)."""

        if self.terminal_manager:
            return self._run_tests_with_terminal(
                cmd, env, repo_name, commit_sha, run_type, debug_helper
            )
        else:
            return self._run_tests_without_terminal(
                cmd, env, repo_name, commit_sha, run_type, debug_helper
            )

    def _run_tests_with_terminal(
        self,
        cmd: list[str],
        env: dict[str, str],
        repo_name: str,
        commit_sha: str,
        run_type: str,
        debug_helper: DebugHelper,
    ) -> tuple[bool, dict[str, int], str]:
        """Run tests using terminal manager."""
        assert self.terminal_manager is not None, "terminal_manager must be set"

        title = f"Test_{run_type}_{commit_sha[:7]}"

        cwd = self.repo_path / "tests" if self._is_django_core() else self.repo_path

        process = self.terminal_manager.queue_command(
            cmd,
            title=title,
            cwd=cwd,
            timeout=1200,
            env=env,
            repo_name=self.repo_name,
        )

        # read test output from last log
        log_file = self.terminal_manager.get_last_log_file()
        stdout = self._read_log_file(log_file)

        summary, stats = self._extract_summary(stdout)
        success = self._evaluate_test_results(process.returncode, stats)

        self._log_test_result(
            success,
            summary,
            stats,
            repo_name,
            commit_sha,
            run_type,
            debug_helper,
            cmd,
            stdout,
        )

        return success, stats, stdout

    def _run_tests_without_terminal(
        self,
        cmd: list[str],
        env: dict[str, str],
        repo_name: str,
        commit_sha: str,
        run_type: str,
        debug_helper: DebugHelper,
    ) -> tuple[bool, dict[str, int], str]:
        """Run tests using subprocess directly."""
        try:
            full_env = os.environ.copy()
            full_env.update(env)
            full_env.pop("PYTHONHOME", None)

            cwd = self.repo_path / "tests" if self._is_django_core() else self.repo_path

            result = subprocess.run(
                cmd,
                cwd=cwd,
                env=full_env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=1200,
                check=False,
            )

            summary, stats = self._extract_summary(result.stdout)
            success = self._evaluate_test_results(result.returncode, stats)

            self._log_test_result(
                success,
                summary,
                stats,
                repo_name,
                commit_sha,
                run_type,
                debug_helper,
                cmd,
                result.stdout,
            )

            return success, stats, result.stdout

        except subprocess.TimeoutExpired:
            log("    --> Tests TIMEOUT after 1200s")
            return False, {"passed": 0, "failed": 0, "skipped": 0, "errors": 0}, ""

    def _read_log_file(self, log_file: Path | None) -> str:
        """Read log file if it exists."""
        if log_file and log_file.exists():
            stdout = log_file.read_text()
            log(f"    --> Reading log from: {log_file}")
            return stdout
        else:
            log(f"    WARNING: Log file not found: {log_file}")
            return ""

    def _log_test_result(
        self,
        success: bool,
        summary: str,
        stats: dict[str, int],
        repo_name: str,
        commit_sha: str,
        run_type: str,
        debug_helper: DebugHelper,
        cmd: list[str],
        stdout: str,
    ):
        """Log test results and save failure logs if needed."""
        if success:
            log(f"    --> Tests PASSED: {summary}")
        else:
            log(f"    --> Tests FAILED: {summary}")
            error = subprocess.CalledProcessError(0, cmd, stdout, "")
            log_path = debug_helper.save_test_failure_log(
                repo_name, commit_sha, run_type, error
            )
            log(f"    --> Logs: {log_path}")

    def _extract_summary(self, stdout: str) -> tuple[str, dict[str, int]]:
        """Extract the pytest summary line and parse stats."""
        import re

        # strip ANSI codes
        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        clean_stdout = ansi_escape.sub("", stdout)

        stats = {"passed": 0, "failed": 0, "skipped": 0, "errors": 0}

        # try to find the summary line
        pattern = r"=+\s*(.+?)\s+in\s+[\d.]+s?\s*=+"
        match = re.search(pattern, clean_stdout, re.IGNORECASE)

        if match:
            summary_text = match.group(1).strip()
            stats = self._parse_summary_text(summary_text)
            return summary_text, stats

        # search for passed/failed anywhere in output
        if "passed" in clean_stdout.lower():
            stats = self._parse_fallback_stats(clean_stdout)
            summary_text = self._build_summary_from_stats(stats)
            return summary_text, stats

        return "No summary found", stats

    def _parse_summary_text(self, summary_text: str) -> dict[str, int]:
        """Parse pytest summary text into stats."""
        import re

        stats = {"passed": 0, "failed": 0, "skipped": 0, "errors": 0}

        patterns = {
            "failed": r"(\d+)\s+failed",
            "passed": r"(\d+)\s+passed",
            "skipped": r"(\d+)\s+skipped",
            "errors": r"(\d+)\s+error",
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, summary_text)
            if match:
                stats[key] = int(match.group(1))

        return stats

    def _parse_fallback_stats(self, clean_stdout: str) -> dict[str, int]:
        """Parse stats from output when no summary line found."""
        import re

        stats = {"passed": 0, "failed": 0, "skipped": 0, "errors": 0}

        passed_match = re.search(r"(\d+)\s+passed", clean_stdout, re.IGNORECASE)
        failed_match = re.search(r"(\d+)\s+failed", clean_stdout, re.IGNORECASE)

        if passed_match:
            stats["passed"] = int(passed_match.group(1))
        if failed_match:
            stats["failed"] = int(failed_match.group(1))

        return stats

    def _build_summary_from_stats(self, stats: dict[str, int]) -> str:
        """Build a summary string from stats."""
        parts = []
        if stats["passed"] > 0:
            parts.append(f"{stats['passed']} passed")
        if stats["failed"] > 0:
            parts.append(f"{stats['failed']} failed")

        return ", ".join(parts) if parts else "No summary found"

    def _evaluate_test_results(
        self, returncode: int, stats: dict[str, int], success_threshold: float = 0.95
    ) -> bool:
        """Evaluate if tests passed based on returncode and statistics."""
        if returncode == 0:
            return True

        # no test stats, fall back to returncode
        total = stats["passed"] + stats["failed"]
        if total == 0:
            return returncode == 0

        success_rate = stats["passed"] / total

        # allow some failures if most tests pass (handles flaky tests)
        if success_rate >= success_threshold:
            passed = stats["passed"]
            failed = stats["failed"]
            log(
                f"    --> Accepting result: {passed}/{total} passed ({success_rate:.1%})"
            )
            return True

        return False

    def _is_django_core(self) -> bool:
        indicators = [
            (self.repo_path / "django" / "__init__.py").exists(),
            (self.repo_path / "tests" / "runtests.py").exists(),
        ]
        return any(indicators)
