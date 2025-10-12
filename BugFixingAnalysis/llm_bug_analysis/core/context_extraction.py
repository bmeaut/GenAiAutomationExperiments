import ast
import re
from typing import Dict, Any, Set, List, Tuple
from git import Repo, Commit as GitCommit
from abc import ABC, abstractmethod
from collections import Counter

# ==============================================================================
#  STANDALONE HELPER FUNCTIONS
# ==============================================================================


def _find_enclosing_class(tree: ast.AST, changed_ranges: List[Tuple[int, int]]) -> Any:
    """
    If a change is outside any function, find the class that contains it.
    """
    if not changed_ranges:
        return None
    # use the start of the first change as the anchor point
    anchor_line = changed_ranges[0][0]

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            start_line = node.lineno
            # use getattr for safety in case end_lineno is missing
            end_line = getattr(node, "end_lineno", start_line)
            if start_line <= anchor_line <= end_line:
                return node  # return the actual ast.ClassDef node
    return None


def _parse_diff_ranges(patch_content) -> List[Tuple[int, int]]:
    """
    Parse diff to extract all changed line ranges from the original file.
    Returns list of (start_line, end_line) tuples.
    """
    if patch_content is None:
        return []

    # properly decode bytes to string
    if isinstance(patch_content, bytes):
        patch_text = patch_content.decode("utf-8")
    else:
        patch_text = str(patch_content)

    changed_ranges = []
    current_original_line = 0
    range_start = None
    range_end = None

    for line in patch_text.splitlines():
        # parse hunk headers like @@ -10,5 +10,7 @@
        if line.startswith("@@"):
            # save previous range if exists
            if range_start is not None:
                changed_ranges.append((range_start, range_end))
                range_start = None
                range_end = None

            match = re.match(r"@@\s*-(\d+)(?:,(\d+))?\s*\+(\d+)(?:,(\d+))?\s*@@", line)
            if match:
                current_original_line = int(match.group(1))
        elif line.startswith("-"):
            # line was deleted or modified
            if range_start is None:
                range_start = current_original_line
            range_end = current_original_line
            current_original_line += 1
        elif line.startswith("+"):
            # line was added (don't increment original line counter)
            # if we have a range going, this might be a modification
            if range_start is not None:
                range_end = (
                    current_original_line - 1
                    if current_original_line > range_start
                    else range_start
                )
        elif line.startswith(" "):
            # context line (unchanged)
            # close current range if exists
            if range_start is not None:
                changed_ranges.append((range_start, range_end))
                range_start = None
                range_end = None
            current_original_line += 1
        # lines not starting with -, +, or space are headers/metadata, ignore

    # save final range if exists
    if range_start is not None:
        changed_ranges.append((range_start, range_end))

    # merge overlapping ranges
    if changed_ranges:
        changed_ranges.sort()
        merged = [changed_ranges[0]]
        for start, end in changed_ranges[1:]:
            if start <= merged[-1][1] + 1:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))
        return merged

    return []


def _find_containing_functions_and_classes(
    tree: ast.AST, changed_ranges: List[Tuple[int, int]]
) -> List[Tuple[str, int, int, str, ast.AST]]:
    """
    Find all functions and classes that contain any of the changed lines.
    Returns list of (name, start_line, end_line, type).
    """
    if not changed_ranges:
        return []

    # use the start of the first change as the anchor
    anchor_line = changed_ranges[0][0]
    containing_items = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start_line = node.lineno
            end_line = getattr(node, "end_lineno", start_line)
            if start_line <= anchor_line <= end_line:
                containing_items.append(
                    (node.name, start_line, end_line, "Function", node)
                )
        elif isinstance(node, ast.ClassDef):
            start_line = node.lineno
            end_line = getattr(node, "end_lineno", start_line)
            if start_line <= anchor_line <= end_line:
                containing_items.append(
                    (node.name, start_line, end_line, "Class", node)
                )

    return containing_items


# ==============================================================================
#  (Abstract Base Class)
# ==============================================================================


