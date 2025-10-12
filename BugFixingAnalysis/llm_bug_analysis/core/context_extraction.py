import ast
import re
from typing import Dict, Any, Set, List, Tuple
from git import Repo, Commit as GitCommit
from abc import ABC, abstractmethod
from collections import Counter

# ==============================================================================
#  STANDALONE HELPER FUNCTIONS
# ==============================================================================


def _parse_diff_ranges(patch_content) -> List[Tuple[int, int]]:
    """
    Parse diff to extract all changed line ranges from the original file.
    Returns list of (start_line, end_line) tuples.
    """
    if patch_content is None:
        print("DEBUG: patch_content is None!")
        return []

    # properly decode bytes to string
    if isinstance(patch_content, bytes):
        patch_text = patch_content.decode("utf-8")
    else:
        patch_text = str(patch_content)

    # DEBUG: Print the actual patch content
    print(f"DEBUG: patch_content type: {type(patch_content)}")
    print(f"DEBUG: patch_text length: {len(patch_text)}")
    print(f"DEBUG: First 500 chars of patch_text:")
    print(repr(patch_text[:500]))
    print(f"DEBUG: Looking for lines starting with '@@'...")

    changed_ranges = []

    for line in patch_text.splitlines():
        # parse hunk headers like @@ -10,5 +10,7 @@
        if line.startswith("@@"):
            print(f"DEBUG: Found @@ line: {line}")
            match = re.match(r"@@\s*-(\d+)(?:,(\d+))?\s*\+(\d+)(?:,(\d+))?\s*@@", line)
            if match:
                original_start = int(match.group(1))
                original_count = int(match.group(2)) if match.group(2) else 1

                print(
                    f"DEBUG: Found hunk - original_start={original_start}, original_count={original_count}"
                )

                # for pure additions, reference the line before the insertion point
                # this gives context about where new code was added
                if original_count == 0:
                    if original_start > 0:
                        # reference the line before where code was inserted
                        changed_ranges.append((original_start, original_start))
                        print(
                            f"DEBUG: Added pure addition range: ({original_start}, {original_start})"
                        )
                    else:
                        print(
                            f"DEBUG: Skipping pure addition at start of file (original_start=0)"
                        )
                else:
                    # normal change or deletion
                    range_tuple = (original_start, original_start + original_count - 1)
                    changed_ranges.append(range_tuple)
                    print(f"DEBUG: Added change range: {range_tuple}")

    print(f"DEBUG: Total ranges before merging: {len(changed_ranges)}")
    print(f"DEBUG: Ranges: {changed_ranges}")

    # merge overlapping ranges
    if changed_ranges:
        changed_ranges.sort()
        merged = [changed_ranges[0]]
        for start, end in changed_ranges[1:]:
            if start <= merged[-1][1] + 1:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))
        print(f"DEBUG: Merged ranges: {merged}")
        return merged

    print("DEBUG: No ranges found!")
    return []


def _find_containing_functions_and_classes(
    tree: ast.AST, changed_ranges: List[Tuple[int, int]]
) -> List[Tuple[str, int, int, str, ast.AST]]:
    """
    Find all functions and classes that contain any of the changed lines.
    Returns list of (name, start_line, end_line, type).
    """
    containing_nodes = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
            start_line = node.lineno
            end_line = getattr(node, "end_lineno", node.lineno)

            # include decorators
            if hasattr(node, "decorator_list") and node.decorator_list:
                start_line = min(d.lineno for d in node.decorator_list)

            # check if any changed range overlaps with this node
            for change_start, change_end in changed_ranges:
                if not (end_line < change_start or start_line > change_end):
                    node_type = (
                        "Function"
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                        else "Class"
                    )
                    containing_nodes.append(
                        (node.name, start_line, end_line, node_type, node)
                    )
                    break

    return containing_nodes


