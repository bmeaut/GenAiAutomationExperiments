import shutil
import tempfile
import subprocess
from pathlib import Path
from typing import Any

from . import cleanup_manager
from .logger import log
from .patch_validator import PatchValidator
from .patch_applicator import PatchApplicator
from .git_operations import GitOperations
from .virtual_environment import VirtualEnvironment
from .debug_helper import DebugHelper
from .terminal_manager import TerminalManager


class ProjectHandler:
    """Coordinates git, venv, and patch operations for a single repo analysis."""

    def __init__(self, repo_name: str, terminal_manager: TerminalManager | None = None):
        self.repo_name = repo_name

        # "pallets/flask" -> /tmp/tmpxxx/flask/
        self.temp_parent = Path(tempfile.mkdtemp())
        repo_dir_name = repo_name.split("/")[-1]
        self.repo_path = self.temp_parent / repo_dir_name

        self.terminal_manager = terminal_manager

        self.git_ops = GitOperations(repo_name, self.repo_path, self.terminal_manager)
        self.venv = VirtualEnvironment(
            self.repo_path, self.terminal_manager, repo_name=repo_name
        )
        self.debug_helper = DebugHelper(self.repo_path)

        self.patch_validator = PatchValidator(self.repo_path, None)
        self.patch_applicator = PatchApplicator(None)

        cleanup_manager.register_temp_dir(self.temp_parent)

    def setup(self):
        """Clone repo and setup git operations."""
        self.git_ops.clone_repository()

        self.venv = VirtualEnvironment(
            self.repo_path, self.terminal_manager, repo_name=self.repo_name
        )

        self.patch_validator.repo = self.git_ops.repo
        self.patch_applicator.repo = self.git_ops.repo

    def setup_virtual_environment(self) -> bool:
        """Create venv and install dependencies."""
        return self.venv.setup()

    def checkout(self, commit_sha: str):
        self.git_ops.checkout(commit_sha)

    def reset_to_commit(self, commit_sha: str):
        self.git_ops.reset_to_commit(commit_sha)

    def get_file_at_commit(self, commit_sha: str, filepath: str) -> str | None:
        """Get file from specific commit."""
        try:
            result = subprocess.run(
                ["git", "show", f"{commit_sha}:{filepath}"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode == 0:
                return result.stdout
            else:
                return None

        except Exception as e:
            log(f"ERROR: Failed to get {filepath} at {commit_sha}: {e}")
            return None

    def get_full_file_content(self, commit_sha: str, file_path: str) -> str:
        """Read file content at specific commit."""
        return self.git_ops.get_full_file_content(commit_sha, file_path)

    def get_human_patch(
        self, commit_sha: str, file_paths: list[str] | None = None
    ) -> str:
        """Generate unified diff for commit."""
        return self.git_ops.get_human_patch(commit_sha, file_paths)

    def validate_and_debug_patch_detailed(self, patch_file_path: str) -> dict[str, Any]:
        """Validate patch with failure analysis."""
        return self.patch_validator.validate_patch(Path(patch_file_path))

    def apply_patch(self, patch_file_path: str) -> bool:
        """Apply patch with multiple fallback strategies."""
        return self.patch_applicator.apply_patch(Path(patch_file_path))

    def cleanup(self):
        """Delete temp directory."""
        log(f"  Cleaning up: {self.temp_parent}")
        shutil.rmtree(self.temp_parent, ignore_errors=True)
        cleanup_manager.unregister_temp_dir(self.temp_parent)
