import ast
import re
import json
from pathlib import Path
from typing import Any, Union
from git import Repo
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from core.logger import log

CodeNode = Union[ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef]


class ContextBuilder:
    """Gets data to give to an LLM as context, using various methods."""

    def __init__(
        self,
        repo_path: str | Path,
        max_snippets: int = 5,
        debug: bool = True,
        cache_dir: Path | None = None,
    ):
        repo_path = Path(repo_path)

        # all info gathering methods
        self.aag_builder = AAGBuilder(repo_path)
        self.rag_retriever = RAGRetriever(repo_path, max_snippets)
        self.structural_analyzer = StructuralAnalyzer(repo_path)
        self.historical_analyzer = HistoricalAnalyzer(repo_path)
        self.formatter = ContextFormatter(debug)

        self.cache_dir = cache_dir
        if cache_dir:
            cache_dir.mkdir(parents=True, exist_ok=True)

    def build(self, bug: dict[str, Any]) -> dict[str, Any]:
        """Build from all methods."""

        cached_context = self._load_from_cache(bug)
        if cached_context is not None:
            log("  --> Using cached context.")
            return cached_context

        # debugging
        changed_files = bug.get("changed_files", [])

        if not changed_files:
            log("  --> WARNING: No changed_files provided!")
            return self._empty_context()

        log(f"  --> Changed files to analyze: {changed_files}")

        # check if files exist
        existing_files = []
        for file_path in changed_files:
            full_path = Path(self.aag_builder.repo_path) / file_path
            if full_path.exists():
                log(f"      {file_path} exists")
                existing_files.append(file_path)
            else:
                log(f"      {file_path} MISSING at current commit")

        if not existing_files:
            log("  --> WARNING: No changed files at parent commit (all newly added?)")
            return self._empty_context()
        # debugging

        log("  --> Building syntax graph...")
        aag_context = self.aag_builder.build_syntax_graph(existing_files)
        log(
            f"      Found {len(aag_context.get('classes', {}))} classes, {len(aag_context.get('functions', {}))} functions"
        )

        log("  --> Finding relevant code snippets...")
        bug_with_existing = {**bug, "changed_files": existing_files}
        rag_context = self.rag_retriever.get_snippets(bug_with_existing)
        log(f"      Found {len(rag_context.get('snippets', []))} snippets")

        log("  --> Analyzing code structure...")
        structural_info = self.structural_analyzer.analyze_structure(existing_files)
        log(
            f"      Found {len(structural_info.get('class_hierarchy', {}))} classes in hierarchy"
        )

        log("  --> Checking git history...")
        historical_info = self.historical_analyzer.analyze_history(bug_with_existing)
        log(
            f"      Found {len(historical_info.get('recent_changes', []))} recent changes, {len(historical_info.get('related_commits', []))} related commits"
        )

        context = {
            "aag": aag_context,
            "rag": rag_context,
            "structural": structural_info,
            "historical": historical_info,
        }

        self._save_to_cache(bug, context)
        return context

    def _empty_context(self) -> dict[str, Any]:
        """Return empty context structure."""
        return {
            "aag": {
                "classes": {},
                "functions": {},
                "dependencies": [],
                "call_graph": [],
            },
            "rag": {"snippets": [], "relevance_scores": []},
            "structural": {"class_hierarchy": {}, "method_signatures": {}},
            "historical": {"recent_changes": [], "related_commits": []},
        }

    def _get_cache_path(self, bug: dict[str, Any]) -> Path | None:
        """Get cache file path for this bug."""
        if not self.cache_dir:
            return None

        repo_name = bug.get("repo_name", "unknown_repo")
        commit_sha = bug.get("bug_commit_sha", "unknown_sha")

        safe_repo_name = repo_name.replace("/", "_").replace("\\", "_")

        repo_cached_dir = self.cache_dir / safe_repo_name
        repo_cached_dir.mkdir(parents=True, exist_ok=True)

        cache_filename = f"{commit_sha[:12]}.json"

        return repo_cached_dir / cache_filename

    def _load_from_cache(self, bug: dict[str, Any]) -> dict[str, Any] | None:
        """Load context from cache if it exists."""
        cache_path = self._get_cache_path(bug)

        if not cache_path or not cache_path.exists():
            return None

        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))

            required_keys = {"aag", "rag", "structural", "historical"}
            if not all(key in cached for key in required_keys):
                log("  --> Cache missing required keys, rebuilding...")
                return None

            return cached

        except Exception as e:
            log(f"  --> ERROR: loading cache file: {e}, rebuilding...")
            return None

    def _save_to_cache(self, bug: dict[str, Any], context: dict[str, Any]) -> None:
        """Save context to cache."""
        cache_path = self._get_cache_path(bug)

        if not cache_path:
            return

        try:
            cache_path.write_text(json.dumps(context, indent=2), encoding="utf-8")

            log(f"  --> Saved context to cache: {cache_path.name}")

        except Exception as e:
            log(f"  --> ERROR: saving cache file: {e}")

    def format(self, context: dict[str, Any]) -> str:
        """Turn context into LLM friendly text."""
        return self.formatter.format(context)

    def build_and_format(self, bug: dict[str, Any]) -> tuple[dict[str, Any], str]:

        context = self.build(bug)
        formatted = self.formatter.format(context)
        return context, formatted


