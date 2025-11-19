from pathlib import Path
import git
from git import Repo

from .logger import log
from .terminal_manager import TerminalManager


class GitOperations:
    """Handles git CLI operations."""

    def __init__(
        self,
        repo_name: str,
        repo_path: Path,
        terminal_manager: TerminalManager | None = None,
    ):
        self.repo_name = repo_name
        self.repo_url = f"https://github.com/{repo_name}.git"
        self.repo_path = Path(repo_path)
        self.repo: Repo | None = None
        self.terminal_manager = terminal_manager

    def clone_repository(self):
        """Clone the repository with full history."""

        parent_dir = self.repo_path.parent
        parent_dir.mkdir(parents=True, exist_ok=True)

        if self.terminal_manager:
            log(f"  Cloning {self.repo_name}...")
            self.terminal_manager.queue_command(
                ["git", "clone", "--progress", self.repo_url, str(self.repo_path)],
                title=f"Cloning {self.repo_name}",
                cwd=parent_dir,
                timeout=600,
            )

            self.repo = Repo(self.repo_path)

        else:
            log(f"  Cloning {self.repo_url} into {self.repo_path}")
            self.repo = Repo.clone_from(self.repo_url, self.repo_path)

        log("  --> Fetching full history...")
        try:
            self.repo.git.fetch("--unshallow")
            log("  --> Got full history.")
        except git.GitCommandError as e:
            if "--unshallow on a complete repository" in e.stderr:
                log("  --> Already complete.")
            else:
                raise

    def checkout(self, commit_sha: str):
        if not self.repo:
            raise RuntimeError("ERROR: Repository not initialized.")
        self.repo.git.checkout(commit_sha, force=True)

    def reset_to_commit(self, commit_sha: str):
        if not self.repo:
            raise RuntimeError("ERROR: Repository not initialized.")
        self.repo.git.reset("--hard", commit_sha)

    def get_full_file_content(self, commit_sha: str, file_path: str) -> str:
        """Read full file content at a specific commit."""
        if not self.repo:
            raise RuntimeError("ERROR: Repository not initialized.")

        try:
            commit = self.repo.commit(commit_sha)
            blob = commit.tree / file_path
            return blob.data_stream.read().decode("utf-8", errors="replace")
        except Exception as e:
            log(f"  --> ERROR reading file {file_path} at {commit_sha[:7]}: {e}")
            return ""

    def get_human_patch(
        self, commit_sha: str, file_paths: list[str] | None = None
    ) -> str:
        """Generate a unified diff patch for a commit."""
        if not self.repo:
            raise RuntimeError("ERROR: Repository not initialized.")

        try:
            commit = self.repo.commit(commit_sha)

            if not commit.parents:
                log("  --> Commit has no parent, cannot generate patch.")
                return ""

            parent = commit.parents[0]

            if file_paths:
                patch = self.repo.git.diff(
                    parent.hexsha,
                    commit.hexsha,
                    "--unified=3",
                    "--",
                    *file_paths,
                )
            else:
                patch = self.repo.git.diff(
                    parent.hexsha,
                    commit.hexsha,
                    "--unified=3",
                )
            return patch

        except Exception as e:
            log(f"  --> ERROR Failed to generate patch: {e}")
            return ""