# ==============================================================================
#  THE BLUEPRINT (Abstract Base Class)
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
#  THE FIRST CONCRETE STRATEGY (for existing logic)
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
        commit_sha = bug_data["bug_commit_sha"]
        max_tokens = kwargs.get(
            "max_tokens_per_file", 4000
        )  # get max_tokens from orchestrator

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

                changed_ranges = _parse_diff_ranges(diff.diff)
                if not changed_ranges:
                    self.log(
                        f"    Warning: No valid change ranges found for {diff.a_path}"
                    )
                    continue

                file_context = self._extract_file_context(
                    buggy_code_lines, changed_ranges, diff.a_path, max_tokens
                )
                if file_context:
                    context_snippets.update(file_context)
            except Exception as e:
                self.log(
                    f"    Warning: Could not extract context for {diff.a_path}. Reason: {e}"
                )
        return context_snippets

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
                    buggy_code_lines, changed_ranges, diff.a_path, max_tokens_per_file
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
        max_tokens: int,
    ) -> Dict[str, str]:
        """
        Extract context around changed ranges with size management.
        """
        try:
            tree = ast.parse("\n".join(buggy_code_lines))
        except SyntaxError:
            return (
                {}
            )  # fallback: for now, don't return simple context, prioritize AST context.

        context_snippets = {}

        # strategy 1: try to extract complete functions/classes that contain changes
        functions_and_classes = _find_containing_functions_and_classes(
            tree, changed_ranges
        )

        if functions_and_classes:
            # sort by size (end_line - start_line) to get the smallest containing block first
            functions_and_classes.sort(key=lambda x: x[2] - x[1])

            name, start_line, end_line, node_type, node_obj = functions_and_classes[0]

            # pass the correct object (node_obj) to get_source_segment
            snippet = ast.get_source_segment("\n".join(buggy_code_lines), node_obj)

            if snippet:
                context_key = f"FILE: {file_path}\n{node_type} '{name}' (lines {start_line}-{end_line})"
                context_snippets[context_key] = snippet

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
        snippets = {}
        commit_sha = bug_data["bug_commit_sha"]
        commit = self.repo.commit(commit_sha)
        parent = commit.parents[0]

        # need to find the names of the functions/classes containing the changes
        changed_nodes_info = self._get_changed_node_info(commit)

        for file_path, node_names in changed_nodes_info.items():
            try:
                file_content = (
                    (parent.tree / file_path).data_stream.read().decode("utf-8")
                )
                file_tree = ast.parse(file_content)

                for node in ast.walk(file_tree):
                    # find the AST node for the function that contains the bug
                    if (
                        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and node.name in node_names
                    ):
                        # now, find what functions *it* calls
                        for sub_node in ast.walk(node):
                            if isinstance(sub_node, ast.Call):
                                if isinstance(sub_node.func, ast.Name):

                                    called_func_name = sub_node.func.id
                                    # now find the definition of this function in the same file
                                    called_func_def = self._find_function_def(
                                        file_tree, called_func_name
                                    )
                                    if called_func_def:
                                        key = f"Dependency in {file_path}: Definition of called function '{called_func_name}'"
                                        snippets[key] = ast.get_source_segment(
                                            file_content, called_func_def
                                        )
            except Exception as e:
                self.log(
                    f"    Warning: Could not analyze dependencies for {file_path}. Reason: {e}"
                )

        return snippets

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

            # DEBUG: Print diff details
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
        snippets = {}

        # get the list of changed files from the orchestrator
        changed_py_files = [
            path for path in kwargs.get("changed_files", []) if path.endswith(".py")
        ]
        if not changed_py_files:
            return {}

        # for simplicity, let's focus on the first buggy file
        for buggy_filepath in changed_py_files:

            # --- strategy 1: latest Change before the bug ---
            try:
                # get the two most recent commits that touched this file *before* the buggy state
                commits = list(
                    self.repo.iter_commits(
                        paths=buggy_filepath,
                        max_count=2,
                        before=bug_data["parent_commit_sha"],
                    )
                )
                if len(commits) > 1:
                    latest_commit = commits[0]
                    previous_to_latest = commits[1]

                    # get the diff between these two commits for the specific file
                    diff = previous_to_latest.diff(
                        latest_commit, paths=buggy_filepath, create_patch=True
                    )
                    if diff:
                        diff_text = diff[0].diff
                        key = f"Most recent change to '{buggy_filepath}' before the bug occurred"
                        snippets[key] = (
                            f"--- (from commit {latest_commit.hexsha[:7]}) ---\n{diff_text}"
                        )
            except Exception as e:
                self.log(
                    f"    Warning: Could not get latest change diff for {buggy_filepath}. Reason: {e}"
                )

        # --- strategy 2: Co-occurring Files ---
        try:
            co_changed_counter = Counter()

            for buggy_filepath in changed_py_files:
                # look at the last 50 commits that touched the buggy file
                for commit in self.repo.iter_commits(
                    paths=buggy_filepath, max_count=50
                ):
                    # get all .py files in that commit, excluding the buggy file itself
                    other_files = [
                        f
                        for f in commit.stats.files.keys()
                        if str(f).endswith(".py") and f != buggy_filepath
                    ]
                    co_changed_counter.update(other_files)

            # get the top 2 most common co-occurring files
            if co_changed_counter:
                top_files = co_changed_counter.most_common(2)
                file_list = [f for f, count in top_files]
                key = "Frequently co-changed files"
                snippets[key] = (
                    "The following files are often changed in the same commit as the buggy file:\n- "
                    + "\n- ".join(file_list)
                )
        except Exception as e:
            self.log(
                f"    Warning: Could not determine co-occurring files. Reason: {e}"
            )

        return snippets
