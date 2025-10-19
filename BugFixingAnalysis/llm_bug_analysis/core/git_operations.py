from pathlib import Path
import git
from git import Repo

from core.logger import log


class GitOperations:
    """Handles git CLI operations."""

    def __init__(self, repo_name: str, repo_path: Path):
        self.repo_name = repo_name
        self.repo_url = f"https://github.com/{repo_name}.git"
        self.repo_path = Path(repo_path)
        self.repo: Repo | None = None

    def clone_repository(self):
        """Clone the repository with full history."""
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

    def get_changed_files(self, commit_sha: str) -> list[str]:
        """Get .py files changed in a commit."""
        if not self.repo:
            raise RuntimeError("ERROR: Repository not initialized.")

        try:
            commit = self.repo.commit(commit_sha)

            if not commit.parents:
                log("  --> Commit has no parent, skipping.")
                return []

            parent = commit.parents[0]
            diffs = parent.diff(commit)

            py_files = []
            for d in diffs:
                # path from a_path or b_path handles renames/deletions
                path = d.b_path or d.a_path
                if path and path.endswith(".py"):
                    py_files.append(path)

            return py_files

        except Exception as e:
            log(f"  --> ERROR getting changed files: {e}")
            return []

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

    def get_human_patch(self, commit_sha: str) -> str:
        """Generate a unified diff patch for a commit."""
        if not self.repo:
            raise RuntimeError("ERROR: Repository not initialized.")

        try:
            commit = self.repo.commit(commit_sha)

            if not commit.parents:
                log("  --> Commit has no parent, cannot generate patch.")
                return ""

            parent = commit.parents[0]
            patch = self.repo.git.diff(
                parent.hexsha,
                commit.hexsha,
                unified=3,
            )
            return patch

        except Exception as e:
            log(f"  --> ERROR Failed to generate patch: {e}")
            return ""