class AAGBuilder:
    """Parse Python files to build syntax graph: code structure and dependencies."""

    def __init__(self, repo_path: str | Path):
        self.repo_path = Path(repo_path)

    @staticmethod
    def _get_name_static(node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{AAGBuilder._get_name_static(node.value)}.{node.attr}"
        else:
            try:
                return ast.unparse(node)
            except:
                return str(type(node).__name__)

    def build_syntax_graph(self, changed_files: list[str]) -> dict[str, Any]:
        """Build graph for the changed files."""
        aag = {"classes": {}, "functions": {}, "dependencies": [], "call_graph": []}

        log(
            f"      AAG: Processing {len(changed_files)} files from {self.repo_path}"
        )  # debug

        for file_path in changed_files:

            # debugging
            full_path = self.repo_path / file_path

            if not full_path.exists():
                log(f"      AAG: File missing: {file_path}")
                continue

            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read()

                log(f"      AAG: {file_path} ({len(content)} bytes)")

                if not content.strip():
                    log(f"      AAG: WARNING: File is empty!")
                    continue

                if not file_path.endswith(".py"):
                    log(f"      AAG: WARNING: Not a .py file")
                    continue

            except Exception as e:
                log(f"      AAG: ERROR: Cannot read {file_path}: {e}")
                continue
            # debugging

            self._parse_file_structure(file_path, aag)

        log(
            f"      AAG: Result - {len(aag['classes'])} classes, {len(aag['functions'])} functions"
        )  # debug

        return aag

    def _parse_file_structure(self, file_path: str, aag: dict[str, Any]) -> None:
        """Parse a file, get its structure."""
        full_path = self.repo_path / file_path

        if not full_path.exists():
            return

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()  # TODO: use path open?

            log(f"      AAG: Parsing {file_path}...")  # debug

            tree = ast.parse(content, filename=file_path)

            class_count = 0
            func_count = 0

            # go through the tree, looking for classes and functions
            # TODO: have a few of these, restructure needed?
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    class_count += 1
                    self._get_class(node, file_path, aag, tree)
                elif isinstance(node, ast.FunctionDef):
                    if not self._is_inside_class(node, tree):
                        func_count += 1
                        self._get_function(node, file_path, aag)

            log(
                f"      AAG: Found {class_count} classes, {func_count} top-level functions"
            )

        except SyntaxError as e:
            log(f"      AAG: Syntax error in {file_path}: {e}")
        except Exception as e:
            log(f"      AAG: Parse error in {file_path}: {e}")
            import traceback

            log(traceback.format_exc())

    def _get_class(
        self, node: ast.ClassDef, file_path: str, aag: dict[str, Any], tree: ast.Module
    ) -> None:
        """Extract class info."""
        methods = []

        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                methods.append(
                    {
                        "name": item.name,
                        "params": [arg.arg for arg in item.args.args],
                        "line": item.lineno,
                    }
                )

        aag["classes"][node.name] = {
            "methods": methods,
            "bases": [self._get_name_static(base) for base in node.bases],
            "location": f"{file_path}:{node.lineno}",
        }

    def _get_function(
        self, node: ast.FunctionDef, file_path: str, aag: dict[str, Any]
    ) -> None:
        """Extract function info."""
        aag["functions"][node.name] = {
            "params": [arg.arg for arg in node.args.args],
            "calls": self._get_function_calls(node),
            "location": f"{file_path}:{node.lineno}",
        }

    def _is_inside_class(self, func_node: ast.FunctionDef, tree: ast.Module) -> bool:
        """Check if function is from a class."""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if item == func_node:
                        return True
        return False

    def _get_function_calls(self, node: ast.FunctionDef) -> list[str]:
        """Find all calls inside a function."""
        calls = []

        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    calls.append(child.func.id)
                elif isinstance(child.func, ast.Attribute):
                    calls.append(child.func.attr)

        # for duplicates
        return list(set(calls))


class RAGRetriever:
    """Find and rank relevant snippets with TF-IDF."""

    def __init__(self, repo_path: str | Path, max_snippets: int = 5):
        self.repo_path = Path(repo_path)
        self.max_snippets = max_snippets

    # TODO: confusing naming with all the snippet functions, refactor later
    def get_snippets(self, bug: dict[str, Any]) -> dict[str, Any]:
        """Find the most relevant code for this bug."""

        query = f"{bug.get('issue_title', '')} {bug.get('issue_body', '')}"
        # debug
        log(f"      RAG: Query length: {len(query)} chars")
        if not query.strip():
            log(f"      RAG: WARNING  Empty query - no issue title/body!")
        # debug
        snippets = self._get_all_snippets(bug.get("changed_files", []))

        log(f"      RAG: Extracted {len(snippets)} total snippets")  # debug

        if not snippets:
            log(f"      RAG: WARNING No snippets found!")
            return {"snippets": [], "relevance_scores": []}

        result = self._rank_snippets(query, snippets)
        log(f"      RAG: Ranked to {len(result.get('snippets', []))} snippets")

        return result

    def _get_all_snippets(self, changed_files: list[str]) -> list[dict[str, Any]]:
        snippets = []

        for file_path in changed_files:
            snippets.extend(self._get_full_snippets(file_path))

        return snippets

    def _get_full_snippets(self, file_path: str) -> list[dict[str, Any]]:
        full_path = self.repo_path / file_path

        if not full_path.exists():
            return []

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()

            tree = ast.parse(content, filename=file_path)
            lines = content.split("\n")

        except Exception as e:
            log(f"Warning: Could not parse {file_path}: {e}")
            return []

        snippets = []

        # TODO: already have this in AAG, refactor later
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                snippet_data = self._get_snippet(node, lines, file_path)
                snippets.append(snippet_data)

        return snippets

    def _get_snippet(
        self, node: ast.AST, lines: list[str], file_path: str
    ) -> dict[str, Any]:
        """Extract a snippet from an AST node."""

        if not isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
            return self._empty_snippet()

        start = node.lineno - 1
        end = node.end_lineno if node.end_lineno else len(lines)
        size = end - start

        # small enough, include everything
        if size <= 50:
            return self._get_small_snippet(node, lines, start, end, file_path, size)

        # truncate to use less tokens
        return self._get_large_snippet(node, lines, start, end, file_path, size)

    def _get_small_snippet(
        self,
        node: CodeNode,
        lines: list[str],
        start: int,
        end: int,
        file_path: str,
        size: int,
    ) -> dict[str, Any]:
        """Get small snippet (<=50 lines)."""
        code = "\n".join(lines[start:end])

        docstring = ""
        if isinstance(
            node, (ast.FunctionDef, ast.ClassDef, ast.Module, ast.AsyncFunctionDef)
        ):
            docstring = ast.get_docstring(node) or ""

        return {
            "type": (
                "function"
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                else "class"
            ),
            "name": node.name,
            "file": file_path,
            "line": node.lineno,
            "code": code,
            "signature": lines[start] if start < len(lines) else "",
            "docstring": docstring,
            "size": size,
            "truncated": False,
        }

    def _get_large_snippet(
        self,
        node: CodeNode,
        lines: list[str],
        start: int,
        end: int,
        file_path: str,
        size: int,
    ) -> dict[str, Any]:
        """Get and truncate snippet (>50 lines)."""
        extracted_lines = []

        # func signature
        extracted_lines.append(lines[start])

        # docstrings give valuable info
        docstring = ""
        if isinstance(
            node, (ast.FunctionDef, ast.ClassDef, ast.Module, ast.AsyncFunctionDef)
        ):
            docstring = ast.get_docstring(node) or ""

        current = start + 1

        if docstring:

            doc_start = start + 1
            doc_end = self._find_docstring_end(lines, doc_start, end)
            extracted_lines.extend(lines[doc_start:doc_end])
            extracted_lines.append("    # ... (docstring continues) ...")
            current = doc_end

        # first lines of logic
        logic_start = current
        extracted_lines.extend(lines[logic_start : min(logic_start + 10, end)])

        if end - (logic_start + 10) > 5:
            extracted_lines.append(
                "    # ... (middle section truncated - see full file) ..."
            )

            # key lines (if, return, etc.)
            key_lines = self._get_key_lines(lines, logic_start + 10, end - 5)
            if key_lines:
                extracted_lines.extend(key_lines[:5])
                extracted_lines.append("    # ... (more logic) ...")

            # last few lines
            extracted_lines.extend(lines[max(end - 5, current) : end])
        else:
            # if there is not much left, just have it all
            extracted_lines.extend(lines[logic_start + 10 : end])

        return {
            "type": (
                "function"
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                else "class"
            ),
            "name": node.name,
            "file": file_path,
            "line": node.lineno,
            "code": "\n".join(extracted_lines),
            "signature": lines[start] if start < len(lines) else "",
            "docstring": docstring,
            "size": size,
            "truncated": True,
        }

    def _find_docstring_end(self, lines: list[str], start: int, end: int) -> int:
        for i in range(start, min(start + 20, end)):
            if i < len(lines) and ('"""' in lines[i] or "'''" in lines[i]):
                # single line?
                if lines[i].count('"""') >= 2 or lines[i].count("'''") >= 2:
                    return i + 1
                return i + 1
        return start

    def _get_key_lines(self, lines: list[str], start: int, end: int) -> list[str]:
        """Get ifs, returns, etc."""
        key_lines = []

        for i in range(start, end):
            if i < len(lines):
                line = lines[i].strip()
                if line.startswith(
                    (
                        "if ",
                        "elif ",
                        "else:",
                        "return ",
                        "raise ",
                        "def ",
                        "class ",
                        "async def ",
                    )
                ):
                    key_lines.append(lines[i])

        return key_lines

    def _empty_snippet(self) -> dict[str, Any]:
        """Return placeholder."""
        return {
            "code": "",
            "signature": "",
            "docstring": "",
            "size": 0,
            "truncated": False,
        }

    def _rank_snippets(
        self, query: str, snippets: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Rank snippets with TF-IDF."""

        # build data: query + snippet metadata
        corpus = [query] + [
            f"{s['name']} {s['signature']} {s['docstring']}" for s in snippets
        ]

        try:
            # TF-IDF stuff: TODO
            vectorizer = TfidfVectorizer(stop_words="english", max_features=1000)
            tfidf_matrix = vectorizer.fit_transform(corpus)

            # calculate similarity
            query_vector = tfidf_matrix[0:1]  # type: ignore[index]
            doc_vectors = tfidf_matrix[1:]  # type: ignore[index]
            similarities = cosine_similarity(query_vector, doc_vectors).flatten()

            # sort and keep only the best few
            ranked_indices = similarities.argsort()[::-1]
            top_snippets = [
                snippets[i]
                for i in ranked_indices[: self.max_snippets]
                if i < len(snippets)
            ]
            top_scores = [
                float(similarities[i])
                for i in ranked_indices[: self.max_snippets]
                if i < len(similarities)
            ]

            return {"snippets": top_snippets, "relevance_scores": top_scores}

        except Exception as e:
            log(
                f"Warning: TF-IDF ranking failed: {e}, returning first {self.max_snippets} snippets"
            )
            return {
                "snippets": snippets[: self.max_snippets],
                "relevance_scores": [1.0] * min(self.max_snippets, len(snippets)),
            }


class StructuralAnalyzer:
    """Analyzes code structure (classes, functions, whats within what)."""

    def __init__(self, repo_path: str | Path):
        self.repo_path = Path(repo_path)

    def analyze_structure(self, changed_files: list[str]) -> dict[str, Any]:
        """TODO"""

        info = {"class_hierarchy": {}, "method_signatures": {}}

        for file_path in changed_files:
            self._get_structural_from_file(file_path, info)

        return info

    def _get_structural_from_file(self, file_path: str, info: dict[str, Any]) -> None:
        """Analyze a single file and update structural info."""
        full_path = self.repo_path / file_path

        if not full_path.exists():
            return

        try:
            with open(full_path, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=file_path)
        except Exception as e:
            log(f"Warning: Could not parse {file_path}: {e}")
            return

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                self._get_class_info(node, info)

    def _get_class_info(self, node: ast.ClassDef, info: dict[str, Any]) -> None:
        """Get hierarchy and method data."""

        info["class_hierarchy"][node.name] = {
            "bases": [AAGBuilder._get_name_static(base) for base in node.bases],
            "methods": [],
        }

        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                sig = self._get_signature(item)

                info["class_hierarchy"][node.name]["methods"].append(sig["name"])

                method_key = f"{node.name}.{sig['name']}"
                info["method_signatures"][method_key] = sig

    def _get_signature(
        self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef]
    ) -> dict[str, Any]:
        """Get function details."""

        return {
            "name": node.name,
            "params": [arg.arg for arg in node.args.args],
            "defaults": len(node.args.defaults),
            "return_type": ast.unparse(node.returns) if node.returns else None,
            "decorators": [ast.unparse(dec) for dec in node.decorator_list],
            "is_async": isinstance(node, ast.AsyncFunctionDef),
        }


class HistoricalAnalyzer:
    """Get relevant parts of git history."""

    def __init__(self, repo_path: str | Path):
        self.repo_path = Path(repo_path)

    def analyze_history(self, bug: dict[str, Any]) -> dict[str, Any]:
        """Get history from git."""
        # TODO: i got quite a few of these, where the class only has one public function, refactor needed?
        try:
            repo = Repo(self.repo_path)

            history = {"recent_changes": [], "related_commits": []}
            self._get_recent_changes(bug, repo, history)
            self._get_related_commits(bug, repo, history)

            return history

        except Exception as e:
            log(f"Warning: git history unavailable: {e}")
            return {"recent_changes": [], "related_commits": []}

    def _get_recent_changes(
        self, bug: dict[str, Any], repo: Repo, history: dict[str, Any]
    ) -> None:
        """Get recent commits of the changed files."""

        for file_path in bug.get("changed_files", [])[:3]:  # limit to 3 files
            try:
                commits = list(repo.iter_commits(paths=file_path, max_count=5))

                for commit in commits:

                    # skip the bug commit itself
                    if commit.hexsha == bug.get("bug_commit_sha"):
                        continue

                    commit_message = str(commit.message) if commit.message else ""
                    message_parts = commit_message.split("\n")
                    first_line = message_parts[0][:80] if message_parts else ""

                    history["recent_changes"].append(
                        {
                            "sha": commit.hexsha[:7],
                            "message": first_line,
                            "author": str(commit.author),
                            "date": commit.committed_datetime.isoformat(),
                        }
                    )

            except Exception as e:
                log(f"Warning: Could not get history for {file_path}: {e}")

    def _get_related_commits(
        self, bug: dict[str, Any], repo: Repo, history: dict[str, Any]
    ) -> None:
        """Find commits similar to the issues."""

        keywords = self._get_keywords(bug.get("issue_title", ""))

        if not keywords:
            return

        # check recent commits for keyword matches
        for commit in repo.iter_commits(max_count=100):

            commit_message = str(commit.message) if commit.message else ""
            message_lower = commit_message.lower()

            relevance = sum(1 for kw in keywords if kw.lower() in message_lower)

            if relevance > 0:
                message_parts = commit_message.split("\n")
                first_line = message_parts[0][:80] if message_parts else ""

                history["related_commits"].append(
                    {
                        "sha": commit.hexsha[:7],
                        "message": first_line,
                        "relevance": relevance,
                    }
                )

        # keep the top 5
        history["related_commits"].sort(key=lambda x: x["relevance"], reverse=True)
        history["related_commits"] = history["related_commits"][:5]

    @staticmethod
    def _get_keywords(text: str) -> list[str]:
        """Get keywords, skip stopwords."""
        stop_words = {
            "the",
            "a",
            "an",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "is",
            "not",
            "does",
            "and",
            "or",
        }

        words = re.findall(r"\w+", text.lower())
        return [w for w in words if w not in stop_words and len(w) > 3]


class ContextFormatter:
    """Turns the gathered info into LLM-friendly, formatted text."""

    def __init__(self, debug: bool = True):
        self.debug = debug

    def format(self, context: dict[str, Any]) -> str:
        """Collect and format text from all methods."""
        # TODO: should this function be split into two?

        if self.debug:
            self._log_debug_info(context)

        sections = []
        sections.append(self._format_aag(context.get("aag", {})))
        sections.append(self._format_rag(context.get("rag", {})))
        sections.append(self._format_structural(context.get("structural", {})))
        sections.append(self._format_historical(context.get("historical", {})))
        result = "\n".join(s for s in sections if s.strip())

        if self.debug:
            self._log_result_info(result)

        return result

    def _log_debug_info(self, context: dict[str, Any]) -> None:
        log("\n" + "=" * 60)
        log("DEBUG: Context summary")
        log(f"Classes found: {len(context.get('aag', {}).get('classes', {}))}")
        log(f"Functions found: {len(context.get('aag', {}).get('functions', {}))}")
        log(f"Code snippets: {len(context.get('rag', {}).get('snippets', []))}")
        log(
            f"Structural classes: {len(context.get('structural', {}).get('class_hierarchy', {}))}"
        )
        log(
            f"Recent changes: {len(context.get('historical', {}).get('recent_changes', []))}"
        )
        log(
            f"Related commits: {len(context.get('historical', {}).get('related_commits', []))}"
        )
        log("=" * 60 + "\n")

    def _log_result_info(self, result: str) -> None:
        """Show what context was found."""
        log(f"DEBUG: Context length: {len(result)} chars")
        if len(result) < 100:
            log(f"DEBUG: WARNING - Context seems too short!")
            log(f"DEBUG: Preview: {result[:500]}")

    def _format_aag(self, aag: dict[str, Any]) -> str:
        """Format the syntax graph."""
        # TODO: is this being here hurting encapsulation?
        output = []

        if aag.get("classes"):
            output.append("**CODE STRUCTURE (Syntax Graph):**")
            output.append("\nClasses:")

            for class_name, class_info in aag["classes"].items():
                output.append(f"  - {class_name}")
                bases_str = (
                    ", ".join(class_info.get("bases", []))
                    if class_info.get("bases")
                    else "object"
                )
                output.append(f"    Inherits from: {bases_str}")
                methods_str = ", ".join(
                    [m["name"] for m in class_info.get("methods", [])]
                )
                output.append(f"    Methods: {methods_str}")
                output.append(f"    Location: {class_info.get('location', 'unknown')}")

        if aag.get("functions"):
            output.append("\nTop-level Functions:")

            for func_name, func_info in aag["functions"].items():
                params_str = ", ".join(func_info.get("params", []))
                output.append(f"  - {func_name}({params_str})")

                calls = func_info.get("calls", [])
                if calls:
                    calls_str = ", ".join(calls[:5])
                    output.append(f"    Calls: {calls_str}")

        return "\n".join(output)

    def _format_rag(self, rag: dict[str, Any]) -> str:
        """Format the relevant code snippets section."""
        output = []

        if rag.get("snippets"):
            output.append("\n**RELEVANT CODE (Ranked by Relevance):**")

            for i, snippet in enumerate(rag["snippets"], 1):
                scores = rag.get("relevance_scores", [])
                score = scores[i - 1] if i - 1 < len(scores) else 0.0

                truncated = (
                    " [TRUNCATED - large function]" if snippet.get("truncated") else ""
                )
                output.append(
                    f"\n--- Snippet {i} (relevance: {score:.2f}){truncated} ---"
                )
                output.append(f"File: {snippet.get('file')}:{snippet.get('line')}")
                output.append(f"Type: {snippet.get('type')} '{snippet.get('name')}'")

                if snippet.get("docstring"):
                    doc_preview = snippet["docstring"][:100]
                    if len(snippet["docstring"]) > 100:
                        doc_preview += "..."
                    output.append(f"Purpose: {doc_preview}")

                output.append(f"\n```python\n{snippet.get('code', '')}\n```")

        return "\n".join(output)

    def _format_structural(self, structural: dict[str, Any]) -> str:
        """Format class hierarchy section."""
        output = []

        if structural.get("class_hierarchy"):
            output.append("\n**CLASS HIERARCHY:**")

            for class_name, info in structural["class_hierarchy"].items():
                bases_str = (
                    ", ".join(info.get("bases", [])) if info.get("bases") else "object"
                )
                output.append(f"  {class_name}({bases_str})")

                methods = info.get("methods", [])
                for method in methods[:10]:
                    sig = structural.get("method_signatures", {}).get(
                        f"{class_name}.{method}", {}
                    )
                    params = ", ".join(sig.get("params", []))
                    output.append(f"    - {method}({params})")

        return "\n".join(output)

    def _format_historical(self, historical: dict[str, Any]) -> str:
        """Format the git history section."""
        output = []

        if historical.get("recent_changes"):
            output.append("\n**RECENT CHANGES TO THESE FILES:**")
            for change in historical["recent_changes"][:3]:
                output.append(
                    f"  [{change.get('sha', '?')}] {change.get('message', '')}"
                )

        if historical.get("related_commits"):
            output.append("\n**RELATED COMMITS (Similar Issues):**")
            for commit in historical["related_commits"][:3]:
                output.append(
                    f"  [{commit.get('sha', '?')}] {commit.get('message', '')}"
                )

        return "\n".join(output)
