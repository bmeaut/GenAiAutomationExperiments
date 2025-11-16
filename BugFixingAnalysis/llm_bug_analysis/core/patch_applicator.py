from pathlib import Path
from typing import Any
import ast
import git

from .logger import log
from .patch_generator import CodeLocator


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

    def apply_with_intent_fallback(
        self, patch_path: Path, intent: dict[str, Any]
    ) -> bool:
        """Try git apply first, then fall back to direct AST replacement."""
        if self.apply_patch(patch_path):
            return True

        log("  --> Trying direct AST-based replacement...")
        return self._apply_direct_replacement(intent)

    def _apply_direct_replacement(self, intent: dict[str, Any]) -> bool:
        """Directly modify file using AST."""
        if not self.repo:
            log("  --> Direct replacement failed: No repo")
            return False

        fix_type = intent.get("fix_type", "add_method")
        if fix_type != "replace_method":
            log(f"  --> Only supports replace_method, got: {fix_type}")
            return False

        target_file = intent.get("target_file")
        target_method = intent.get("target_method")
        target_class = intent.get("target_class")
        new_code = intent.get("new_code", [])
        indent_level = intent.get("indentation_level", 4)

        if not target_file or not target_method or not new_code:
            log("  --> Direct replacement failed: Missing required fields")
            return False

        file_path = Path(self.repo.working_dir) / target_file
        if not file_path.exists():
            log(f"  --> Direct replacement failed: File not found: {file_path}")
            return False

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            try:
                locator = CodeLocator(lines)
            except ValueError as e:
                log(f"  --> Direct replacement failed: Cannot parse source: {e}")
                return False

            method_start = locator.find_method_start(target_method, target_class)
            method_end = locator.find_method_end(target_method, target_class)

            if method_start is None or method_end is None:
                log(f"  --> Direct replacement failed:'{target_method}' not found")
                return False

            log(f"  --> Found method at lines {method_start + 1}-{method_end}")

            indent = " " * indent_level
            indented_new_code = []
            for line in new_code:
                if line.strip():
                    indented_new_code.append(indent + line.rstrip() + "\n")
                else:
                    indented_new_code.append("\n")

            new_lines = lines[:method_start] + indented_new_code + lines[method_end:]

            new_source = "".join(new_lines)
            try:
                ast.parse(new_source)
            except SyntaxError as e:
                log(f"  --> Direct replacement failed: new code has syntax error: {e}")
                return False

            with open(file_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)

            log(f"  --> Direct AST replacement successful!")
            return True

        except Exception as e:
            log(f"  --> Direct replacement failed with error: {e}")
            return False
