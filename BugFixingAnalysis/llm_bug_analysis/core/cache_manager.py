import json
import shutil
from pathlib import Path
from typing import Any
from .logger import log


class CacheManager:
    """Manages loading and saving of JSON cache files."""

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.cache_root = self.project_root / ".cache"

    def get_entity_path(
        self,
        subdir: str,
        repo_name: str,
        commit_sha: str,
        suffix: str = "",
    ) -> Path:
        """Get path for bug cache files."""
        safe_repo = repo_name.replace("/", "_").replace("\\", "_")
        cache_subdir = self.cache_root / subdir / safe_repo
        cache_subdir.mkdir(parents=True, exist_ok=True)
        return cache_subdir / f"{commit_sha[:12]}{suffix}.json"

    def load_entity_cache(
        self,
        subdir: str,
        repo_name: str,
        commit_sha: str,
        suffix: str = "",
        required_keys: set[str] | None = None,
    ) -> dict[str, Any] | None:
        """Load cached context or llm response for a bug."""
        cache_path = self.get_entity_path(subdir, repo_name, commit_sha, suffix)
        if not cache_path.exists():
            return None

        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            if required_keys and not all(key in cached for key in required_keys):
                log(f"  --> Cache invalid (missing keys), will rebuild")
                return None
            return cached

        except Exception as e:
            log(f"  --> ERROR loading cache: {e}")
            return None

    def save_entity_cache(
        self,
        subdir: str,
        repo_name: str,
        commit_sha: str,
        data: dict[str, Any],
        suffix: str = "",
    ) -> bool:
        """Save entity cache for a bug."""
        cache_path = self.get_entity_path(subdir, repo_name, commit_sha, suffix)

        try:
            cache_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            log(f"  --> Saved to cache: {cache_path.name}")
            return True

        except Exception as e:
            log(f"  --> ERROR saving cache: {e}")
            return False

    def clear_entity_caches(self, subdirs: list[str] | None = None) -> list[str]:
        """Clear specific cache directories."""
        if subdirs is None:
            subdirs = ["contexts", "llm_responses"]

        cleared = []
        for subdir in subdirs:
            cache_subdir = self.cache_root / subdir
            if cache_subdir.exists():
                shutil.rmtree(cache_subdir)
                cache_subdir.mkdir(parents=True)
                cleared.append(subdir)
        return cleared

    def _load_corpus(self) -> list[dict[str, Any]]:
        """Load corpus.json from project root."""
        corpus_path = self.project_root / "corpus.json"
        if not corpus_path.exists():
            log("ERROR: corpus.json not found")
            return []
        try:
            return json.loads(corpus_path.read_text())
        except Exception as e:
            log(f"ERROR: Failed to load corpus.json: {e}")
            return []

    def load_all_contexts(
        self,
        corpus: list[dict[str, Any]] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Load all cached contexts for bugs in corpus."""
        from .context_builder import ContextFormatter

        if corpus is None:
            corpus = self._load_corpus()
            if not corpus:
                return {}

        contexts = {}
        formatter = ContextFormatter(debug=False)

        for bug in corpus:
            repo_name = bug.get("repo_name", "")
            bug_sha = bug.get("bug_commit_sha", "")
            bug_key = f"{repo_name.replace('/', '_')}_{bug_sha[:12]}"
            cached = self.load_entity_cache(
                "contexts",
                repo_name,
                bug_sha,
                required_keys={"aag", "rag", "structural", "historical"},
            )

            if cached:
                formatted_context = formatter.format(cached)
                context_metadata = ContextFormatter.extract_metadata(cached)
                contexts[bug_key] = {
                    "bug": bug,
                    "formatted_context": formatted_context,
                    "changed_source_files": bug.get("changed_source_files", []),
                    "changed_test_files": bug.get("changed_test_files", []),
                    "context_metadata": context_metadata,
                }

        return contexts

    def load_all_patches(
        self,
        provider: str,
        model: str,
        corpus: list[dict[str, Any]] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Load all cached LLM responses (patches) for bugs in corpus."""
        if corpus is None:
            corpus = self._load_corpus()
            if not corpus:
                return {}

        patches = {}
        suffix = f"_{provider}_{model}"

        for bug in corpus:
            repo_name = bug.get("repo_name", "")
            bug_sha = bug.get("bug_commit_sha", "")
            bug_key = f"{repo_name.replace('/', '_')}_{bug_sha[:12]}"

            llm_result = self.load_entity_cache(
                "llm_responses",
                repo_name,
                bug_sha,
                suffix=suffix,
                required_keys={"intent", "provider", "model"},
            )

            if llm_result:
                patches[bug_key] = {
                    "bug": bug,
                    "llm_result": llm_result,
                    "changed_source_files": bug.get("changed_source_files", []),
                    "changed_test_files": bug.get("changed_test_files", []),
                    "context_metadata": {},
                }

        return patches

    def has_cached_contexts(self) -> bool:
        """Check if there are any cached contexts."""
        contexts_dir = self.cache_root / "contexts"
        if not contexts_dir.exists():
            return False
        return any(contexts_dir.rglob("*.json"))

    def has_cached_patches(self, provider: str, model: str) -> bool:
        """Check if there are any cached LLM responses for given provider/model."""
        responses_dir = self.cache_root / "llm_responses"
        if not responses_dir.exists():
            return False
        suffix = f"_{provider}_{model}.json"
        return any(responses_dir.rglob(f"*{suffix}"))
