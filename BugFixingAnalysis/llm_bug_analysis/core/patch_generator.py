import ast
from pathlib import Path
from typing import Any
from abc import ABC, abstractmethod

from core.logger import log


class CodeLocator:
    """Finds methods and classes in Python source using AST."""

    def __init__(self, source_lines: list[str]):
        self.lines = source_lines
        self.source = "".join(source_lines)

        try:
            self.tree = ast.parse(self.source)
        except SyntaxError as e:
            raise ValueError(f"Invalid Python syntax: {e}")

    def find_method_start(
        self, method_name: str, class_name: str | None = None
    ) -> int | None:
        """Find line where method starts (0-indexed)."""
        for node in ast.walk(self.tree):
            if isinstance(node, ast.FunctionDef) and node.name == method_name:
                if class_name:
                    parent = self._find_parent_class(node)
                    if parent and parent.name == class_name:
                        return node.lineno - 1  # AST uses 1-indexed, use 0-indexed
                else:
                    return node.lineno - 1
        return None

    def find_method_end(
        self, method_name: str, class_name: str | None = None
    ) -> int | None:
        """Find line after method ends (0-indexed)."""
        for node in ast.walk(self.tree):
            if isinstance(node, ast.FunctionDef) and node.name == method_name:
                if class_name:
                    parent = self._find_parent_class(node)
                    if not parent or parent.name != class_name:
                        continue
                return node.end_lineno
        return None

    def _find_parent_class(self, node: ast.AST) -> ast.ClassDef | None:
        """Find parent class of a node."""
        for potential_parent in ast.walk(self.tree):
            if isinstance(potential_parent, ast.ClassDef):
                for child in ast.walk(potential_parent):
                    if child is node:
                        return potential_parent
        return None

    def find_class_start(self, class_name: str) -> int | None:
        """Find line where a class starts (0 indexed)"""
        for node in ast.walk(self.tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                return node.lineno - 1
        return None

    def find_class_end(self, class_name: str) -> int | None:
        """Find line after a class ends."""
        for node in ast.walk(self.tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                return node.end_lineno
        return None

    def find_insertion_point(
        self, strategy: dict[str, Any], target_class: str | None = None
    ) -> int | None:
        """Find where to insert code based on strategy."""
        strategy_type = strategy.get("type")
        anchor = strategy.get("anchor")

        if strategy_type == "after_method":
            return self.find_method_end(anchor, target_class) if anchor else None

        elif strategy_type == "before_method":
            return self.find_method_start(anchor, target_class) if anchor else None

        elif strategy_type == "end_of_class":
            return self.find_class_end(target_class) if target_class else None

        elif strategy_type == "beginning_of_class":
            if not target_class:
                return None
            start = self.find_class_start(target_class)
            return start + 1 if start is not None else None

        elif strategy_type == "line_number":
            return int(anchor) if anchor else None

        return None


class PatchFormatter:
    """Formats unified diff patches with headers and line prefixes."""

    def __init__(self, file_path: str):
        self.file_path = file_path

    def create_diff_header(
        self, start_line: int, old_count: int, new_count: int
    ) -> str:
        """Generate diff header with line counts."""
        return f"""--- a/{self.file_path}
+++ b/{self.file_path}
@@ -{start_line},{old_count} +{start_line},{new_count} @@
"""

    def format_context_lines(self, lines: list[str]) -> str:
        return "".join(" " + line for line in lines)

    def format_added_lines(self, lines: list[str]) -> str:
        return "".join("+" + line for line in lines)

    def format_removed_lines(self, lines: list[str]) -> str:
        return "".join("-" + line for line in lines)

    def calculate_context_window(
        self, target_line: int, context_size: int = 3
    ) -> tuple[int, int]:
        """Calculate how much context to show before target."""
        before_count = min(context_size, target_line)
        start_line = max(0, target_line - before_count)
        return start_line, before_count

    def build_patch(
        self,
        start_line: int,
        context_before: list[str],
        old_lines: list[str],
        new_lines: list[str],
        context_after: list[str],
    ) -> str:
        """Build a complete unified diff patch."""
        old_count = len(context_before) + len(old_lines) + len(context_after)
        new_count = len(context_before) + len(new_lines) + len(context_after)

        patch = self.create_diff_header(start_line + 1, old_count, new_count)
        patch += self.format_context_lines(context_before)

        if old_lines:
            patch += self.format_removed_lines(old_lines)

        if new_lines:
            patch += self.format_added_lines(new_lines)

        patch += self.format_context_lines(context_after)
        return patch

    def apply_indentation(self, lines: list[str], indent_level) -> list[str]:
        """Indent code lines consistently."""
        indent = " " * indent_level
        indented = []

        for line in lines:
            if line.strip():
                indented.append(indent + line.rstrip() + "\n")
            else:
                indented.append("\n")

        return indented


class PatchStrategy(ABC):
    """Base for different patch strategies (add, replace, modify)."""

    def __init__(
        self,
        intent: dict[str, Any],
        source_lines: list[str],
        file_path: str,
    ):
        self.intent = intent
        self.lines = source_lines
        self.file_path = file_path
        self.locator = CodeLocator(source_lines)
        self.formatter = PatchFormatter(file_path)

    def generate(self) -> str | None:
        """Template method for patch generation."""
        target = self._find_target_line()
        if target is None:
            log(f"ERROR: Couldn't find target location")
            return None

        old = self._get_old_lines(target)
        indent = self._get_indent(target)

        new = self.formatter.apply_indentation(self.intent["new_code"], indent)
        new = self._add_spacing(new)

        before, after = self._get_context(target)

        start = max(0, target - len(before))
        return self.formatter.build_patch(start, before, old, new, after)

    @abstractmethod
    def _find_target_line(self) -> int | None:
        """Find where to make the change."""
        pass

    @abstractmethod
    def _get_old_lines(self, target_line) -> list[str]:
        """Get lines to remove."""
        pass

    def _get_indent(self, target_line) -> int:
        """Figure out indentation for new code."""
        old = self._get_old_lines(target_line)

        # for additions, use intent or default
        if not old:
            return self.intent.get("indentation_level", 4)

        # for replacements/modifications, match original indentation
        original = self._line_indent(target_line)
        return self.intent.get("indentation_level", original)

    def _add_spacing(self, lines: list[str]) -> list[str]:
        """Add blank lines around code."""
        return ["\n"] + lines + ["\n"]

    def _line_indent(self, line_number) -> int:
        """Get indentation of a specific line."""
        if 0 <= line_number < len(self.lines):
            line = self.lines[line_number]
            return len(line) - len(line.lstrip())
        return 0

    def _get_context(self, target_line, context_size=3) -> tuple[list[str], list[str]]:
        """Get context before and after target line."""
        before_count = min(context_size, target_line)
        after_count = min(context_size, len(self.lines) - target_line)

        start = max(0, target_line - before_count)
        before = self.lines[start:target_line]
        after = self.lines[target_line : target_line + after_count]

        return before, after


class AddMethodPatch(PatchStrategy):

    def _find_target_line(self) -> int | None:
        strategy = self.intent.get("insertion_strategy", {})
        target_class = self.intent.get("target_class")
        return self.locator.find_insertion_point(strategy, target_class)

    def _get_old_lines(self, target_line) -> list[str]:
        """No old lines for addition."""
        # target_line to match abstract method
        return []


class ReplaceMethodPatch(PatchStrategy):

    def _find_target_line(self) -> int | None:
        method = self.intent.get("target_method")
        if not method:
            log("ERROR: replace_method requires target_method field")
            return None

        target_class = self.intent.get("target_class")

        start = self.locator.find_method_start(method, target_class)
        if start is None:
            log(f"ERROR: Method '{method}' not found.")
            return None

        self._method_end = self.locator.find_method_end(method, target_class)
        if self._method_end is None:
            log(f"ERROR: Couldn't find end of '{method}'")
            return None

        return start

    def _get_old_lines(self, target_line) -> list[str]:
        """Get the method being replaced."""
        return self.lines[target_line : self._method_end]

    def _add_spacing(self, lines: list[str]) -> list[str]:
        """No extra spacing for replacement."""
        return lines


class ModifyLinesPatch(PatchStrategy):

    def _find_target_line(self) -> int | None:
        start = self.intent.get("start_line")
        end = self.intent.get("end_line")

        if start is None or end is None:
            log("ERROR: modify_lines requires start_line and end_line")
            return None

        start = int(start)
        end = int(end)

        if start < 0 or end > len(self.lines):
            log(f"ERROR: Invalid range [{start}, {end}]")
            return None

        if start >= end:
            log(f"ERROR: start_line must be less than end_line")
            return None

        self._end_line = end
        return start

    def _get_old_lines(self, target_line) -> list[str]:
        """Get lines being modified."""
        return self.lines[target_line : self._end_line]

    def _add_spacing(self, lines: list[str]) -> list[str]:
        """No extra spacing for modifications."""
        return lines


class PatchGenerator:
    """Generates unified diff patches from LLM fix intents."""

    STRATEGY_MAP = {
        "add_method": AddMethodPatch,
        "replace_method": ReplaceMethodPatch,
        "modify_lines": ModifyLinesPatch,
    }

    def __init__(self, repo_path: str | Path):
        self.repo_path = Path(repo_path)

    def generate(self, intent: dict[str, Any]) -> str | None:
        """Generate a patch from LLM's fix intention."""

        error = self._validate_intent(intent)
        if error:
            log(f"ERROR: {error}")
            return None

        source = self._load_source(intent["target_file"])
        if source is None:
            return None

        fix_type = intent.get("fix_type", "add_method")
        strategy_class = self.STRATEGY_MAP[fix_type]

        strategy = strategy_class(intent, source, intent["target_file"])
        return strategy.generate()

    @staticmethod
    def count_patch_stats(patch: str) -> dict[str, int]:
        """Count line changes in patch."""
        added = sum(
            1
            for line in patch.split("\n")
            if line.startswith("+") and not line.startswith("+++")
        )
        deleted = sum(
            1
            for line in patch.split("\n")
            if line.startswith("-") and not line.startswith("---")
        )

        return {
            "lines_added": added,
            "lines_deleted": deleted,
            "total": added + deleted,
        }

    def _load_source(self, file_path: str) -> list[str] | None:
        """Load source file as list of lines."""
        full_path = self.repo_path / file_path
        if not full_path.exists():
            log(f"ERROR: File not found: {full_path}")
            return None

        try:
            # .read_text() only gives string instead of list
            with open(full_path, "r", encoding="utf-8") as f:
                return f.readlines()
        except Exception as e:
            log(f"ERROR: Failed to read {full_path}: {e}")
            return None

    def _validate_intent(self, intent: dict[str, Any]) -> str | None:
        """Check if required fields are there."""
        required = ["target_file", "new_code"]
        for field in required:
            if field not in intent:
                return f"Missing field: {field}"

        fix_type = intent.get("fix_type", "add_method")

        if fix_type not in self.STRATEGY_MAP:
            return f"Unknown fix_type: {fix_type}. Use: {', '.join(self.STRATEGY_MAP.keys())}"

        if fix_type == "replace_method" and "target_method" not in intent:
            return "replace_method needs target_method field"

        if fix_type == "modify_lines":
            missing = [f for f in ["start_line", "end_line"] if f not in intent]
            if missing:
                return f"modify_lines needs: {', '.join(missing)}"

        return None
