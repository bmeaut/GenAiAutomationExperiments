from __future__ import annotations
import ast
import re
import json
from pathlib import Path
from typing import Any, Union
from git import Repo
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from rank_bm25 import BM25Okapi

from .logger import log
from .ast_utility import ASTUtils

CodeNode = Union[ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef]

# TODO export cache handling?


class ContextBuilder:
    """Gets data to give to an LLM as context, using various methods."""

    def __init__(
        self,
        repo_path: str | Path,
        max_snippets: int = 5,
        debug: bool = True,
        cache_dir: Path | None = None,
        test_context_level: str = "assertions",
    ):
        repo_path = Path(repo_path)

        # all info gathering methods
        self.aag_builder = AAGBuilder(repo_path)
        self.rag_retriever = RAGRetriever(repo_path, max_snippets)
        self.structural_analyzer = StructuralAnalyzer(repo_path)
        self.historical_analyzer = HistoricalAnalyzer(repo_path)
        self.test_metadata_extractor = TestMetadataExtractor(
            repo_path, test_context_level
        )
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

        changed_source_files = bug.get("changed_source_files", [])
        changed_test_files = bug.get("changed_test_files", [])

        if not changed_source_files:
            log("  --> WARNING: No changed_source_files provided!")
            return self._empty_context()

        log(f"  --> Source files to analyze: {changed_source_files}")
        log(f"  --> Test files (metadata only): {changed_test_files}")

        existing_source_files = []
        for file_path in changed_source_files:
            full_path = Path(self.aag_builder.repo_path) / file_path
            if full_path.exists():
                log(f"      {file_path} exists")
                existing_source_files.append(file_path)
            else:
                log(f"      {file_path} MISSING at current commit")

        if not existing_source_files:
            log("  --> WARNING: No source files at parent commit (all newly added?)")
            return self._empty_context()

        log("  --> Building syntax graph...")
        aag_context = self.aag_builder.build_syntax_graph(existing_source_files)
        log(
            f"      Found {len(aag_context.get('classes', {}))} classes, {len(aag_context.get('functions', {}))} functions"
        )

        log("  --> Finding relevant code snippets...")
        # existing_source_files filters files that don't exist at parent commit
        # changed_source_files might include newly added files
        bug_with_existing = {
            **bug,
            "changed_source_files": existing_source_files,
            "changed_test_files": changed_test_files,
        }
        rag_context = self.rag_retriever.get_snippets(bug_with_existing)
        log(f"      Found {len(rag_context.get('snippets', []))} snippets")

        log("  --> Analyzing code structure...")
        structural_info = self.structural_analyzer.analyze_structure(
            existing_source_files
        )
        log(
            f"      Found {len(structural_info.get('class_hierarchy', {}))} classes in hierarchy"
        )

        log("  --> Checking git history...")
        historical_info = self.historical_analyzer.analyze_history(bug_with_existing)
        log(
            f"      Found {len(historical_info.get('recent_changes', []))} recent changes, {len(historical_info.get('related_commits', []))} related commits"
        )

        log("  --> Extracting test metadata...")
        test_metadata = self.test_metadata_extractor.extract_metadata(
            changed_test_files
        )
        log(
            f"      Found {len(test_metadata.get('test_functions', []))} test functions (level: {test_metadata.get('level', 'none')})"
        )

        context = {
            "aag": aag_context,
            "rag": rag_context,
            "structural": structural_info,
            "historical": historical_info,
            "test_metadata": test_metadata,
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
            "test_metadata": {"test_functions": [], "level": "none"},
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

    def build_syntax_graph(self, changed_files: list[str]) -> dict[str, Any]:
        """Build graph for the changed files."""
        aag = {"classes": {}, "functions": {}, "dependencies": [], "call_graph": []}

        log(f"      Building syntax graph for {len(changed_files)} files")

        errors = []
        for file_path in changed_files:
            try:
                self._parse_file_structure(file_path, aag)
            except Exception as e:
                errors.append(f"{file_path}: {e}")

        log(
            f"      --> {len(aag['classes'])} classes, {len(aag['functions'])} functions"
        )
        if errors:
            log(f"      --> {len(errors)} files had errors")

        return aag

    def _parse_file_structure(self, file_path: str, aag: dict[str, Any]) -> None:
        """Parse a file, get its structure."""
        full_path = self.repo_path / file_path

        result = ASTUtils.parse_file(full_path)
        if not result:
            return

        tree, _ = result

        for cls in ASTUtils.get_classes(tree):
            self._get_class(cls, file_path, aag)

        for func in ASTUtils.get_functions(tree, exclude_class_methods=True):
            self._get_function(func, file_path, aag)

    def _get_class(
        self,
        node: ast.ClassDef,
        file_path: str,
        aag: dict[str, Any],
    ) -> None:
        """Extract class info."""
        methods = []

        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.append(
                    {
                        "name": item.name,
                        "params": ASTUtils.get_function_params(item),
                        "line": item.lineno,
                    }
                )

        aag["classes"][node.name] = {
            "methods": methods,
            "bases": ASTUtils.get_base_classes(node),
            "location": f"{file_path}:{node.lineno}",
        }

    def _get_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        file_path: str,
        aag: dict[str, Any],
    ) -> None:
        """Extract function info."""
        aag["functions"][node.name] = {
            "params": ASTUtils.get_function_params(node),
            "calls": ASTUtils.get_function_calls(node),
            "location": f"{file_path}:{node.lineno}",
        }


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
        snippets = self._get_all_snippets(bug.get("changed_source_files", []))

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

        result = ASTUtils.parse_file(full_path)
        if not result:
            return []

        tree, lines = result
        snippets = []

        nodes = ASTUtils.get_classes(tree) + ASTUtils.get_functions(tree)
        for node in nodes:
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

    def _tokenize(self, text: str) -> list[str]:
        """Tokenization for BM25."""
        tokens = re.findall(r"\w+", text.lower())
        stopwords = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "from",
            "as",
            "is",
            "was",
            "are",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "should",
            "could",
            "may",
            "might",
            "must",
            "can",
            "this",
            "that",
            "these",
            "those",
            "it",
            "its",
        }
        return [token for token in tokens if token not in stopwords and len(token) > 1]

    def _rank_snippets(
        self, query: str, snippets: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Rank snippets with BM25."""

        try:
            # snippet metadata
            corpus_texts = [
                f"{s['name']} {s['signature']} {s['docstring']}" for s in snippets
            ]

            tokenized_corpus = [self._tokenize(doc) for doc in corpus_texts]

            # k1: term frequency saturation (default: 1.5)
            # b: document length normalization (default: 0.75)
            bm25 = BM25Okapi(tokenized_corpus, k1=1.5, b=0.75)
            tokenized_query = self._tokenize(query)

            # bm25 scores for each snippet
            scores = bm25.get_scores(tokenized_query)

            # get top snippets
            ranked_indices = scores.argsort()[::-1]
            top_snippets = [
                snippets[i]
                for i in ranked_indices[: self.max_snippets]
                if i < len(snippets)
            ]

            # normalize scores to [0, 1] range
            max_score = scores.max() if len(scores) > 0 and scores.max() > 0 else 1.0
            top_scores = [
                float(scores[i] / max_score)
                for i in ranked_indices[: self.max_snippets]
                if i < len(scores)
            ]

            return {"snippets": top_snippets, "relevance_scores": top_scores}

        except Exception as e:
            log(
                f"Warning: BM25 ranking failed: {e}, returning first {self.max_snippets} snippets"
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
        """Checks code structure of changed files."""

        info = {"class_hierarchy": {}, "method_signatures": {}}

        for file_path in changed_files:
            self._get_structural_from_file(file_path, info)

        return info

    def _get_structural_from_file(self, file_path: str, info: dict[str, Any]) -> None:
        """Analyze a single file and update structural info."""
        full_path = self.repo_path / file_path

        result = ASTUtils.parse_file(full_path)
        if not result:
            return

        tree, _ = result

        for cls in ASTUtils.get_classes(tree):
            self._get_class_info(cls, info)

    def _get_class_info(self, node: ast.ClassDef, info: dict[str, Any]) -> None:
        """Get hierarchy and method data."""

        info["class_hierarchy"][node.name] = {
            "bases": ASTUtils.get_base_classes(node),
            "methods": [],
        }

        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                sig = self._get_signature(item)

                info["class_hierarchy"][node.name]["methods"].append(sig["name"])

                method_key = f"{node.name}.{sig['name']}"
                info["method_signatures"][method_key] = sig

    def _get_signature(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> dict[str, Any]:
        """Get function details."""

        return {
            "name": node.name,
            "params": ASTUtils.get_function_params(node),
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

        for file_path in bug.get("changed_source_files", [])[:3]:  # limit to 3 files
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


class TestMetadataExtractor:
    """Extract test function names, docstrings, and assertions from test files."""

    def __init__(self, repo_path: str | Path, level: str = "assertions"):
        self.repo_path = Path(repo_path)
        self.level = level  # "none", "names", "docstrings", "assertions"

    def extract_metadata(self, test_files: list[str]) -> dict[str, Any]:
        """Extract metadata from test files."""
        if self.level == "none":
            return {"test_functions": [], "level": "none"}

        test_functions = []
        for file_path in test_files:
            functions = self._extract_from_file(file_path)
            test_functions.extend(functions)

        return {"test_functions": test_functions, "level": self.level}

    def _extract_from_file(self, file_path: str) -> list[dict[str, Any]]:
        """Extract test function metadata from a single file."""
        full_path = self.repo_path / file_path

        result = ASTUtils.parse_file(full_path)
        if not result:
            return []

        tree, lines = result
        functions = []

        for node in ASTUtils.get_functions(tree, exclude_class_methods=False):
            if not node.name.startswith("test_"):
                continue

            func_data = {
                "file": file_path,
                "name": node.name,
                "line": node.lineno,
            }

            if self.level in ("docstrings", "assertions"):
                docstring = ast.get_docstring(node) or ""
                func_data["docstring"] = docstring

            if self.level == "assertions":
                assertions = self._extract_assertions(node, lines)
                func_data["assertions"] = assertions

            functions.append(func_data)

        return functions

    def _extract_assertions(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, lines: list[str]
    ) -> list[str]:
        """Extract assertion statements from a test function."""
        assertions = []

        for child in ast.walk(node):
            if isinstance(child, ast.Assert):
                try:
                    if hasattr(child, "lineno") and child.lineno <= len(lines):
                        line = lines[child.lineno - 1].strip()
                        if line.startswith("assert"):
                            assertions.append(line[:150])
                except Exception:
                    pass

            # unittest-style assertions
            elif isinstance(child, ast.Call):
                if isinstance(child.func, ast.Attribute):
                    attr_name = child.func.attr
                    if attr_name.startswith("assert") or attr_name in (
                        "assertEqual",
                        "assertNotEqual",
                        "assertTrue",
                        "assertFalse",
                        "assertIs",
                        "assertIsNot",
                        "assertIsNone",
                        "assertIsNotNone",
                        "assertIn",
                        "assertNotIn",
                        "assertRaises",
                    ):
                        try:
                            if hasattr(child, "lineno") and child.lineno <= len(lines):
                                line = lines[child.lineno - 1].strip()
                                assertions.append(line[:150])
                        except Exception:
                            pass

        # no duplicates, max 10 assertions
        seen = set()
        unique_assertions = []
        for assertion in assertions:
            if assertion not in seen:
                seen.add(assertion)
                unique_assertions.append(assertion)
                if len(unique_assertions) >= 10:
                    break

        return unique_assertions


class ContextFormatter:
    """Turns the gathered info into LLM-friendly, formatted text."""

    def __init__(self, debug: bool = True):
        self.debug = debug

    @staticmethod
    def extract_metadata(context: dict[str, Any]) -> dict[str, Any]:
        """Extract context metadata counts for CSV logging."""
        return {
            "context_classes_count": len(context.get("aag", {}).get("classes", {})),
            "context_functions_count": len(context.get("aag", {}).get("functions", {})),
            "context_snippets_count": len(context.get("rag", {}).get("snippets", [])),
            "context_structural_classes_count": len(
                context.get("structural", {}).get("class_hierarchy", {})
            ),
            "context_recent_changes_count": len(
                context.get("historical", {}).get("recent_changes", [])
            ),
            "context_related_commits_count": len(
                context.get("historical", {}).get("related_commits", [])
            ),
            "context_test_functions_count": len(
                context.get("test_metadata", {}).get("test_functions", [])
            ),
        }

    def format(self, context: dict[str, Any]) -> str:
        """Collect and format text from all methods."""

        if self.debug:
            self._log_debug_info(context)

        sections = []
        sections.append(self._format_aag(context.get("aag", {})))
        sections.append(self._format_rag(context.get("rag", {})))
        sections.append(self._format_structural(context.get("structural", {})))
        sections.append(self._format_historical(context.get("historical", {})))
        sections.append(self._format_test_metadata(context.get("test_metadata", {})))
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
        test_metadata = context.get("test_metadata", {})
        log(
            f"Test functions: {len(test_metadata.get('test_functions', []))} (level: {test_metadata.get('level', 'none')})"
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
                bases_str = ", ".join(info.get("bases", [])) or "object"
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

    def _format_test_metadata(self, test_metadata: dict[str, Any]) -> str:
        """Format the test requirements section."""
        test_functions = test_metadata.get("test_functions", [])
        level = test_metadata.get("level", "none")

        if not test_functions or level == "none":
            return ""

        output = ["\n**TEST REQUIREMENTS:**"]

        # group test functions
        tests_by_file: dict[str, list[dict[str, Any]]] = {}
        for func in test_functions:
            file_path = func.get("file", "unknown")
            if file_path not in tests_by_file:
                tests_by_file[file_path] = []
            tests_by_file[file_path].append(func)

        for file_path, functions in tests_by_file.items():
            output.append(f"\nFile: {file_path}")

            for func in functions[:10]:  # max 10 func per file
                func_name = func.get("name", "unknown")
                output.append(f"  {func_name}():")

                if level in ("docstrings", "assertions"):
                    docstring = func.get("docstring", "")
                    if docstring:
                        doc_preview = docstring[:200].replace("\n", " ")
                        if len(docstring) > 200:
                            doc_preview += "..."
                        output.append(f'    "{doc_preview}"')

                if level == "assertions":
                    assertions = func.get("assertions", [])
                    if assertions:
                        output.append("    Assertions:")
                        for assertion in assertions[:10]:  # max 10 assertions
                            output.append(f"      - {assertion}")

        return "\n".join(output)
