from __future__ import annotations
import os
import subprocess
import time
from pathlib import Path
from typing import Any


class TerminalManager:
    """Opens external terminal windows to show live subprocesses."""

    # rwx permissions for owner, rx for group and others
    SCRIPT_PERMISSIONS = 0o755
    POLL_INTERVAL = 0.5
    DEFAULT_TIMEOUT = 1200

    SEPARATOR = "=" * 70
    DIVIDER = "─" * 70

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        package_root = Path(__file__).parent.parent

        self._setup_directories(package_root)
        self.terminal_cmd = self._get_wsl_terminal()
        self._reset_state()

    def _setup_directories(self, package_root: Path) -> None:
        """Create and configure directory structure."""
        cache_dir = package_root / ".cache" / "terminal_logs"

        self.log_dir = cache_dir / "logs"
        self.script_dir_runtime = cache_dir / "scripts"
        self.flag_dir = cache_dir / "flags"
        self.script_dir_template = Path(__file__).parent / "scripts"

        for directory in [self.log_dir, self.script_dir_runtime, self.flag_dir]:
            directory.mkdir(parents=True, exist_ok=True)

    def _reset_state(self) -> None:
        """Reset terminal manager state."""
        self.persistent_terminal: subprocess.Popen | None = None
        self.command_queue_file: Path | None = None
        self.persistent_mode: bool = False
        self._last_log_file: Path | None = None

    def _get_wsl_terminal(self) -> list[str]:
        """Get terminal command for WSL."""

        try:
            result = subprocess.run(
                ["cmd.exe", "/c", "where", "wt.exe"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                return ["cmd.exe", "/c", "start", "wt.exe", "wsl.exe", "--"]
        except Exception:
            pass

        # fallback to cmd
        return ["cmd.exe", "/c", "start", "cmd.exe", "/k", "wsl.exe", "-e"]

    def __enter__(self) -> TerminalManager:
        """Context manager entry: start persistent terminal."""
        self.start_persistent_terminal()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> bool:
        """Context manager exit: stop persistant terminal."""
        self.stop_persistent_terminal()

        if exc_type is not None:
            error_log = self.log_dir.parent / "terminal_error.log"
            error_log.write_text(f"{exc_type.__name__}: {exc_val}")

        return False  # don't suppress exceptions

    def start_persistent_terminal(self, title: str = "Bug Analysis Pipeline") -> bool:
        """Start one terminal that runs all commands sequentially."""
        self._cleanup_terminal_state()

        self.command_queue_file = self.flag_dir / "command_queue.txt"
        self.command_queue_file.write_text("")

        script_content = self._create_persistent_script(title)
        script_path = self.script_dir_runtime / "persistent_terminal.sh"

        self._write_executable_script(script_path, script_content)

        try:
            self.persistent_terminal = subprocess.Popen(
                self.terminal_cmd + [str(script_path)],
                stdout=subprocess.DEVNULL,  # don't capture, show in terminal
                stderr=subprocess.DEVNULL,
            )
            self.persistent_mode = True
            time.sleep(1)  # give it a moment to start
            return True
        except Exception:
            return False

    def stop_persistent_terminal(self) -> bool:
        """Stop the persistent terminal."""

        if not self.persistent_mode:
            return True

        stop_file = self.flag_dir / "stop.flag"
        stop_file.write_text("STOP")

        if self.persistent_terminal:
            try:
                self.persistent_terminal.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.persistent_terminal.kill()

        self.persistent_mode = False
        return True

    def queue_command(
        self,
        command: list[str],
        title: str,
        cwd: Path | None = None,
        timeout: int = DEFAULT_TIMEOUT,
        log_file: Path | None = None,
        env: dict[str, str] | None = None,
        repo_name: str | None = None,
    ) -> subprocess.CompletedProcess:
        """Queue a command in the persistent terminal."""

        if not self.persistent_mode or self.command_queue_file is None:
            return self.run_and_wait(command, title, cwd, timeout, repo_name)

        full_cmd = self._build_command_string(command, cwd, env)

        actual_log_file = self._resolve_log_file(title, log_file, repo_name)
        self._last_log_file = actual_log_file
        if actual_log_file:
            self._set_current_log_mapping(actual_log_file)

        self._append_to_queue(full_cmd)

        # wait for completion
        done_file = self.flag_dir / "cmd_done.flag"
        exit_code = self._wait_for_done_file(done_file, command, timeout)

        return subprocess.CompletedProcess(command, exit_code, "", "")

    def run_and_wait(
        self,
        command: list[str],
        title: str,
        cwd: Path | None = None,
        timeout: int = DEFAULT_TIMEOUT,
        repo_name: str | None = None,
    ) -> subprocess.CompletedProcess:
        """Run command in terminal and wait for completion."""

        log_file = self._resolve_log_file(title, None, repo_name)
        self._last_log_file = log_file
        done_file = self.flag_dir / f"done_{os.getpid()}.flag"

        process = self.run_with_terminal(command, title, cwd, log_file, done_file)
        exit_code = self._wait_for_done_file(done_file, command, timeout)

        return subprocess.CompletedProcess(command, exit_code, "", "")

    def run_with_terminal(
        self,
        command: list[str],
        title: str,
        cwd: Path | None = None,
        log_file: Path | None = None,
        done_file: Path | None = None,
    ) -> subprocess.Popen:
        """Run command in a new terminal window."""

        script_content = self._create_wrapper_script(
            command, title, log_file, cwd, done_file
        )
        script_path = self.script_dir_runtime / f"wrapper_{os.getpid()}.sh"

        self._write_executable_script(script_path, script_content)

        return subprocess.Popen(
            self.terminal_cmd + [str(script_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def get_last_log_file(self) -> Path | None:
        """Get the path to the last log file that was written."""
        return self._last_log_file

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """Clean a string for use as filename."""
        return name.replace("/", "_").replace(" ", "_")

    def _resolve_log_file(
        self,
        title: str,
        log_file: Path | None,
        repo_name: str | None,
    ) -> Path | None:
        """Determine the log file path to use."""
        if log_file:
            return log_file

        if repo_name:
            return self._get_repo_log_path(title, repo_name)

        return None

    def _get_repo_log_path(self, title: str, repo_name: str) -> Path:
        """Generate log file path with repo organization."""
        safe_title = self._sanitize_filename(title)
        safe_repo = self._sanitize_filename(repo_name)

        # create repo-specific subdirectory
        repo_log_dir = self.log_dir / safe_repo
        repo_log_dir.mkdir(parents=True, exist_ok=True)

        return repo_log_dir / f"{safe_title}.log"

    def _set_current_log_mapping(self, log_file: Path):
        """Write log file path to mapping file for bash script."""
        log_map_file = self.flag_dir / "current_log.txt"
        log_map_file.write_text(str(log_file))

    def _append_to_queue(self, command: str):
        """Append command to the queue file."""
        if self.command_queue_file is None:
            raise RuntimeError("Command queue not initialized")

        with open(self.command_queue_file, "a") as f:
            f.write(f"{command}\n")

    def _cleanup_terminal_state(self):
        """Remove old flag files from previous runs."""
        flag_files = [
            self.flag_dir / "cmd_done.flag",
            self.flag_dir / "stop.flag",
            self.flag_dir / "current_log.txt",
            self.flag_dir / "command_queue.txt",
        ]

        for flag_file in flag_files:
            if flag_file.exists():
                flag_file.unlink()

    def _create_persistent_script(self, title: str) -> str:
        """Create the master terminal script."""

        template_path = self.script_dir_template / "persistent_terminal.sh"
        template = template_path.read_text()

        return template.format(
            title=title,
            separator=self.SEPARATOR,
            divider=self.DIVIDER,
            queue_file=self.command_queue_file,
            done_file=self.flag_dir / "cmd_done.flag",
            stop_file=self.flag_dir / "stop.flag",
            log_map_file=self.flag_dir / "current_log.txt",
        )

    def _create_wrapper_script(
        self,
        command: list[str],
        title: str,
        log_file: Path | None,
        cwd: Path | None = None,
        done_file: Path | None = None,
    ) -> str:
        """Create bash script for environment."""

        template = (self.script_dir_template / "wrapper.sh").read_text()

        cmd_str = " ".join(f'"{arg}"' for arg in command)

        if done_file is None:
            done_file = self.log_dir / f"done_{os.getpid()}.flag"

        return template.format(
            cwd=cwd or "",
            title=title,
            separator=self.SEPARATOR,
            command=cmd_str,
            log_file=log_file or "",
            done_file=done_file,
            has_cwd="true" if cwd else "false",
            has_log="true" if log_file else "false",
        )

    def _write_executable_script(self, path: Path, content: str) -> None:
        """Write a script file and make it executable."""
        path.write_text(content)
        path.chmod(self.SCRIPT_PERMISSIONS)

    def _build_command_string(
        self,
        command: list[str],
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> str:
        """Build a bash command string with environment and cwd setup."""
        cmd_parts = []

        if env:
            for key, value in env.items():
                cmd_parts.append(f'export {key}="{value}"')

        if cwd:
            cmd_parts.append(f'cd "{cwd}"')

        cmd_str = " ".join(f'"{arg}"' if " " in arg else arg for arg in command)
        cmd_parts.append(cmd_str)

        return " && ".join(cmd_parts)

    def _wait_for_done_file(
        self,
        done_file: Path,
        command: list[str],
        timeout: int,
    ) -> int:
        """Wait for done file to appear and read exit code."""
        # clean up old done file
        if done_file.exists():
            done_file.unlink()

        # wait for new done file
        start_time = time.time()
        while not done_file.exists():
            if time.time() - start_time > timeout:
                raise subprocess.TimeoutExpired(command, timeout)
            time.sleep(self.POLL_INTERVAL)

        # read exit code
        try:
            exit_code = int(done_file.read_text().strip())
            done_file.unlink()
            return exit_code
        except (ValueError, FileNotFoundError):
            if done_file.exists():
                done_file.unlink()
            return 0  # assume success if can't read