class BaseContextGatherer(ABC):
    """
    Abstract base class for a context gathering strategy.
    This acts as a "blueprint" to ensure all context strategies have the same structure.
    """

    def __init__(self, repo: Repo, log_callback):
        self.repo = repo
        self.log = log_callback

    @abstractmethod
    def gather(self, bug_data: dict, **kwargs) -> dict:
        """
        Gathers a specific type of context for a given bug.
        It must be implemented by any class that inherits from this one.
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """
        The user-friendly name of this strategy for logging purposes.
        """
        pass


# ==============================================================================
#  BASIC CONTEXT
# ==============================================================================


class BuggyCodeContextGatherer(BaseContextGatherer):
    """
    This class will hold all the original logic for finding the buggy code.
    It fulfills the "contract" set by the BaseContextGatherer blueprint.
    """

    @property
    def name(self) -> str:
        return "Bug Knowledge (Local Code Snippets)"

    def gather(self, bug_data: dict, **kwargs) -> dict:
        """
        This is the main entry point for gathering context.
        """
        self.log("--- DEBUG: Starting BuggyCodeContextGatherer.gather ---")
        commit_sha = bug_data["bug_commit_sha"]
        max_tokens = kwargs.get("max_tokens_per_file", 4000)

        commit: GitCommit = self.repo.commit(commit_sha)
        if not commit.parents:
            self.log("  Warning: Initial commit, cannot extract context.")
            return {}

        parent: GitCommit = commit.parents[0]
        diffs = parent.diff(commit, create_patch=True)
        context_snippets = {}

        self.log(f"--- DEBUG: Found {len(diffs)} diffs to process ---")

        for i, diff in enumerate(diffs):
            self.log(f"\n--- DEBUG: Processing diff #{i+1} for file: {diff.a_path} ---")
            if not diff.a_path or not str(diff.a_path).endswith(".py"):
                self.log("--- DEBUG: Skipping non-python file. ---")
                continue
            try:
                buggy_code = (
                    (parent.tree / diff.a_path).data_stream.read().decode("utf-8")
                )
                buggy_code_lines = buggy_code.splitlines()

                self.log(f"--- DEBUG: Raw diff content for {diff.a_path}:")
                self.log(str(diff.diff))
                self.log("--- END RAW DIFF ---")

                changed_ranges = _parse_diff_ranges(diff.diff)
                self.log(
                    f"--- DEBUG: Result from _parse_diff_ranges: {changed_ranges} ---"
                )

                # for pure additions, extract insertion point context instead
                if not changed_ranges:
                    self.log(
                        f"    Info: Pure addition detected in {diff.a_path}. Extracting insertion context."
                    )
                    insertion_line = self._extract_insertion_line_from_diff(diff.diff)
                    if insertion_line:
                        file_context = self._extract_insertion_point_context(
                            buggy_code_lines, insertion_line, diff.a_path
                        )
                        if file_context:
                            context_snippets.update(file_context)
                    continue

                file_context = self._extract_file_context(
                    buggy_code_lines, changed_ranges, diff.a_path
                )

                self.log(
                    f"--- DEBUG: Result from _extract_file_context: {'Found context' if file_context else 'No context found'} ---"
                )

                if file_context:
                    context_snippets.update(file_context)
            except Exception as e:
                self.log(
                    f"    Warning: Could not extract context for {diff.a_path}. Reason: {e}"
                )

        self.log(
            f"--- DEBUG: Finished BuggyCodeContextGatherer.gather. Total snippets found: {len(context_snippets)} ---"
        )
        return context_snippets

    def _extract_insertion_line_from_diff(self, patch_content) -> int | None:
        """
        For pure additions, extract the line number where code was inserted.
        """
        if isinstance(patch_content, bytes):
            patch_text = patch_content.decode("utf-8")
        else:
            patch_text = str(patch_content)

        for line in patch_text.splitlines():
            if line.startswith("@@"):
                match = re.match(r"@@\s*-(\d+)", line)
                if match:
                    return int(match.group(1))
        return None

    def _extract_insertion_point_context(
        self,
        code_lines: List[str],
        insertion_line: int,
        file_path: str,
    ) -> Dict[str, str]:
        """
        For pure additions, extract minimal context:
        1. Class header (if in a class)
        2. Method before insertion
        3. Method after insertion
        """
        try:
            full_code = "\n".join(code_lines)
            tree = ast.parse(full_code)
        except SyntaxError:
            self.log(f"    Warning: Could not parse AST for {file_path}.")
            return {}

        snippets = {}

        # find the class containing the insertion point
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                start_line = node.lineno
                end_line = getattr(node, "end_lineno", start_line)
                if start_line <= insertion_line <= end_line:
                    self.log(f"    --> Found class '{node.name}' at insertion point")

                    # 1. extract class header (definition + docstring, ~20 lines max)
                    header_end = min(start_line + 20, len(code_lines))
                    class_header = "\n".join(code_lines[start_line - 1 : header_end])
                    if len(class_header.split("\n")) > 5:  # only if meaningful
                        snippets[
                            f"FILE: {file_path}\nClass '{node.name}' header (lines {start_line}-{header_end})"
                        ] = class_header
                        self.log(f"    --> Extracted class header")

                    # 2. find methods before and after insertion
                    methods = []
                    for child in node.body:
                        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            methods.append(
                                (
                                    child.name,
                                    child.lineno,
                                    getattr(child, "end_lineno", child.lineno),
                                    child,
                                )
                            )

                    methods.sort(key=lambda x: x[1])

                    # extract method immediately before and after
                    method_before = None
                    method_after = None

                    for i, (name, start, end, method_node) in enumerate(methods):
                        if end < insertion_line:
                            # this method ends before insertion - it's a candidate
                            # keep updating to get the LAST (closest) one
                            method_before = (name, start, end, method_node)
                        elif start > insertion_line and method_after is None:
                            # this is the first method after insertion
                            method_after = (name, start, end, method_node)

                    # extract the method before insertion
                    if method_before:
                        name, start, end, method_node = method_before
                        snippet = ast.get_source_segment(full_code, method_node)
                        if snippet:
                            snippets[
                                f"FILE: {file_path}\nMethod '{name}' (before insertion, lines {start}-{end})"
                            ] = snippet
                            self.log(
                                f"    --> Extracted method '{name}' (before insertion)"
                            )
                        else:
                            self.log(
                                f"    WARNING: Could not extract snippet for '{name}' (before insertion)"
                            )

                    # extract the method after insertion
                    if method_after:
                        name, start, end, method_node = method_after
                        snippet = ast.get_source_segment(full_code, method_node)
                        if snippet:
                            snippets[
                                f"FILE: {file_path}\nMethod '{name}' (after insertion, lines {start}-{end})"
                            ] = snippet
                            self.log(
                                f"    --> Extracted method '{name}' (after insertion)"
                            )
                        else:
                            self.log(
                                f"    WARNING: Could not extract snippet for '{name}' (after insertion)"
                            )

                    if not method_before and not method_after:
                        self.log(
                            f"    WARNING: Could not find methods before/after insertion at line {insertion_line}"
                        )

                    break  # found the class, done

        return snippets

    def _extract_code_context(self, commit_sha: str, max_tokens_per_file=1000):
        """
        Extracts precise context with token limits.
        """
        commit: GitCommit = self.repo.commit(commit_sha)
        if not commit.parents:
            self.log("  Warning: Initial commit, cannot extract context.")
            return {}

        parent: GitCommit = commit.parents[0]
        diffs = parent.diff(commit, create_patch=True)
        context_snippets = {}

        for diff in diffs:
            if not diff.a_path or not str(diff.a_path).endswith(".py"):
                continue

            try:
                buggy_code = (
                    (parent.tree / diff.a_path).data_stream.read().decode("utf-8")
                )
                buggy_code_lines = buggy_code.splitlines()

                print("=" * 50)
                print(f"DEBUG: Analyzing file: {diff.a_path}")
                print(f"DEBUG: Raw diff content:\n{diff.diff}")

                # parse the diff to get all changed line ranges
                changed_ranges = _parse_diff_ranges(diff.diff)
                if not changed_ranges:
                    self.log(
                        f"    Warning: No valid change ranges found for {diff.a_path}"
                    )
                    continue

                # extract relevant code sections with size limits
                file_context = self._extract_file_context(
                    buggy_code_lines, changed_ranges, diff.a_path
                )

                if file_context:
                    context_snippets.update(file_context)

            except Exception as e:
                self.log(
                    f"    Warning: Could not extract context for {diff.a_path}. Reason: {e}"
                )

        return context_snippets

    def _extract_file_context(
        self,
        buggy_code_lines: List[str],
        changed_ranges: List[Tuple[int, int]],
        file_path: str,
    ) -> Dict[str, str]:
        """
        Extract context around changed ranges.
        Strategy:
        1. For ADDITIONS: Show insertion point context (before/after methods)
        2. For MODIFICATIONS: Show the exact function/method being modified
        3. For DELETIONS: Show the function where code was removed
        """
        self.log("--- DEBUG: Inside _extract_file_context ---")
        try:
            full_code = "\n".join(buggy_code_lines)
            tree = ast.parse(full_code)
        except SyntaxError:
            self.log(f"    Warning: Could not parse AST for {file_path}.")
            return self._extract_simple_context(
                buggy_code_lines, changed_ranges, file_path, 1000
            )

        context_snippets = {}

        # find what contains the change
        containing_nodes = _find_containing_functions_and_classes(tree, changed_ranges)

        if not containing_nodes:
            self.log("    Warning: No containing function/class found.")
            return self._extract_simple_context(
                buggy_code_lines, changed_ranges, file_path, 1000
            )

        # sort by size (smallest first = most specific)
        containing_nodes.sort(key=lambda x: x[2] - x[1])

        # extract the smallest containing node (most specific context)
        name, start_line, end_line, node_type, node_obj = containing_nodes[0]

        # check if it's too large
        node_size = end_line - start_line
        if node_size > 100:
            self.log(
                f"    Warning: {node_type} '{name}' is large ({node_size} lines). Using minimal context."
            )
            return self._extract_minimal_context(
                buggy_code_lines, changed_ranges, file_path, 1000
            )

        # extract the containing function/method
        snippet = ast.get_source_segment(full_code, node_obj)
        if snippet:
            context_key = f"FILE: {file_path}\n{node_type} '{name}' (lines {start_line}-{end_line})"
            context_snippets[context_key] = snippet
            self.log(f"    --> Extracted {node_type} '{name}' (changed code is here)")

            # if it's a method in a class, also show the class header for context
            if node_type == "Function":
                # find parent class
                for parent_node in containing_nodes:
                    if parent_node[3] == "Class":
                        class_name = parent_node[0]
                        class_start = parent_node[1]
                        # extract just the class definition + docstring (first ~10 lines)
                        class_header_lines = buggy_code_lines[
                            class_start - 1 : class_start + 9
                        ]
                        class_header = "\n".join(class_header_lines)
                        context_snippets[
                            f"FILE: {file_path}\nClass '{class_name}' context (lines {class_start}-{class_start + 9})"
                        ] = class_header
                        self.log(
                            f"    --> Added class header context for '{class_name}'"
                        )
                        break
        else:
            self.log(
                f"    Warning: Could not extract snippet for {node_type} '{name}'."
            )
            return self._extract_simple_context(
                buggy_code_lines, changed_ranges, file_path, 1000
            )

        return context_snippets

    def _extract_imports_and_constants(
        self, tree: ast.AST, code_lines: List[str]
    ) -> str:
        """
        Extract imports and module-level constants that might be relevant.
        """
        relevant_lines = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if hasattr(node, "lineno"):
                    relevant_lines.append(node.lineno)
            elif isinstance(node, ast.Assign):
                # only top-level assignments (module constants)
                if isinstance(node.targets[0], ast.Name) and node.lineno:
                    # simple heuristic: if it's ALL_CAPS, it's probably a constant
                    if hasattr(node.targets[0], "id") and node.targets[0].id.isupper():
                        relevant_lines.append(node.lineno)

        if relevant_lines:
            # get a few lines around each import/constant
            lines_to_include = set()
            for line_num in relevant_lines:
                lines_to_include.add(line_num - 1)  # convert to 0-based indexing

            # sort and extract
            selected_lines = sorted(lines_to_include)
            return "\n".join(
                code_lines[i] for i in selected_lines if 0 <= i < len(code_lines)
            )

        return ""

    def _extract_simple_context(
        self,
        buggy_code_lines: List[str],
        changed_ranges: List[Tuple[int, int]],
        file_path: str,
        max_tokens: int,
    ) -> Dict[str, str]:
        """
        Fallback: extract lines around changes when AST parsing fails.
        """
        context_lines = set()
        context_margin = 20  # lines before and after each change

        for start, end in changed_ranges:
            for line_num in range(
                max(1, start - context_margin),
                min(len(buggy_code_lines) + 1, end + context_margin + 1),
            ):
                context_lines.add(line_num - 1)  # convert to 0-based

        # estimate tokens and truncate if needed
        selected_lines = sorted(context_lines)
        if len(selected_lines) * 10 > max_tokens:  # rough estimate: 10 tokens per line
            # take lines closest to changes
            selected_lines = selected_lines[: max_tokens // 10]

        if selected_lines:
            snippet = "\n".join(
                f"{i+1:4d}: {buggy_code_lines[i]}" for i in selected_lines
            )
            return {f"Context around changes in {file_path}": snippet}

        return {}

    def _extract_minimal_context(
        self,
        buggy_code_lines: List[str],
        changed_ranges: List[Tuple[int, int]],
        file_path: str,
        max_tokens: int,
    ) -> Dict[str, str]:
        """
        Extract just the changed lines plus minimal context when functions are too large.
        """
        context_lines = set()
        context_margin = 10

        for start, end in changed_ranges:
            for line_num in range(
                max(1, start - context_margin),
                min(len(buggy_code_lines) + 1, end + context_margin + 1),
            ):
                context_lines.add(line_num - 1)

        selected_lines = sorted(context_lines)
        snippet = "\n".join(
            f"{i+1:4d}: {buggy_code_lines[i]}"
            for i in selected_lines[: max_tokens // 10]
        )

        return {f"Minimal context from {file_path}": snippet} if snippet else {}

    def _prioritize_context_by_relevance(
        self, functions_dict: Dict[str, str], bug_description: str = ""
    ) -> Dict[str, str]:
        """
        Score functions by likely relevance to the bug and return them in priority order.
        """
        if not bug_description:
            return functions_dict

        scores = {}
        bug_keywords = set(
            word.lower() for word in bug_description.split() if len(word) > 2
        )

        for func_key, func_content in functions_dict.items():
            score = 0
            content_lower = func_content.lower()
            func_name_lower = func_key.lower()

            # score based on various relevance factors:

            # 1. function name matches bug keywords
            for keyword in bug_keywords:
                if keyword in func_name_lower:
                    score += 10
                if keyword in content_lower:
                    score += 3

            # 2. contains error handling (likely bug-prone areas)
            error_patterns = [
                "try:",
                "except:",
                "raise",
                "error",
                "exception",
                "assert",
            ]
            for pattern in error_patterns:
                if pattern in content_lower:
                    score += 5

            # 3. has complex logic (many branches - more bug-prone)
            complexity_indicators = ["if ", "for ", "while ", "elif "]
            complexity_count = sum(
                content_lower.count(indicator) for indicator in complexity_indicators
            )
            if complexity_count > 3:
                score += 3
            elif complexity_count > 6:
                score += 5

            # 4. contains common bug-related terms
            bug_terms = [
                "null",
                "none",
                "empty",
                "zero",
                "index",
                "length",
                "size",
                "bounds",
            ]
            for term in bug_terms:
                if term in content_lower:
                    score += 2

            # 5. function size penalty (very large functions are harder to analyze)
            line_count = func_content.count("\n")
            if line_count > 100:
                score -= 3
            elif line_count > 50:
                score -= 1

            scores[func_key] = score

        # sort by score (highest first) and return as ordered dict
        sorted_functions = sorted(
            functions_dict.items(), key=lambda x: scores.get(x[0], 0), reverse=True
        )

        # log the scoring for debugging
        return dict(sorted_functions)

    def _extract_relevant_imports(
        self, commit_sha: str, max_tokens: int
    ) -> Dict[str, str]:
        """
        Extract imports that might be relevant to the changed code.
        """
        commit: GitCommit = self.repo.commit(commit_sha)
        if not commit.parents:
            return {}

        parent: GitCommit = commit.parents[0]
        diffs = parent.diff(commit, create_patch=True)
        import_context = {}

        for diff in diffs:
            if not diff.a_path or not str(diff.a_path).endswith(".py"):
                continue

            try:
                buggy_code = (
                    (parent.tree / diff.a_path).data_stream.read().decode("utf-8")
                )
                tree = ast.parse(buggy_code)

                imports = []
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            imports.append(f"import {alias.name}")
                    elif isinstance(node, ast.ImportFrom):
                        module = node.module or ""
                        names = [alias.name for alias in node.names]
                        imports.append(f"from {module} import {', '.join(names)}")

                if imports:
                    import_text = "\n".join(imports[:10])  # limit to first 10 imports
                    estimated_tokens = len(import_text.split()) * 0.75

                    if estimated_tokens <= max_tokens:
                        import_context[f"Imports from {diff.a_path}"] = import_text

            except Exception as e:
                self.log(
                    f"    Warning: Could not extract imports from {diff.a_path}: {e}"
                )

        return import_context

    def _extract_function_signatures(
        self, commit_sha: str, max_tokens: int
    ) -> Dict[str, str]:
        """
        Extract function signatures (just the def lines) from the entire file for context.
        """
        commit: GitCommit = self.repo.commit(commit_sha)
        if not commit.parents:
            return {}

        parent: GitCommit = commit.parents[0]
        diffs = parent.diff(commit, create_patch=True)
        signature_context = {}

        for diff in diffs:
            if not diff.a_path or not str(diff.a_path).endswith(".py"):
                continue

            try:
                buggy_code = (
                    (parent.tree / diff.a_path).data_stream.read().decode("utf-8")
                )
                buggy_lines = buggy_code.splitlines()
                tree = ast.parse(buggy_code)

                signatures = []
                for node in ast.walk(tree):
                    if isinstance(
                        node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                    ):
                        line_idx = node.lineno - 1
                        if 0 <= line_idx < len(buggy_lines):
                            # get the definition line (and maybe docstring first line)
                            def_line = buggy_lines[line_idx].strip()
                            signature_info = f"Line {node.lineno}: {def_line}"

                            # add docstring first line if available
                            if (
                                isinstance(
                                    node, (ast.FunctionDef, ast.AsyncFunctionDef)
                                )
                                and node.body
                                and isinstance(node.body[0], ast.Expr)
                                and isinstance(node.body[0].value, ast.Constant)
                                and isinstance(node.body[0].value.value, str)
                            ):
                                docstring_first_line = (
                                    node.body[0].value.value.split("\n")[0].strip()
                                )
                                if docstring_first_line:
                                    signature_info += f" # {docstring_first_line}"

                            signatures.append(signature_info)

                if signatures:
                    signature_text = "\n".join(signatures)
                    estimated_tokens = len(signature_text.split()) * 0.75

                    if estimated_tokens <= max_tokens:
                        signature_context[f"Function signatures from {diff.a_path}"] = (
                            signature_text
                        )

            except Exception as e:
                self.log(
                    f"    Warning: Could not extract signatures from {diff.a_path}: {e}"
                )

        return signature_context


# ==============================================================================
#  STRUCTURAL DEPENDENCY GATHERER - Analysis-Augmented (AAG) strategy
# ==============================================================================


class StructuralDependencyGatherer(BaseContextGatherer):
    """Gathers definitions of functions called by the buggy function (within the same file)."""

    @property
    def name(self) -> str:
        return "Repository Knowledge (Structural Dependencies)"

    def gather(self, bug_data: dict, **kwargs) -> dict:
        self.log("  Gathering structural dependencies...")
        commit_sha = bug_data["bug_commit_sha"]

        commit: GitCommit = self.repo.commit(commit_sha)
        if not commit.parents:
            return {}

        parent: GitCommit = commit.parents[0]
        diffs = parent.diff(commit, create_patch=True)

        context = {}

        for diff in diffs:
            if not diff.a_path or not str(diff.a_path).endswith(".py"):
                continue

            try:
                buggy_code = (
                    (parent.tree / diff.a_path).data_stream.read().decode("utf-8")
                )
                tree = ast.parse(buggy_code)

                # find which class the change is in
                insertion_line = self._get_insertion_line(diff.diff)
                target_class = None

                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        start_line = node.lineno
                        end_line = getattr(node, "end_lineno", start_line)
                        if start_line <= insertion_line <= end_line:
                            target_class = node
                            break

                if target_class:
                    related_items = []

                    # show inheritance
                    if target_class.bases:
                        base_names = [
                            self._get_name(base) for base in target_class.bases
                        ]
                        related_items.append(
                            f"Class '{target_class.name}' inherits from: {', '.join(base_names)}"
                        )

                    # show only operator methods from this class
                    for child in target_class.body:
                        if isinstance(child, ast.FunctionDef):
                            if child.name.startswith("__") and child.name.endswith(
                                "__"
                            ):
                                related_items.append(f"Operator method: {child.name}")

                    if related_items:
                        context[f"FILE: {diff.a_path}\nStructural Information"] = (
                            "\n".join(related_items)
                        )

            except Exception as e:
                self.log(f"    Warning: Could not extract structural info: {e}")

        return context

    def _get_insertion_line(self, patch_content):
        """Extract insertion line from diff"""
        if isinstance(patch_content, bytes):
            patch_text = patch_content.decode("utf-8")
        else:
            patch_text = str(patch_content)

        for line in patch_text.splitlines():
            if line.startswith("@@"):
                match = re.match(r"@@\s*-(\d+)", line)
                if match:
                    return int(match.group(1))
        return 0

    def _get_name(self, node):
        """Extract name from AST node"""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_name(node.value)}.{node.attr}"
        return str(node)

    def _get_changed_node_info(self, commit: GitCommit) -> Dict[str, Set[str]]:
        """
        Finds the names of the functions/classes that were changed in a commit.
        Returns a dict mapping file paths to a set of node names.
        """
        if not commit.parents:
            return {}
        parent = commit.parents[0]

        print(f"DEBUG: Comparing commits:")
        print(f"  Parent (buggy): {parent.hexsha[:7]}")
        print(f"  Current (fix): {commit.hexsha[:7]}")

        diffs = parent.diff(commit, create_patch=True)

        changed_node_info = {}
        for diff in diffs:
            if not diff.a_path or not diff.a_path.endswith(".py"):
                continue

            # DEBUG: print diff details
            print(f"DEBUG: Diff for {diff.a_path}:")
            print(f"  new_file: {diff.new_file}")
            print(f"  deleted_file: {diff.deleted_file}")
            print(f"  a_path: {diff.a_path}")
            print(f"  b_path: {diff.b_path}")
            print(f"  First 200 chars of diff: {str(diff.diff)[:200]}")

            try:
                file_content = (
                    (parent.tree / diff.a_path).data_stream.read().decode("utf-8")
                )
                tree = ast.parse(file_content)
                changed_ranges = _parse_diff_ranges(diff.diff)

                # use existing helper to find the nodes containing these changes
                containing_nodes = _find_containing_functions_and_classes(
                    tree, changed_ranges
                )

                if containing_nodes:
                    changed_node_info[diff.a_path] = {
                        name for name, _, _, _, _ in containing_nodes
                    }
            except Exception:
                continue  # ignore files that can't be parsed

        return changed_node_info

    def _find_function_def(self, tree: ast.AST, func_name: str) -> Any:
        """Walks an AST to find the definition of a function by name."""
        for node in ast.walk(tree):
            if (
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == func_name
            ):
                return node
        return None


# ==============================================================================
#  HISTORICAL CONTEXT GATHERER - Retrieval-Augmented (RAG) strategy
# ==============================================================================


class HistoricalContextGatherer(BaseContextGatherer):
    """Gathers historical context, like co-occurring files and the last change."""

    @property
    def name(self) -> str:
        return "Repository Knowledge (Historical Context)"

    def gather(self, bug_data: dict, **kwargs) -> dict:
        self.log("  Gathering historical context...")
        max_commits = kwargs.get("max_historical_commits", 5)

        commit_sha = bug_data["bug_commit_sha"]
        commit: GitCommit = self.repo.commit(commit_sha)

        if not commit.parents:
            return {}

        parent = commit.parents[0]
        diffs = parent.diff(commit, create_patch=True)

        context = {}

        for diff in diffs:
            if not diff.a_path or not str(diff.a_path).endswith(".py"):
                continue

            try:
                # find commits that modified this file
                file_history = list(
                    self.repo.iter_commits(
                        max_count=max_commits + 10, paths=diff.a_path
                    )
                )

                relevant_commits = []
                for hist_commit in file_history[:max_commits]:
                    # skip the current commit
                    if hist_commit.hexsha == commit_sha:
                        continue

                    # ensure message is a string - handle bytes, memoryview, etc.
                    commit_msg = hist_commit.message
                    if isinstance(commit_msg, (bytes, memoryview)):
                        commit_msg = bytes(commit_msg).decode("utf-8", errors="replace")
                    elif not isinstance(commit_msg, str):
                        commit_msg = str(commit_msg)

                    msg = commit_msg.split("\n")[0][:100]
                    relevant_commits.append(f"- {hist_commit.hexsha[:8]}: {msg}")
                    self.log(f"    --> Found relevant commit: {hist_commit.hexsha[:8]}")

                if relevant_commits:
                    context[f"FILE: {diff.a_path}\nRecent Changes"] = "\n".join(
                        [
                            f"Recent commits that modified this file:",
                            *relevant_commits[:5],
                        ]
                    )

            except Exception as e:
                self.log(
                    f"    Warning: Could not extract history for {diff.a_path}: {e}"
                )

        return context
