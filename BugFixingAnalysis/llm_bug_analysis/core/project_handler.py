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


class ProjectHandler:
    """Coordinates git, venv, and patch operations for a single repo analysis."""

    def __init__(self, repo_name: str):
        self.repo_name = repo_name
        self.repo_path = Path(tempfile.mkdtemp())

        self.git_ops = GitOperations(repo_name, self.repo_path)
        self.venv = VirtualEnvironment(self.repo_path)
        self.debug_helper = DebugHelper(self.repo_path)

        self.patch_validator = PatchValidator(self.repo_path, None)
        self.patch_applicator = PatchApplicator(None)

        cleanup_manager.register_temp_dir(self.repo_path)

    def setup(self):
        """Clone repo and setup git operations."""
        self.git_ops.clone_repository()

        self.patch_validator.repo = self.git_ops.repo
        self.patch_applicator.repo = self.git_ops.repo

    def setup_virtual_environment(self) -> bool:
        """Create venv and install dependencies."""
        return self.venv.setup()

    def run_tests(self, test_command: list[str]) -> subprocess.CompletedProcess:
        """Run tests in the venv."""
        log(f"  Running: '{' '.join(test_command)}' (via: {self.venv.project_type})")
        return self.venv.execute_command(test_command)

    def checkout(self, commit_sha: str):
        self.git_ops.checkout(commit_sha)

    def reset_to_commit(self, commit_sha: str):
        self.git_ops.reset_to_commit(commit_sha)

    def get_changed_files(self, commit_sha: str) -> list[str]:
        """Get .py files changed in commit."""
        return self.git_ops.get_changed_files(commit_sha)

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

    def get_human_patch(self, commit_sha: str) -> str:
        """Generate unified diff for commit."""
        return self.git_ops.get_human_patch(commit_sha)

    def validate_and_debug_patch_detailed(self, patch_file_path: str) -> dict[str, Any]:
        """Validate patch with failure analysis."""
        return self.patch_validator.validate_patch(Path(patch_file_path))

    def apply_patch(self, patch_file_path: str) -> bool:
        """Apply patch with multiple fallback strategies."""
        return self.patch_applicator.apply_patch(Path(patch_file_path))

    def cleanup(self):
        """Delete temp directory."""
        log(f"  Cleaning up: {self.repo_path}")
        shutil.rmtree(self.repo_path, ignore_errors=True)
        cleanup_manager.unregister_temp_dir(self.repo_path)
