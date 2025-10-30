import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
from pathlib import Path
from typing import Any
import threading

from .project_handler import ProjectHandler
from .analysis import analyze_files
from .logger import log
from .results_logger import ResultsLogger
from .debug_helper import DebugHelper
from .patch_evaluator import PatchEvaluator


class AnalysisPipeline:
    """Coordinates AI vs human fix analysis across multiple repos."""

    def __init__(
        self,
        config: dict[str, Any],
        project_root: Path,
        skip_llm_fix: bool = False,
        debug_on_failure: bool = False,
        llm_provider: str = "gemini",
        llm_model: str = "gemini-2.5-flash",
    ):
        """Set up pipeline with config and LLM settings."""
        self.config = config
        self.project_root = Path(project_root)
        self.skip_llm_fix = skip_llm_fix
        self.debug_on_failure = debug_on_failure
        self.llm_provider = llm_provider
        self.llm_model = llm_model

        self.test_command = config.get("test_command", "pytest")

        results_path = self.project_root / "results" / "results.csv"
        self.results_logger = ResultsLogger(results_path)
        self.debug_helper = DebugHelper(self.project_root)

        self.context_cache_dir = project_root / "results" / "context_cache"
        self.context_cache_dir.mkdir(parents=True, exist_ok=True)

        self.patch_cache_dir = project_root / "results" / "patches"
        self.patch_cache_dir.mkdir(parents=True, exist_ok=True)

        self.patch_evaluator = PatchEvaluator(
            test_command=self.test_command,
            config=self.config,
            debug_helper=self.debug_helper,
            project_root=self.project_root,
            context_cache_dir=self.context_cache_dir,
            patch_cache_dir=self.patch_cache_dir,
        )

    @classmethod
    def from_config_files(
        cls,
        config_path: Path,
        skip_llm_fix: bool = False,
        debug_on_failure: bool = False,
        llm_provider: str = "gemini",
        llm_model: str = "gemini-2.5-flash",
    ) -> "AnalysisPipeline":
        """Load pipeline from config.json."""
        config_path = Path(config_path)
        project_root = config_path.parent

        try:
            config = json.loads(config_path.read_text())
        except FileNotFoundError as e:
            log(f"ERROR: {e.filename} not found.")
            raise

        return cls(
            config=config,
            project_root=project_root,
            skip_llm_fix=skip_llm_fix,
            debug_on_failure=debug_on_failure,
            llm_provider=llm_provider,
            llm_model=llm_model,
        )

    def run_corpus(
        self,
        corpus: list[dict[str, Any]],
        resume_event: threading.Event | None = None,
        stop_event: threading.Event | None = None,
    ):
        """Run analysis on entire corpus (grouped by repo)."""
        if resume_event is None:
            resume_event = threading.Event()
            resume_event.set()
        if stop_event is None:
            stop_event = threading.Event()

        bugs_by_repo = self._group_by_repo(corpus)

        for repo_name, bugs in bugs_by_repo.items():
            if stop_event.is_set():
                log("--> Stopped.")
                break

            self._process_repository(repo_name, bugs, resume_event, stop_event)

    def run_single_bug(
        self,
        bug_data: dict[str, Any],
        resume_event: threading.Event | None = None,
        stop_event: threading.Event | None = None,
    ):
        """Run analysis for single commit."""
        log("--- Running analysis for single commit ---")
        self.run_corpus([bug_data], resume_event, stop_event)

    def _group_by_repo(self, corpus: list[dict[str, Any]]) -> dict[str, list]:
        """Group bugs by repository name."""
        grouped: dict[str, list] = {}
        for bug in corpus:
            repo = bug["repo_name"]
            if repo not in grouped:
                grouped[repo] = []
            grouped[repo].append(bug)
        return grouped

    def _process_repository(
        self,
        repo_name: str,
        bugs: list[dict[str, Any]],
        resume_event: threading.Event,
        stop_event: threading.Event,
    ):
        """Process all bugs in a repo (setup once, analyze many)."""
        log(f"\n{'='*60}")
        log(f"Repository: {repo_name}")
        log(f"{'='*60}")

        handler = ProjectHandler(repo_name)
        try:
            handler.setup()
            if not handler.setup_virtual_environment():
                log(f"  --> CRITICAL: venv setup failed - skipping repo")
                return

            for bug in bugs:
                if not resume_event.is_set():
                    log("--> Paused - waiting...")
                    resume_event.wait()
                    log("--> Resumed.")

                if stop_event.is_set():
                    log("--> Stopped.")
                    break

                self._process_bug(bug, handler)

        except Exception as e:
            log(f"  FATAL ERROR in {repo_name}: {e}")
        finally:
            handler.cleanup()

    def _process_bug(
        self,
        bug: dict[str, Any],
        handler: ProjectHandler,
    ):
        """Analyze single bug commit - before/after complexity, AI vs human fix."""
        fix_sha = bug["bug_commit_sha"]
        parent_sha = bug["parent_commit_sha"]

        log(f"\n{'─'*60}")
        log(f"Commit: {fix_sha[:7]}")
        log(f"{'─'*60}")

        try:
            results = {**bug}

            changed = handler.get_changed_files(fix_sha)
            if not changed:
                log("  --> Skipping: No Python files changed.")
                return

            before = self._analyze_before(handler, parent_sha, changed)
            results["comp_before"] = before

            # AI fix
            if not self.skip_llm_fix:
                ai = self.patch_evaluator.evaluate_ai_fix(
                    bug,
                    handler,
                    parent_sha,
                    changed,
                    self.debug_on_failure,
                    llm_provider=self.llm_provider,
                    llm_model=self.llm_model,
                )
                results["ai_results"] = ai
            else:
                log("  --> Skipping AI fix as requested.")
                results["ai_results"] = self._skipped_results()

            # human fix
            human = self.patch_evaluator.evaluate_human_fix(
                handler,
                fix_sha,
                changed,
                bug,
            )
            results["human_results"] = human

            self._log_final_comparison(results)
            self.results_logger.log(results)

        except Exception as e:
            log(f"  FATAL ERROR in {fix_sha[:7]}: {e}")

    def _analyze_before(
        self,
        handler: ProjectHandler,
        parent_sha: str,
        changed_files: list,
    ) -> dict[str, Any]:
        """Measure complexity before the fix."""
        log("  Analyzing 'before' state...")
        handler.checkout(parent_sha)

        repo_path = Path(handler.repo_path)
        existing = [f for f in changed_files if (repo_path / f).exists()]

        complexity = analyze_files(str(handler.repo_path), existing)

        log(
            f"    --> Before: CC={complexity.get('total_cc')}, "
            f"Cognitive={complexity.get('total_cognitive')}, "
            f"Avg Params={complexity.get('avg_params')}, "
            f"Total Tokens={complexity.get('total_tokens')}"
        )

        return complexity

    def _skipped_results(self) -> dict[str, Any]:
        """Result dict when AI fix is skipped."""
        return {
            "applied_ok": "SKIPPED",
            "tests_passed": "SKIPPED",
            "complexity": {
                "total_cc": "SKIPPED",
                "total_cognitive": "SKIPPED",
                "avg_params": "SKIPPED",
                "total_tokens": "SKIPPED",
            },
            "patch_stats": {
                "lines_added": 0,
                "lines_deleted": 0,
                "total": 0,
            },
            "llm_metadata": {
                "provider": "SKIPPED",
                "model": "SKIPPED",
                "prompt_tokens": "SKIPPED",
                "completion_tokens": "SKIPPED",
                "thinking_tokens": "SKIPPED",
                "total_tokens": "SKIPPED",
            },
        }

    def _log_final_comparison(self, results: dict[str, Any]):
        """Log AI vs human complexity comparison."""
        ai = results.get("ai_results", {}).get("complexity", {})
        human = results.get("human_results", {}).get("complexity", {})

        log(
            f"    --> AI: CC={ai.get('total_cc')}, "
            f"Cognitive={ai.get('total_cognitive')}, "
            f"Avg Params={ai.get('avg_params')}, "
            f"Total Tokens={ai.get('total_tokens')}"
        )
        log(
            f"    --> Human: CC={human.get('total_cc')}, "
            f"Cognitive={human.get('total_cognitive')}, "
            f"Avg Params={human.get('avg_params')}, "
            f"Total Tokens={human.get('total_tokens')}"
        )
