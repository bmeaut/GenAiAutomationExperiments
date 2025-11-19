import json
from pathlib import Path
from typing import Any, Callable, Tuple, Literal
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
from contextlib import contextmanager

from .project_handler import ProjectHandler
from .analysis import analyze_files
from .logger import log
from .results_logger import ResultsLogger
from .debug_helper import DebugHelper
from .patch_evaluator import PatchEvaluator
from .context_builder import ContextBuilder
from .terminal_manager import TerminalManager
from .cache_manager import CacheManager

ProgressCallback = Callable[[int, int, str], None]
ControlStatus = Literal["continue", "paused", "stopped"]


class PipelineController:
    """Pause/resume/stop logic for pipeline operations."""

    @staticmethod
    def check_pause_and_stop(
        resume_event: threading.Event | None,
        stop_event: threading.Event | None,
        pause_msg: str = "Paused - waiting...",
        resume_msg: str = "Resumed",
        stop_msg: str | None = None,
    ) -> Tuple[ControlStatus, str | None]:

        # paused
        if resume_event and not resume_event.is_set():
            log(pause_msg)
            while not resume_event.is_set():
                resume_event.wait(timeout=0.5)
                if stop_event and stop_event.is_set():
                    break

            # stopped while paused
            if stop_event and stop_event.is_set():
                if stop_msg:
                    log(stop_msg)
                return ("stopped", stop_msg)

            log(resume_msg)
            return ("paused", None)

        # stopped
        if stop_event and stop_event.is_set():
            if stop_msg:
                log(stop_msg)
            return ("stopped", stop_msg)

        return ("continue", None)


