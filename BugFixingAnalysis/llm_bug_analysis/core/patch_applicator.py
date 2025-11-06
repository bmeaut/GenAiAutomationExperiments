from pathlib import Path
import git

from .logger import log


class PatchApplicator:
    """Tries multiple strategies to apply git patches."""

    def __init__(self, repo: git.Repo | None):
        self.repo = repo

    def apply_patch(self, patch_path: Path) -> bool:
        if not self.repo:
            raise RuntimeError("Repo not initialized")

        if not patch_path.exists():
            log(f"Patch file missing: {patch_path}")
            return False

        for method in [
            self._try_direct,
            self._try_whitespace_fix,
            self._try_ignore_whitespace,
        ]:
            if method(patch_path):
                return True

        log("  --> All strategies failed")
        return False

    def _try_direct(self, path: Path) -> bool:
        """Direct apply (no fixes)."""
        if not self.repo:  # repetitive but Pylance complains without it
            return False
        try:
            self.repo.git.apply(["--check", str(path)])
            self.repo.git.apply(str(path))
            log("  --> Direct patch applied.")
            return True
        except git.GitCommandError as e:
            log(f"  --> Direct apply failed: {e.stderr}")
            return False

    def _try_whitespace_fix(self, path: Path) -> bool:
        """Auto-fix whitespace issues."""
        if not self.repo:
            return False
        try:
            self.repo.git.apply(["--whitespace=fix", str(path)])
            log("  --> Patch applied with whitespace fixes.")
            return True
        except git.GitCommandError as e:
            log(f"  --> Whitespace fix failed: {e.stderr}")
            return False

    def _try_ignore_whitespace(self, path: Path) -> bool:
        """Ignore all whitespace differences."""
        if not self.repo:
            return False
        try:
            self.repo.git.apply(["--ignore-whitespace", str(path)])
            log("  --> Patch applied ignoring whitespaces.")
            return True
        except git.GitCommandError as e:
            log(f"  --> Ignore whitespace failed: {e.stderr}")
            return False