class AnalysisPipeline:
    """Coordinates AI vs human fix analysis across multiple repos."""

    def __init__(
        self,
        config: dict[str, Any],
        project_root: Path,
        skip_llm_fix: bool = False,
        debug_on_failure: bool = False,
        llm_provider: str = "gemini",
        llm_model: str = "gemini-3-pro-preview",
        show_terminals: bool = True,
    ):
        """Set up pipeline with config and LLM settings."""

        self.config = config
        self.project_root = Path(project_root)
        self.skip_llm_fix = skip_llm_fix
        self.debug_on_failure = debug_on_failure
        self.llm_provider = llm_provider
        self.llm_model = llm_model

        self.terminal_manager = (
            TerminalManager(project_root) if show_terminals else None
        )

        self.test_command = config.get("test_command", "pytest")

        self.max_parallel_llm = config.get("max_parallel_llm", 5)

        results_path = self.project_root / "results" / "results.csv"
        self.results_logger = ResultsLogger(results_path)
        self.debug_helper = DebugHelper(self.project_root)

        self.cache_manager = CacheManager(self.project_root)

        self.patch_evaluator = PatchEvaluator(
            test_command=self.test_command,
            config=self.config,
            debug_helper=self.debug_helper,
            project_root=self.project_root,
            cache_manager=self.cache_manager,
        )

    @contextmanager
    def _terminal_context(self, title: str):
        """Context manager for terminal lifecycle."""
        started_here = False

        if self.terminal_manager and not self.terminal_manager.persistent_mode:
            self.terminal_manager.start_persistent_terminal(title=title)
            started_here = True

        try:
            yield
        finally:
            if started_here and self.terminal_manager:
                self.terminal_manager.stop_persistent_terminal()

    def _extract_formatted_context(self, cached_context: dict[str, Any]) -> str:
        """Extract formatted text from cached context."""
        from .context_builder import ContextFormatter

        formatter = ContextFormatter(debug=False)
        return formatter.format(cached_context)

    def _group_by_repo(self, corpus: list[dict[str, Any]]) -> dict[str, list]:
        """Group bugs by repository name."""
        grouped: dict[str, list] = {}
        for bug in corpus:
            repo = bug["repo_name"]
            if repo not in grouped:
                grouped[repo] = []
            grouped[repo].append(bug)
        return grouped

    def run_stage_1_build_contexts(
        self,
        corpus: list[dict[str, Any]],
        stop_event: threading.Event | None = None,
        resume_event: threading.Event | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Build contexts for all bugs."""
        log("\n" + "=" * 60)
        log("STAGE 1: Building contexts...")
        log("=" * 60)

        with self._terminal_context("Stage 1: Building Contexts"):
            if stop_event is None:
                stop_event = threading.Event()

            bugs_by_repo = self._group_by_repo(corpus)
            total_bugs = len(corpus)
            processed_bugs = 0

            all_contexts = {}

            for repo_idx, (repo_name, bugs) in enumerate(bugs_by_repo.items(), 1):
                status, _ = PipelineController.check_pause_and_stop(
                    resume_event,
                    stop_event,
                    pause_msg="Stage 1 paused - waiting...",
                    resume_msg="Stage 1 resumed",
                    stop_msg="\nWARNING: Stage 1 stopped.",
                )
                if status == "stopped":
                    break

                log(
                    f"\n[Repo {repo_idx}/{len(bugs_by_repo)}] {repo_name} ({len(bugs)} bugs)"
                )

                try:
                    repo_contexts = self._build_contexts_for_repo(
                        repo_name,
                        bugs,
                        stop_event,
                        resume_event,
                        lambda curr, total, msg: (
                            progress_callback(processed_bugs + curr, total_bugs, msg)
                            if progress_callback
                            else None
                        ),
                    )

                    all_contexts.update(repo_contexts)
                    processed_bugs += len(bugs)

                except Exception as e:
                    log(f"ERROR: in processing {repo_name}: {e}")
                    processed_bugs += len(bugs)

            log(
                f"\nSUCCESS: Stage 1 complete: {len(all_contexts)}/{total_bugs} contexts built"
            )

            return all_contexts

    def _build_contexts_for_repo(
        self,
        repo_name: str,
        bugs: list[dict[str, Any]],
        stop_event: threading.Event,
        resume_event: threading.Event | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Build contexts for all bugs in one repo."""
        contexts = {}

        log(f"   Checking cache for {len(bugs)} bugs...")
        uncached_bugs = []

        for bug in bugs:
            bug_sha = bug.get("bug_commit_sha", "unknown")
            bug_key = f"{repo_name.replace('/', '_')}_{bug_sha[:12]}"

            cached = self.cache_manager.load_entity_cache(
                "contexts",
                repo_name,
                bug_sha,
                required_keys={"aag", "rag", "structural", "historical"},
            )

            if cached:
                formatted_context = self._extract_formatted_context(cached)
                changed_source_files = bug.get("changed_source_files", [])
                changed_test_files = bug.get("changed_test_files", [])
                if not changed_source_files:
                    log(f"    No Python source files changed (check corpus.json).")
                    continue

                # context metadata for csv logging
                from .context_builder import ContextFormatter

                context_metadata = ContextFormatter.extract_metadata(cached)
                contexts[bug_key] = {
                    "bug": bug,
                    "formatted_context": formatted_context,
                    "changed_source_files": changed_source_files,
                    "changed_test_files": changed_test_files,
                    "context_metadata": context_metadata,
                }
                log(f"    [{bug_sha[:7]}] loaded from cache.")

            else:
                uncached_bugs.append(bug)

        cache_hits = len(bugs) - len(uncached_bugs)
        log(f"  Cache: {cache_hits}/{len(bugs)} hits ({cache_hits/len(bugs)*100:.0f}%)")

        if not uncached_bugs:
            log(f"  All contexts cached - skipping clone!")
            return contexts

        with self._terminal_context(f"Building Context: {repo_name}"):
            log(f"  Cloning {repo_name} for {len(uncached_bugs)} uncached bugs...")

            handler = ProjectHandler(repo_name, self.terminal_manager)

            try:
                log(f"  Cloning {repo_name}...")
                handler.setup()
                log(f"  Cloned to {handler.repo_path}")

                total = len(uncached_bugs)
                for i, bug in enumerate(uncached_bugs, 1):
                    status, _ = PipelineController.check_pause_and_stop(
                        resume_event,
                        stop_event,
                        pause_msg="  Bug processing paused - waiting...",
                        resume_msg="  Bug processing resumed",
                    )
                    if status == "stopped":
                        break

                    bug_sha = bug.get("bug_commit_sha", "unknown")
                    parent_sha = bug.get("parent_commit_sha", "unknown")
                    bug_key = f"{repo_name.replace('/', '_')}_{bug_sha[:12]}"

                    if progress_callback:
                        progress_callback(i, total, f"Building context: {bug_key}")

                    log(f"  [{i}/{total}] {bug_sha[:7]}")
                    # TODO: repeated code, remove
                    try:
                        changed_source_files = bug.get("changed_source_files", [])
                        changed_test_files = bug.get("changed_test_files", [])
                        if not changed_source_files:
                            log(
                                f"    No Python source files changed (check corpus.json)."
                            )
                            continue

                        handler.checkout(parent_sha)

                        builder = ContextBuilder(
                            repo_path=handler.repo_path,
                            max_snippets=5,
                            debug=True,
                            cache_manager=self.cache_manager,
                            test_context_level=self.config.get(
                                "test_context_level", "assertions"
                            ),
                            oracle_level=self.config.get("oracle_level", "none"),
                        )

                        context, context_text = builder.build_and_format(bug)
                        from .context_builder import ContextFormatter

                        context_metadata = ContextFormatter.extract_metadata(context)
                        contexts[bug_key] = {
                            "bug": bug,
                            "formatted_context": context_text,
                            "changed_source_files": changed_source_files,
                            "changed_test_files": changed_test_files,
                            "context_metadata": context_metadata,
                        }

                        log(f"    Context built ({len(context_text)} chars)")

                    except Exception as e:
                        log(f"    FAIL: {e}")

            finally:
                handler.cleanup()

        return contexts

    def run_stage_2_generate_patches(
        self,
        contexts: dict[str, dict[str, Any]] | None = None,
        mode: str = "parallel",  # "sequential" or "parallel"
        stop_event: threading.Event | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Generate patches from contexts via LLM."""
        log("\n" + "=" * 60)
        log(f"STAGE 2: Generating patches ({mode.upper()})")
        log("=" * 60)

        if self.skip_llm_fix:
            log("WARNING: Skipping LLM generation...")
            return {}

        if stop_event is None:
            stop_event = threading.Event()

        if contexts is None:
            contexts = self.cache_manager.load_all_contexts()
            if not contexts:
                log("No cached contexts found. Run Stage 1 first.")
                return {}
            log(f"Loaded {len(contexts)} contexts from cache")

        else:
            if not isinstance(contexts, dict):
                log("ERROR: Invalid contexts format")
                return {}

        if mode == "sequential":
            patches = self._generate_patches_sequential(
                contexts, stop_event, progress_callback
            )
        elif mode == "parallel":
            patches = self._generate_patches_parallel(
                contexts, stop_event, progress_callback
            )
        else:
            log(f"ERROR: Unknown mode '{mode}'. Use 'sequential' or 'parallel'.")
            return {}

        log(
            f"\nSUCCESS: Stage 2 complete: {len(patches)}/{len(contexts)} patches generated"
        )

        return patches

    def _generate_patches_sequential(
        self,
        contexts: dict[str, dict[str, Any]],
        stop_event: threading.Event,
        progress_callback: ProgressCallback | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Generate patches one by one."""
        patches = {}
        total = len(contexts)

        for i, (bug_key, context_data) in enumerate(contexts.items(), 1):
            if stop_event.is_set():
                log("\nWARNING:  Stage 2 stopped by user")
                break

            if progress_callback:
                progress_callback(i, total, f"Generating patch: {bug_key}")

            log(f"  [{i}/{total}] {bug_key}")

            try:
                result = self._generate_single_patch(bug_key, context_data)
                patches[bug_key] = result
                log(f"    Patch generated")

            except Exception as e:
                log(f"    FAILED: {e}")
                patches[bug_key] = {
                    "bug": context_data.get("bug"),
                    "error": str(e),
                    "llm_result": None,
                }

        return patches

    def _generate_patches_parallel(
        self,
        contexts: dict[str, dict[str, Any]],
        stop_event: threading.Event,
        progress_callback: ProgressCallback | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Generate patches in parallel."""
        patches = {}
        total = len(contexts)
        completed = 0

        log(f"Using {self.max_parallel_llm} parallel workers")

        with ThreadPoolExecutor(max_workers=self.max_parallel_llm) as executor:
            futures = {
                executor.submit(
                    self._generate_single_patch, bug_key, context_data
                ): bug_key
                for bug_key, context_data in contexts.items()
                if not stop_event.is_set()
            }

            for future in as_completed(futures):
                if stop_event.is_set():
                    log("\nWARNING:  Stage 2 stopped by user")
                    break

                bug_key = futures[future]
                completed += 1

                if progress_callback:
                    progress_callback(completed, total, f"Generated: {bug_key}")

                try:
                    result = future.result()
                    patches[bug_key] = result
                    log(f"  [{completed}/{total}] - {bug_key}")

                except Exception as e:
                    log(f"  [{completed}/{total}] FAILED: {bug_key}: {e}")
                    context_data = contexts.get(bug_key, {})
                    patches[bug_key] = {
                        "bug": context_data.get("bug"),
                        "error": str(e),
                        "llm_result": None,
                    }

        return patches

    def _generate_single_patch(
        self,
        bug_key: str,
        context_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate a single patch from pre-built context."""
        bug = context_data["bug"]
        changed_source_files = context_data.get("changed_source_files", [])
        changed_test_files = context_data.get("changed_test_files", [])
        context_metadata = context_data.get("context_metadata", {})

        if self.skip_llm_fix:
            log(f"  Skipping LLM generation for {bug_key} (skip_llm_fix=True)")
            return {
                "bug": bug,
                "llm_result": None,
                "changed_source_files": changed_source_files,
                "changed_test_files": changed_test_files,
                "context_metadata": context_metadata,
                "skipped": True,
            }

        formatted_context = context_data["formatted_context"]

        llm_result = self.patch_evaluator.llm_manager.generate_fix(
            bug=bug,
            context_text=formatted_context,
            provider=self.llm_provider,
            model=self.llm_model,
        )

        return {
            "bug": bug,
            "llm_result": llm_result,
            "changed_source_files": changed_source_files,
            "changed_test_files": changed_test_files,
            "context_metadata": context_metadata,
        }

    def run_stage_3_test_patches(
        self,
        patches: dict[str, dict[str, Any]] | None = None,
        resume_event: threading.Event | None = None,
        stop_event: threading.Event | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        """Test all patches."""
        log("\n" + "=" * 60)
        log("STAGE 3: Testing patches...")
        log("=" * 60)

        with self._terminal_context("Stage 3: Testing Patches"):
            if resume_event is None:
                resume_event = threading.Event()
                resume_event.set()
            if stop_event is None:
                stop_event = threading.Event()

            # load patches if not provided
            if patches is None:

                if self.skip_llm_fix:
                    log("Skip mode: Loading contexts from cache...")
                    contexts = self.cache_manager.load_all_contexts()
                    if not contexts:
                        log("No cached contexts found. Run Stage 1 first.")
                        return

                    patches = {
                        bug_key: {
                            "bug": ctx_data["bug"],
                            "llm_result": None,
                            "changed_source_files": ctx_data.get(
                                "changed_source_files", []
                            ),
                            "changed_test_files": ctx_data.get(
                                "changed_test_files", []
                            ),
                            "context_metadata": ctx_data.get("context_metadata", {}),
                            "skipped": True,
                        }
                        for bug_key, ctx_data in contexts.items()
                    }
                    log(f"Loaded {len(patches)} bugs from contexts (skip mode)")

                else:
                    patches = self.cache_manager.load_all_patches(
                        self.llm_provider, self.llm_model
                    )
                    if not patches:
                        log("ERROR: No cached patches found. Run Stage 2 first.")
                        return
                    log(f"Loaded {len(patches)} patches from cache")

            else:
                if not isinstance(patches, dict):
                    log("ERROR: Invalid patches format")
                    return

            patches_by_repo = self._group_patches_by_repo(patches)

            total_repos = len(patches_by_repo)
            total_patches = len(patches)
            processed_patches = 0

            for repo_idx, (repo_name, repo_patches) in enumerate(
                patches_by_repo.items(), 1
            ):
                status, _ = PipelineController.check_pause_and_stop(
                    resume_event,
                    stop_event,
                    pause_msg="Stage 3 paused - waiting...",
                    resume_msg="Stage 3 resumed",
                    stop_msg="\nWARNING: Stage 3 stopped.",
                )
                if status == "stopped":
                    break

                log(
                    f"\n[Repo {repo_idx}/{total_repos}] {repo_name} ({len(repo_patches)} patches)"
                )

                try:
                    self._test_patches_for_repo(
                        repo_name,
                        repo_patches,
                        resume_event,
                        stop_event,
                        lambda curr, total, msg: (
                            progress_callback(
                                processed_patches + curr, total_patches, msg
                            )
                            if progress_callback
                            else None
                        ),
                    )
                    processed_patches += len(repo_patches)

                except Exception as e:
                    log(f"ERROR: {e}")
                    processed_patches += len(repo_patches)

            log(f"\nSUCCESS: Stage 3 complete: {processed_patches} patches tested")

    def _group_patches_by_repo(
        self,
        patches: dict[str, dict[str, Any]],
    ) -> dict[str, list[dict[str, Any]]]:
        """Group patches by repository name."""
        grouped = defaultdict(list)

        for bug_key, patch_data in patches.items():
            bug = patch_data.get("bug")
            if not bug:
                continue

            repo_name = bug.get("repo_name", "unknown")
            grouped[repo_name].append(patch_data)

        return dict(grouped)

    def _test_patches_for_repo(
        self,
        repo_name: str,
        repo_patches: list[dict[str, Any]],
        resume_event: threading.Event,
        stop_event: threading.Event,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        """Test all patches for one repository."""

        untested_patches = [
            p
            for p in repo_patches
            if not self.results_logger.entry_exists(
                repo_name, p.get("bug", {}).get("bug_commit_sha", "")
            )
        ]

        if not untested_patches:
            log(f"  All {len(repo_patches)} patches already tested - skipping repo")
            return

        log(f"  {len(untested_patches)}/{len(repo_patches)} patches need testing")
        repo_patches = untested_patches

        if progress_callback:
            progress_callback(0, len(repo_patches), f"Cloning {repo_name}...")

        handler = ProjectHandler(repo_name, self.terminal_manager)

        try:
            log(f"  Cloning {repo_name}...")
            handler.setup()

            total = len(repo_patches)
            prev_commit_sha = None
            for i, patch_data in enumerate(repo_patches, 1):
                status, _ = PipelineController.check_pause_and_stop(
                    resume_event,
                    stop_event,
                    pause_msg="Paused - waiting...",
                    resume_msg="Resumed",
                )
                if status == "stopped":
                    break

                bug = patch_data.get("bug")
                if not bug:
                    continue

                bug_sha = bug.get("bug_commit_sha", "unknown")
                parent_sha = bug.get("parent_commit_sha", "unknown")

                if progress_callback:
                    progress_callback(
                        i, total, f"Testing: {repo_name}_{bug_sha[:7]} [{i}/{total}]"
                    )

                log(f"\n  [{i}/{total}] {bug_sha[:7]}")

                log(f"  Checking out parent commit {parent_sha[:7]}...")
                handler.checkout(parent_sha)

                # setup venv if commit changed or first time
                if prev_commit_sha != parent_sha:
                    log(f"  Building virtual environment at {parent_sha[:7]}...")

                    if not handler.setup_virtual_environment():
                        log(f"  ERROR: venv setup failed at {parent_sha[:7]}")
                        log(f"  Skipping remaining patches for this commit")
                        # skip to next different commit
                        continue

                    env_setup_time = handler.venv.get_setup_time()
                    log(f"  Environment ready in {env_setup_time:.1f}s")

                    prev_commit_sha = parent_sha

                else:
                    log(f"  Using existing venv (same commit as previous)")

                self._test_single_patch(patch_data, handler)

        except Exception as e:
            log(f"ERROR: in {repo_name}: {e}")

        finally:
            handler.cleanup()

    def _test_single_patch(
        self,
        patch_data: dict[str, Any],
        handler: ProjectHandler,
    ) -> None:
        """Test a single pre-generated patch."""
        import time

        start_time = time.time()

        bug = patch_data["bug"]
        llm_result = patch_data.get("llm_result")
        changed_source_files = patch_data.get("changed_source_files", [])
        changed_test_files = patch_data.get("changed_test_files", [])
        context_metadata = patch_data.get("context_metadata", {})

        fix_sha = bug["bug_commit_sha"]
        parent_sha = bug["parent_commit_sha"]

        try:
            results = {**bug, **context_metadata}

            before = self._analyze_before(handler, changed_test_files)
            results["comp_before"] = before

            if self.skip_llm_fix:
                log(f"  Skipping AI fix (skip_llm_fix=True)")
                results["ai_results"] = self._skipped_results()
            elif llm_result and not patch_data.get("error"):
                ai = self.patch_evaluator.evaluate_ai_fix(
                    bug=bug,
                    handler=handler,
                    parent_sha=parent_sha,
                    changed_source_files=changed_source_files,
                    llm_fix=llm_result,
                )
                results["ai_results"] = ai
            else:
                log(f"ERROR: Skipping AI (generation failed)")
                results["ai_results"] = self._skipped_results()

            human = self.patch_evaluator.evaluate_human_fix(
                handler,
                fix_sha,
                changed_source_files,
                bug,
            )
            results["human_results"] = human
            total_test_time = time.time() - start_time
            results["env_setup_time_seconds"] = handler.venv.get_setup_time()
            results["total_test_time_seconds"] = total_test_time

            self._log_final_comparison(results)
            self.results_logger.log(results)

        except Exception as e:
            total_test_time = time.time() - start_time
            log(f"ERROR after {total_test_time:.1f}s: {e}")

    def run_full_pipeline(
        self,
        corpus: list[dict[str, Any]],
        threaded_mode: str = "parallel",
        resume_event: threading.Event | None = None,
        stop_event: threading.Event | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        """Run complete 3-stage pipeline"""
        log("\n" + "=" * 60)
        log(f"Starting 3-stage pipeline: {len(corpus)} bugs")
        log(f"   LLM Mode: {threaded_mode.upper()}")
        log("=" * 60)

        with self._terminal_context("LLM Bug Analysis Pipeline"):
            log("\nStage 1/3: Building contexts...")
            contexts = self.run_stage_1_build_contexts(
                corpus, stop_event, resume_event, progress_callback
            )
            if stop_event and stop_event.is_set():
                log("Pipeline stopped after Stage 1")
                return

            log("\nStage 2/3: Generating patches...")
            if self.skip_llm_fix:
                log("DRY RUN: Skipping patch generation")
                patches = None  # will load contexts in stage 3
            else:
                patches = self.run_stage_2_generate_patches(
                    contexts, threaded_mode, stop_event, progress_callback
                )
            if stop_event and stop_event.is_set():
                log("Pipeline stopped after Stage 2")
                return

            log("\nStage 3/3: Testing patches...")
            self.run_stage_3_test_patches(
                patches, resume_event, stop_event, progress_callback
            )

            log("\n" + "=" * 60)
            log("SUCCESS: Pipeline complete")
            log("=" * 60)

    def _analyze_before(
        self,
        handler: ProjectHandler,
        changed_source_files: list,
    ) -> dict[str, Any]:
        """Measure complexity before the fix."""
        log("  Analyzing 'before' state...")

        repo_path = Path(handler.repo_path)
        existing = [f for f in changed_source_files if (repo_path / f).exists()]

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
            "test_stats": {"passed": 0, "failed": 0, "skipped": 0, "errors": 0},
            "test_time_seconds": 0.0,
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
                "generation_time_seconds": 0.0,
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
